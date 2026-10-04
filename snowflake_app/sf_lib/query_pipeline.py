import contextvars
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from sf_lib import catalog_service, conversation, domain_agent, metadata
from sf_lib.activity_log import log
from sf_lib.query_understanding import understand_query
from sf_lib.result_interpretation import interpret_results
from sf_lib.sql_validator import SqlValidationError, validate_read_only_sql

logger = logging.getLogger("app.query")

# ── Supply-chain metric keywords — when ANY of these appear in the user
#    question the pipeline routes through Cortex Analyst (semantic view)
#    instead of freestyle domain-agent SQL, guaranteeing governed answers.
_SC_METRIC_KEYWORDS = [
    "on-time delivery", "on time delivery", "otd", "otd%",
    "fill rate", "fill_rate", "fillrate",
    "days of inventory", "doi", "inventory days", "inventory position",
    "landed cost", "landed_cost", "total cost per unit",
    "supplier scorecard", "supplier ranking", "supplier performance",
    "supply chain health", "supply chain kpi", "sc kpi",
]

SEMANTIC_VIEW_NAME = "SC_SUPPLY_CHAIN"


def _is_sc_metric_question(question: str) -> bool:
    q_lower = question.lower()
    return any(kw in q_lower for kw in _SC_METRIC_KEYWORDS)


def _query_via_cortex_analyst(session, ctx: dict, question: str, persona: str | None = None) -> dict | None:
    """Route the question through Cortex Analyst against the governed
    semantic view.  Returns the first result set or None on failure."""
    sv_fqn = f'"{ctx["database"]}"."{ctx["schema"]}"."{SEMANTIC_VIEW_NAME}"'
    persona_hint = ""
    if persona:
        persona_hint = f" Answer from the perspective of the {persona} team."
    full_question = question + persona_hint

    try:
        log(f"📊 Routing to Cortex Analyst (semantic view {SEMANTIC_VIEW_NAME}, persona={persona or 'default'})")
        payload = json.dumps({
            "messages": [{"role": "user", "content": [{"type": "text", "text": full_question}]}],
            "semantic_view": sv_fqn,
        }).replace("'", "''")

        row = session.sql(
            f"SELECT SNOWFLAKE.CORTEX.ANALYST_RUN('{payload}') AS RESP"
        ).collect()

        if not row:
            return None
        resp = json.loads(row[0]["RESP"])
        # Analyst returns content blocks — find the SQL one and the text one
        sql_text = None
        answer_text = None
        for block in resp.get("content", []):
            if block.get("type") == "sql":
                sql_text = block.get("statement", "")
            elif block.get("type") == "text":
                answer_text = block.get("text", "")

        if sql_text:
            log(f"📊 Cortex Analyst generated SQL, executing...")
            result_rows = session.sql(sql_text).collect()
            rows = [r.as_dict() for r in result_rows]
            return {"sql": sql_text, "rows": rows, "answer": answer_text}
        elif answer_text:
            return {"sql": None, "rows": [], "answer": answer_text}
        return None
    except Exception as exc:
        log(f"⚠️ Cortex Analyst failed, falling back to domain agents: {exc}")
        logger.warning("Cortex Analyst call failed: %s", exc)
        return None

# Every response — success or short-circuit (clarification, no data, error,
# entity not found, ...) — carries this full field set with sensible empty
# defaults, so callers (the React/Streamlit UIs) never have to guess which
# fields a given response actually included.
_BASE_RESPONSE = {
    "entity": None,
    "result": [],
    "timeline": [],
    "summary": None,
    "visualization": None,
    "sql": None,
    "agents_consulted": [],
    "missing_info": [],
}


def _response(session_id: str, answer: str, intent: str, **overrides) -> dict:
    return {**_BASE_RESPONSE, "session_id": session_id, "answer": answer, "intent": intent, **overrides}


def _agent_keys_for_relevant_tables(relevant_tables: list[str], table_to_agent: dict[str, str]) -> list[str]:
    """Resolves query_understanding's relevantTables (loosely-formatted table
    references from the model) to the actual owning agent_key, in order,
    without duplicates.
    """
    agent_keys: list[str] = []
    for t in relevant_tables:
        t_upper = (t or "").upper()
        for table_name, agent_key in table_to_agent.items():
            if table_name in t_upper and agent_key not in agent_keys:
                agent_keys.append(agent_key)
    return agent_keys


def _call_one_agent(
    session, ctx: dict, agent_key: str, catalog: str, question: str,
    entity_type: str | None, entity_id: str | None,
) -> tuple[str, str | None, list[dict], Exception | None]:
    try:
        sql_used, rows = domain_agent.answer_via_agent(session, ctx, agent_key, catalog, question, entity_type, entity_id)
        return agent_key, sql_used, rows, None
    except Exception as exc:  # noqa: BLE001 - one failing agent must not crash the whole question
        return agent_key, None, [], exc


def _dispatch_agents(
    session, ctx: dict, agents_to_call: list[str], catalog: str, question: str,
    entity_type: str | None, entity_id: str | None,
    session_factory: Callable[[], object] | None,
) -> list[tuple[str, str | None, list[dict], Exception | None]]:
    """Runs each relevant domain agent's turn. Sequential by default (safe
    with just the one shared session). When a session_factory is given and
    there's more than one agent to call, dispatches them in parallel instead
    — a single Snowflake session can only run one query at a time, so real
    concurrency needs one independent session per parallel call, opened here
    and closed when that call finishes.
    """
    if not session_factory or len(agents_to_call) <= 1:
        return [
            _call_one_agent(session, ctx, agent_key, catalog, question, entity_type, entity_id)
            for agent_key in agents_to_call
        ]

    # Propagate the calling thread's contextvars (activity_log's per-request
    # capture list) into each worker thread — a plain ThreadPoolExecutor
    # submission would otherwise start each worker in a fresh context, and
    # log() calls made inside it would silently miss the outer capture().
    # A `Context` object can only be entered by one thread at a time, so each
    # worker needs its OWN copy — sharing a single copy across threads raises
    # "cannot enter context: already entered" the moment two workers overlap.

    def _run_in_own_session(agent_key: str, ctx_snapshot: contextvars.Context):
        worker_session = session_factory()
        try:
            return ctx_snapshot.run(
                _call_one_agent, worker_session, ctx, agent_key, catalog, question, entity_type, entity_id
            )
        finally:
            try:
                worker_session.close()
            except Exception:  # noqa: BLE001
                pass

    results = []
    with ThreadPoolExecutor(max_workers=len(agents_to_call)) as executor:
        futures = {
            executor.submit(_run_in_own_session, agent_key, contextvars.copy_context()): agent_key
            for agent_key in agents_to_call
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results


def ask_question(
    session, ctx: dict, question: str, session_id: str | None,
    session_factory: Callable[[], object] | None = None,
    persona: str | None = None,
) -> dict:
    session_id = session_id or conversation.new_session_id()
    metadata.append_message(session, ctx, session_id, "user", question)

    domains = metadata.list_ready_domains(session, ctx)
    if not domains:
        answer = "You don't have any data loaded yet. Upload and confirm a file first, then come back and ask about it."
        metadata.append_message(session, ctx, session_id, "assistant", answer)
        return _response(session_id, answer, "error")

    # ── GOVERNED PATH: route supply-chain metric questions through Cortex
    #    Analyst against the semantic view instead of freestyle agent SQL.
    if _is_sc_metric_question(question):
        analyst_result = _query_via_cortex_analyst(session, ctx, question, persona)
        if analyst_result is not None:
            answer = analyst_result.get("answer") or "Here are the results from the governed semantic view."
            sql_used = analyst_result.get("sql")
            rows = analyst_result.get("rows", [])
            metadata.append_message(
                session, ctx, session_id, "assistant", answer,
                sql_generated=sql_used or "",
            )
            return _response(
                session_id, answer, "analytics",
                result=rows,
                sql=sql_used,
                agents_consulted=["cortex_analyst (semantic view)"],
                summary={"governed_by": SEMANTIC_VIEW_NAME, "persona": persona or "default"},
            )
        log("⚠️ Cortex Analyst unavailable, falling through to domain agents")

    catalog = catalog_service.build_dataset_catalog(session, ctx, domains)
    history = metadata.get_recent_history(session, ctx, session_id)
    history_text = conversation.history_to_text(history)

    log(f"🧠 Query Understanding: \"{question}\"")
    understanding = understand_query(session, question, catalog, history_text)
    intent = understanding.get("intent", "analytics")
    log(
        f"🧠 Understood as intent={intent}, entity={understanding.get('entityType')}"
        f"/{understanding.get('entityId')}, relevantTables={understanding.get('relevantTables')}"
    )

    if intent == "clarification":
        answer = understanding.get("clarificationQuestion") or "Could you clarify what you mean?"
        metadata.append_message(session, ctx, session_id, "assistant", answer)
        return _response(session_id, answer, "clarification")

    allowed_tables = catalog_service.allowed_table_names(domains)
    table_to_agent = catalog_service.table_to_agent_key(domains)
    agent_keys = _agent_keys_for_relevant_tables(understanding.get("relevantTables", []), table_to_agent)
    if not agent_keys:
        agent_keys = list(dict.fromkeys(table_to_agent.values()))[:1]

    # entity_investigation: each relevant domain independently answers the
    # part concerning its own table (parallel, per-entity facts). analytics:
    # a single domain agent gets the full catalog and may join other tables
    # itself if the aggregate genuinely spans more than one — asking every
    # relevant domain separately would fragment a cross-table aggregate.
    agents_to_call = agent_keys if intent == "entity_investigation" else agent_keys[:1]

    entity_type = understanding.get("entityType")
    entity_id = understanding.get("entityId")

    if len(agents_to_call) > 1 and session_factory:
        log(f"📡 Asking {len(agents_to_call)} agents in parallel: {', '.join(agents_to_call)}")
    else:
        log(f"📡 Asking {', '.join(agents_to_call)} to write and run its own query")

    call_results = _dispatch_agents(session, ctx, agents_to_call, catalog, question, entity_type, entity_id, session_factory)

    # Parallel dispatch completes in whichever order finishes first, not
    # submission order — rebuild everything in agents_to_call's original
    # priority order so "primary" stays deterministic regardless of timing.
    results_by_agent = {agent_key: (sql_used, rows, error) for agent_key, sql_used, rows, error in call_results}

    labeled_results: dict[str, list[dict]] = {}
    agents_consulted: list[str] = []
    sql_by_agent: dict[str, str] = {}
    for agent_key in agents_to_call:
        sql_used, rows, error = results_by_agent.get(agent_key, (None, [], None))
        if error is not None:
            log(f"⚠️ {agent_key} failed, skipping: {error}")
            continue
        if sql_used is None:
            log(f"📡 {agent_key} found nothing relevant, skipped")
            continue
        try:
            validate_read_only_sql(sql_used, ctx["database"], ctx["schema"], allowed_tables)
        except SqlValidationError as exc:
            log(f"⚠️ Discarding {agent_key}'s query — failed validation: {exc}")
            continue
        log(f"📡 {agent_key} returned {len(rows)} row(s)")
        labeled_results[agent_key] = rows
        sql_by_agent[agent_key] = sql_used
        agents_consulted.append(agent_key)

    if not agents_consulted:
        answer = "That information isn't available in your uploaded data."
        metadata.append_message(session, ctx, session_id, "assistant", answer)
        return _response(session_id, answer, intent)

    primary_label = agents_consulted[0]
    if intent == "entity_investigation" and not labeled_results.get(primary_label):
        entity_type_out = entity_type or "record"
        answer = f"No {entity_type_out} record was found for '{entity_id}' in your data."
        metadata.append_message(session, ctx, session_id, "assistant", answer, entity_type=entity_type_out, entity_id=entity_id or "")
        return _response(
            session_id, answer, intent,
            entity={"type": entity_type_out, "id": entity_id} if entity_id else None,
        )

    if not any(labeled_results.values()):
        answer = "No records were found matching your request."
        metadata.append_message(session, ctx, session_id, "assistant", answer)
        return _response(session_id, answer, intent)

    log(f"✅ Agents actually consulted for this question: {', '.join(agents_consulted)}")
    log("💬 Result Interpretation Agent is writing the final answer…")
    interpretation = interpret_results(session, question, understanding, labeled_results, history_text)

    entity = None
    if entity_id:
        entity = {"type": entity_type or "entity", "id": entity_id}

    all_sql = "\n\n".join(f"-- {agent_key}\n{sql}" for agent_key, sql in sql_by_agent.items())
    metadata.append_message(
        session, ctx, session_id, "assistant", interpretation["answer"],
        entity_type=(entity["type"] if entity else ""),
        entity_id=(entity["id"] if entity else ""),
        sql_generated=all_sql,
    )

    return _response(
        session_id, interpretation["answer"], intent,
        entity=entity,
        result=labeled_results.get(primary_label, []),
        timeline=interpretation.get("timeline", []),
        summary=interpretation.get("summary") or None,
        sql=all_sql,
        agents_consulted=agents_consulted,
        missing_info=interpretation.get("missingInfo", []),
    )
