import json
import re

from sf_lib.activity_log import log
from sf_lib.cortex import CortexAgent
from sf_lib.domain_agents import agent_catalog_text, is_known_agent

_ID_COLUMN_RE = re.compile(r"(^|_)id$", re.IGNORECASE)

SYSTEM_INSTRUCTION = """You are the Orchestrator Agent of a multi-agent business data platform.
A user has uploaded ONE file. It may contain information relevant to more than one business
domain at once — do not assume one file only ever belongs to one domain.

Your job: look at the column names and sample rows, and decide which specialized domain agent(s)
should each receive which columns. A single file with customer_id, order_id, supplier_id,
shipment_date, revenue, and cost columns should be split: customer_id-related columns go to the
Customer Agent, supplier_id-related columns to the Supplier Agent, shipment_date-related columns
to the Delivery Agent, revenue/cost to the Finance Agent, and so on. A shared key column that more
than one agent genuinely needs to join on (e.g. order_id needed by both Order Agent and Delivery
Agent) may be assigned to more than one agent — duplicate it in both lists in that case.

You must choose agent keys ONLY from this exact catalog:
{agent_catalog}

Every column must end up in exactly one place: either assigned to at least one agent, or listed in
unassignedColumns if it genuinely fits no domain here (e.g. an internal row number with no
business meaning). Assign at most 2 agents to any single column, and never invent an agent key
that isn't in the catalog above.

Respond with ONLY minified JSON, no markdown fences, no commentary:
{{
  "assignments": [
    {{"agentKey": "string, one of the catalog keys", "columns": ["source column names"], "reasoning": "one short sentence"}}
  ],
  "unassignedColumns": ["source column names that fit no domain"]
}}"""


SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agentKey": {"type": "string"},
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "reasoning": {"type": "string"},
                },
                "required": ["agentKey", "columns", "reasoning"],
                "additionalProperties": False,
            },
        },
        "unassignedColumns": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["assignments", "unassignedColumns"],
    "additionalProperties": False,
}


def split_by_domain(session, columns: list[str], sample_rows: list[dict]) -> dict[str, list[str]]:
    """Returns {agent_key: [source_column, ...]} for every domain the
    orchestrator assigned at least one column to. A column may appear under
    more than one agent_key when the model decided it's a genuine shared join
    key. Unknown/invalid agent keys and empty assignments are dropped.
    """
    agent = CortexAgent(session, SYSTEM_INSTRUCTION.format(agent_catalog=agent_catalog_text()))
    prompt = (
        f"Columns: {json.dumps(columns)}\n\n"
        f"Sample rows (up to 10):\n{json.dumps(sample_rows, default=str)}\n\n"
        "Decide the domain routing now."
    )
    result = agent.generate_json(prompt, SCHEMA)

    by_agent: dict[str, list[str]] = {}
    for item in result.get("assignments", []):
        key = item.get("agentKey", "")
        cols = [c for c in item.get("columns", []) if c in columns]
        if not is_known_agent(key) or not cols:
            continue
        by_agent.setdefault(key, [])
        for c in cols:
            if c not in by_agent[key]:
                by_agent[key].append(c)

    # The model is instructed to duplicate shared join-key columns across
    # every domain that needs them, but doesn't always follow that reliably.
    # Guarantee it in code instead: any id-like column (e.g. customer_id)
    # propagates to EVERY domain this same upload was split across, so
    # cross-domain queries always have a column to join on, regardless of
    # what the model actually decided per column.
    id_columns = [c for c in columns if _ID_COLUMN_RE.search(c)]
    for agent_key in by_agent:
        for c in id_columns:
            if c not in by_agent[agent_key]:
                by_agent[agent_key].append(c)

    log(f"🧭 Orchestrator routed this upload to: {', '.join(by_agent.keys()) or '(nothing matched)'}")
    return by_agent
