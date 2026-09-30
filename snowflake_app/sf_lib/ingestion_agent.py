"""A genuine Snowflake Cortex Agent (not just a COMPLETE call) that performs
the actual ingestion actions — creating the confirmed table is a real tool
call the agent makes, not app code executing SQL directly. Schema PROPOSAL
still goes through sf_lib/classification.py (a plain structured COMPLETE call
— reliable, already verified), because pinning the AGENT's own free-text
turns to our exact JSON shape is far less controlled than a schema-constrained
COMPLETE call. This module is where the agent's tool-calling & clarifying-
question behavior lives, on top of that proposal.

Setup (one-time, see deploy.py): CREATE_TABLE_PROC + CREATE AGENT INGESTION_AGENT
both live in <database>.PUBLIC so every user's app session shares one agent;
the proc takes the target schema as a parameter and uses EXECUTE IMMEDIATE, so
it's schema-agnostic and reusable across every isolated user schema.
"""

import json

AGENT_NAME = "INGESTION_AGENT"


def _agent_fqn(ctx: dict) -> str:
    return f'{ctx["database"]}.PUBLIC.{AGENT_NAME}'


def run_agent(session, ctx: dict, user_text: str) -> dict:
    """Runs one turn against the ingestion agent and returns a normalized
    dict: {"question": str|None, "tool_calls": [...], "answer": str|None}.
    `question`/`answer` are mutually exclusive: the agent either asks the
    user something before acting, or reports what it did.
    """
    # `stream` must be present — a bare {"messages": [...]} body was rejected
    # as malformed during testing even though the docs call it optional.
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
        "stream": False,
    }
    # Both DATA_AGENT_RUN arguments must be literal constants (a real compile
    # error hit during testing rules out bind params, and PARSE_JSON(...)
    # around a bind param doesn't count as constant either) — it also wants a
    # plain VARCHAR, not a VARIANT, matching Snowflake's own tutorial example.
    # Safe to inline: agent_fqn is our own fixed constant, and the payload's
    # only variable content is escaped for a single-quoted SQL literal.
    agent_fqn = _agent_fqn(ctx)
    payload_literal = json.dumps(payload).replace("'", "''")
    row = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{agent_fqn}', '{payload_literal}') AS RESP"
    ).collect()[0]
    resp = json.loads(row["RESP"])

    tool_calls = []
    texts = []
    for item in resp.get("content", []):
        t = item.get("type")
        if t == "tool_use":
            tool_calls.append(item["tool_use"])
        elif t == "text":
            texts.append(item.get("text", ""))

    final_text = " ".join(texts).strip()
    # Heuristic: if the agent called a tool this turn, treat its accompanying
    # text as a status/answer; if it called no tool at all, treat text as a
    # clarifying question back to the user (matches the agent instructions
    # below, which tell it exactly when to do which).
    if tool_calls:
        return {"question": None, "tool_calls": tool_calls, "answer": final_text}
    return {"question": final_text or None, "tool_calls": [], "answer": None}


def create_table_via_agent(session, ctx: dict, table_name: str, columns: list[dict]) -> str:
    """Asks the ingestion agent to create the confirmed table — a real tool
    call the agent makes (CreateDatasetTable -> CREATE_TABLE_PROC), not app
    code running CREATE TABLE directly.
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
        f"The user has confirmed this column schema for a new dataset table, create it now "
        f"using the CreateDatasetTable tool, do not ask any questions, this mapping is final. "
        f"database is {ctx['database']}, schema is {ctx['schema']}, table name is {table_name}, "
        f"columns are: {col_descriptions}."
    )
    result = run_agent(session, ctx, prompt)
    if not result["tool_calls"]:
        raise RuntimeError(
            f"Ingestion agent did not create the table as instructed. It said: {result['question']}"
        )
    return result["answer"] or f"Table {table_name} created."


def ask_about_ambiguity(session, ctx: dict, classification: dict) -> str | None:
    """A lighter-weight use of the same agent: given the classifier's own
    flagged ambiguous fields, ask the agent to phrase ONE clarifying question
    for a non-technical user, or return None if nothing is genuinely unclear.
    This is the "asks the user for the correct columns" behavior, surfaced
    as a note in the schema review UI rather than blocking on a chat reply.
    """
    ambiguous = classification.get("ambiguousFields", [])
    if not ambiguous:
        return None
    # Plain comma-separated text, not a JSON array literal — see the bracket/
    # newline note on create_table_via_agent above.
    ambiguous_text = ", ".join(str(a) for a in ambiguous)
    prompt = (
        "A dataset classifier flagged these fields as ambiguous while proposing a schema: "
        f"{ambiguous_text}. Do not call any tool. In one short sentence, ask the user "
        "a plain-English clarifying question about the single most important ambiguity here "
        "(or say there's nothing worth asking about, in one short sentence, if none of these "
        "actually matter for loading the data)."
    )
    result = run_agent(session, ctx, prompt)
    return result["question"]
