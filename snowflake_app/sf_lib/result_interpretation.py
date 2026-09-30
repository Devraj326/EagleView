import json

from sf_lib.cortex import CortexAgent

SYSTEM_INSTRUCTION = """You are the Result Interpretation Agent. You turn raw Snowflake query results into
a clear, human-friendly English answer for a non-technical business user. You never expose raw SQL,
column names, or database jargon in the answer text.

Absolute rule: NEVER invent or assume any fact that is not present in the given query results. If a
field the user would expect (e.g. current location, delivery ETA, discount) is not present in any of the
results, explicitly say it isn't available in their uploaded data — do not guess or estimate it.

For a single-value analytical answer: give the number/fact in one or two sentences.
For a multi-row analytical answer: give a one-sentence summary; the raw rows are shown to the user as a
table separately, so do not re-list every row in your prose — just summarize/highlight what stands out.
For an entity investigation: write a short structured narrative covering, only for sections where data
actually exists: overview, key details, related info (customer/payment/delivery/etc as applicable),
a timeline (only if timestamped events exist in the results), and the current status. Reconstruct the
timeline strictly from event/timestamp fields present in the results, in chronological order.
If the primary entity has zero rows, say plainly that no record was found for that id and stop there.

Respond with ONLY minified JSON, no markdown fences, no commentary:
{
  "answer": "string - the full natural-language answer, formatted as readable plain text with line breaks",
  "timeline": [{"timestamp": "string, or the literal string null if this event has no timestamp", "event": "string"}],
  "summary": [{"label": "short key fact label", "value": "its value"}] (empty array if not applicable),
  "missingInfo": ["short phrases naming anything the user would expect that wasn't in the data"]
}"""


SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"timestamp": {"type": "string"}, "event": {"type": "string"}},
                "required": ["timestamp", "event"],
                "additionalProperties": False,
            },
        },
        "summary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
                "required": ["label", "value"],
                "additionalProperties": False,
            },
        },
        "missingInfo": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "timeline", "summary", "missingInfo"],
    "additionalProperties": False,
}


def interpret_results(
    session, question: str, understanding: dict, labeled_results: dict[str, list[dict]], history_text: str
) -> dict:
    agent = CortexAgent(session, SYSTEM_INSTRUCTION)
    trimmed = {label: rows[:50] for label, rows in labeled_results.items()}
    prompt = (
        f"Recent conversation:\n{history_text}\n\n"
        f"User question: {question}\n\n"
        f"Query understanding: {json.dumps(understanding)}\n\n"
        f"Query results by label:\n{json.dumps(trimmed, default=str)}\n\n"
        "Interpret these results now."
    )
    result = agent.generate_json(prompt, SCHEMA)
    result.setdefault("answer", "")
    result.setdefault("timeline", [])
    result.setdefault("summary", [])
    result.setdefault("missingInfo", [])

    for event in result["timeline"]:
        if isinstance(event.get("timestamp"), str) and event["timestamp"].strip().lower() == "null":
            event["timestamp"] = None

    result["summary"] = {
        item["label"]: item["value"] for item in result["summary"] if item.get("label")
    }
    return result
