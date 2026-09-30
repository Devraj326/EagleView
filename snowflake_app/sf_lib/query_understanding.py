from sf_lib.cortex import CortexAgent

SYSTEM_INSTRUCTION = """You are the Query Understanding Agent of a natural-language analytics platform.
A user is asking a question in English about THEIR OWN business data, already loaded into Snowflake tables
described below. You must figure out what they want, in structured form, before any SQL is written.

Two kinds of questions:
1. "analytics" — an aggregate/analytical question (counts, sums, averages, top-N, trends, comparisons).
2. "entity_investigation" — the user wants the full story of ONE specific business entity
   (an order, customer, product, shipment, transaction, etc identified by an id/code), e.g.
   "What happened with order 1234?", "Where is shipment SHP-456?", "Tell me about customer 456".

If the question is ambiguous (e.g. no entity id given when one is required, or it's unclear which
metric/dataset they mean), set intent to "clarification" and ask ONE short clarifying question.

Use the conversation history to resolve references like "that order", "the previous month", "that customer".

The given id may not live in the table its entityType implies — e.g. a payment/transaction id given for
an "order" question only exists in a payments table, not the orders table. Don't assume the id is
missing or the question can't be answered just because it doesn't match the obvious table's key format.
For relevantTables, list AT MOST 5 tables: the table the id might actually live in, plus whatever it
directly links to — never more than 5, and never list a table that isn't in the catalog above.

Respond with ONLY minified JSON, no markdown fences, no commentary:
{
  "intent": "analytics" | "entity_investigation" | "clarification",
  "entityType": "string or null (e.g. order, customer, product, shipment, transaction)",
  "entityId": "string or null (the concrete identifier resolved from the question or history)",
  "metric": "string or null (what is being measured/asked for analytics questions)",
  "relevantTables": ["exact quoted table references from the catalog that are needed to answer"],
  "clarificationQuestion": "string or null",
  "reasoning": "one short sentence"
}"""


SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["analytics", "entity_investigation", "clarification"]},
        "entityType": {"type": "string"},
        "entityId": {"type": "string"},
        "metric": {"type": "string"},
        "relevantTables": {"type": "array", "items": {"type": "string"}},
        "clarificationQuestion": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": ["intent", "entityType", "entityId", "metric", "relevantTables", "reasoning"],
}

_NULL_SENTINELS = {"null", "none", "n/a", ""}


def _denull(value):
    if isinstance(value, str) and value.strip().lower() in _NULL_SENTINELS:
        return None
    return value


def understand_query(session, question: str, dataset_catalog: str, history_text: str) -> dict:
    agent = CortexAgent(session, SYSTEM_INSTRUCTION)
    prompt = (
        f"Available datasets and relationships:\n{dataset_catalog}\n\n"
        f"Recent conversation:\n{history_text}\n\n"
        f"User question: {question}\n\n"
        "Determine the intent now."
    )
    result = agent.generate_json(prompt, SCHEMA)
    result.setdefault("intent", "analytics")
    result.setdefault("entityType", None)
    result.setdefault("entityId", None)
    result.setdefault("metric", None)
    result.setdefault("relevantTables", [])
    result.setdefault("clarificationQuestion", None)
    for key in ("entityType", "entityId", "metric", "clarificationQuestion"):
        result[key] = _denull(result[key])
    return result
