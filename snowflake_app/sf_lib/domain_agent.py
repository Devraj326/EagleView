"""Real, tool-calling Cortex Agents — one per business domain (see
sf_lib/domain_agents.py) — that perform the actual ingestion/query actions:
merging a confirmed column schema into that domain's persistent table
(MergeDomainTable -> MERGE_TABLE_PROC), and writing + running a read-only
query against it (RunDomainQuery -> RUN_SELECT_PROC) to help answer a
question — SQL generation happens inside this same real agent call, the
agent composes its own query rather than being handed pre-written SQL.
Schema PROPOSAL still goes through sf_lib/classification.py (a plain
structured COMPLETE call) — pinning an agent's own free-text turns to our
exact JSON shape is far less controlled than a schema-constrained COMPLETE
call. This module is where each domain agent's tool-calling behavior lives.
"""

import json

from sf_lib.activity_log import log


def _agent_fqn(ctx: dict, agent_key: str) -> str:
    return f'{ctx["database"]}.PUBLIC.{agent_key.upper()}'


def run_agent(session, ctx: dict, agent_key: str, user_text: str) -> dict:
    """Runs one turn against the given domain agent and returns a normalized
    dict: {"question": str|None, "tool_calls": [...], "tool_results": [...],
    "answer": str|None}. A tool's actual return value lives in a SEPARATE
    "tool_result" content item (matched by tool_use_id), not on the
    "tool_use" item itself — confirmed by inspecting a live response.
    """
    log(f"→ [{agent_key}] called: {user_text[:120]}{'…' if len(user_text) > 120 else ''}")

    # `stream` must be present — a bare {"messages": [...]} body was rejected
    # as malformed during testing even though the docs call it optional.
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
        "stream": False,
    }
    # Both DATA_AGENT_RUN arguments must be literal constants (a real compile
    # error rules out bind params, and PARSE_JSON(...) around a bind param
    # doesn't count as constant either) — a plain VARCHAR, not a VARIANT.
    agent_fqn = _agent_fqn(ctx, agent_key)
    payload_literal = json.dumps(payload).replace("'", "''")
    row = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{agent_fqn}', '{payload_literal}') AS RESP"
    ).collect()[0]
    resp = json.loads(row["RESP"])

    tool_calls = []
    tool_results = []
    texts = []
    for item in resp.get("content", []):
        t = item.get("type")
        if t == "tool_use":
            tool_calls.append(item["tool_use"])
        elif t == "tool_result":
            tool_results.append(item["tool_result"])
        elif t == "text":
            texts.append(item.get("text", ""))

    final_text = " ".join(texts).strip()
    if tool_calls:
        tool_names = ", ".join(tc.get("name", "?") for tc in tool_calls)
        log(f"← [{agent_key}] called tool(s): {tool_names}")
        return {"question": None, "tool_calls": tool_calls, "tool_results": tool_results, "answer": final_text}
    log(f"← [{agent_key}] replied without calling a tool: {(final_text or '(empty)')[:120]}")
    return {"question": final_text or None, "tool_calls": [], "tool_results": [], "answer": None}


def merge_table_via_agent(session, ctx: dict, agent_key: str, table_name: str, columns: list[dict]) -> str:
    """Asks the domain agent to merge the user's confirmed column schema into
    its persistent table — a real tool call (MergeDomainTable ->
    MERGE_TABLE_PROC), not app code running DDL directly. Creates the table
    the first time, extends it with ALTER TABLE ADD COLUMN on every upload
    after that.
    """
    # Deliberately a single line of plain prose with no embedded brackets or
    # newlines: a real (undocumented) request-validation bug rejects agent
    # messages containing '[', '{', or '\n' in the text, even though those
    # are perfectly valid once escaped inside the outer JSON request.
    col_descriptions = "; ".join(
        f'{c["target_column"]} of type {c["target_type"]}'
        + (" nullable" if c["nullable"] else " not nullable")
        for c in columns
    )
    prompt = (
        f"The user has confirmed this column schema for your domain's table, merge it now using "
        f"the MergeDomainTable tool, do not ask any questions, this mapping is final. "
        f"database is {ctx['database']}, schema is {ctx['schema']}, table name is {table_name}, "
        f"columns are: {col_descriptions}."
    )
    result = run_agent(session, ctx, agent_key, prompt)
    if not any(tc.get("name") == "MergeDomainTable" for tc in result["tool_calls"]):
        raise RuntimeError(
            f"{agent_key} did not merge the table as instructed. It said: {result['question']}"
        )
    return result["answer"] or f"Table {table_name} merged."


def ask_about_ambiguity(session, ctx: dict, agent_key: str, classification: dict) -> str | None:
    """Given the classifier's own flagged ambiguous fields, ask the domain
    agent to phrase ONE clarifying question for a non-technical user, or
    return None if nothing is genuinely unclear.
    """
    ambiguous = classification.get("ambiguousFields", [])
    if not ambiguous:
        return None
    ambiguous_text = ", ".join(str(a) for a in ambiguous)
    prompt = (
        "A dataset classifier flagged these fields as ambiguous while proposing a schema for your "
        f"domain: {ambiguous_text}. Do not call any tool. In one short sentence, ask the user "
        "a plain-English clarifying question about the single most important ambiguity here "
        "(or say there's nothing worth asking about, in one short sentence, if none of these "
        "actually matter for loading the data)."
    )
    result = run_agent(session, ctx, agent_key, prompt)
    return result["question"]


def _extract_tool_result(result: dict, tool_name: str) -> dict | None:
    """A single agent turn can call more than one tool (e.g. AskAnotherAgent
    then RunDomainQuery) — always match by the tool_result's own `name`
    field rather than assuming there's only one result to look at.
    """
    for tr in result["tool_results"]:
        if tr.get("name") == tool_name:
            return tr
    return None


def _extract_rows(result: dict, tool_name: str = "RunDomainQuery") -> list[dict] | None:
    tr = _extract_tool_result(result, tool_name)
    if tr is None:
        return None
    if tr.get("status") != "success":
        raise RuntimeError(f"{tool_name} tool call failed: {tr}")
    for content_item in tr.get("content", []):
        if content_item.get("type") == "json":
            rows_json = content_item["json"].get("result")
            if not rows_json:
                continue
            try:
                return json.loads(rows_json)
            except json.JSONDecodeError:
                log(f"⚠️ {tool_name} returned unparseable output, treating as no rows: {rows_json[:200]!r}")
                return None
    return None


def answer_via_agent(
    session, ctx: dict, agent_key: str, catalog_text: str, question: str,
    entity_type: str | None, entity_id: str | None,
) -> tuple[str | None, list[dict]]:
    """Asks the domain agent to WRITE and RUN an appropriate SQL query
    against its own table — SQL generation happens INSIDE this real Cortex
    Agent call now, not a separate plain COMPLETE call beforehand. Returns
    (sql_it_wrote, rows); sql is None if it decided nothing in its table was
    relevant and didn't call the tool.
    """
    # Double quotes and brackets both trip the same undocumented
    # request-malformed bug as elsewhere in this module — strip them from
    # the catalog text before it goes into the agent's input message. The
    # agent's own *generated* SQL (which comes back in tool_use.input, not
    # through this text) is unaffected by that restriction.
    single_line_catalog = " ".join(catalog_text.replace('"', "").split())
    entity_clause = f"The user is asking about {entity_type} {entity_id}. " if entity_id else ""
    prompt = (
        f"{entity_clause}User question: {question} "
        f"database is {ctx['database']}, schema is {ctx['schema']}. "
        f"Available tables and columns: {single_line_catalog} "
        "Write a single-line read-only SELECT or WITH query, fully qualifying every table as "
        "database.schema.table with no quotes, scoped to answer the part of this question relevant "
        "to your own table — join or use a subquery against the other tables shown above only if "
        "genuinely necessary to resolve a shared key — then call the RunDomainQuery tool with that "
        "exact SQL. If nothing in your table is relevant to this question, do not call any tool, "
        "just say so in one short sentence instead. If you need a fact from another domain instead, "
        "use AskAnotherAgent with the same database and schema given above."
    )
    result = run_agent(session, ctx, agent_key, prompt)
    if not result["tool_calls"]:
        return None, []

    sql_used = None
    for tc in result["tool_calls"]:
        if tc.get("name") == "RunDomainQuery":
            sql_used = tc.get("input", {}).get("p_sql")
            break

    rows = _extract_rows(result)
    return sql_used, rows or []
