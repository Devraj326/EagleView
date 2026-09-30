"""Thin wrapper around SNOWFLAKE.CORTEX.COMPLETE.

Uses the message-history form with `response_format` (a JSON Schema) for
every structured call — verified live against a real Cortex-enabled account:
COMPLETE(model, [{'role':...,'content':...}, ...], {'response_format': {...}})
returns `{"structured_output": [{"raw_message": <schema-conforming object>}], ...}`.

This replaced an earlier plain-string-prompt approach: without a schema, the
model would embed literal unescaped double quotes inside JSON string values
(e.g. quoted SQL identifiers), which is exactly what structured decoding
exists to prevent — worth the slightly heavier call shape.
"""

import json

DEFAULT_MODEL = "llama3.1-70b"


class CortexAgent:
    def __init__(self, session, system_instruction: str, model: str = DEFAULT_MODEL):
        self.session = session
        self.system_instruction = system_instruction
        self.model = model

    def generate_json(self, prompt: str, schema: dict) -> dict:
        messages = [
            {"role": "system", "content": self.system_instruction},
            {"role": "user", "content": prompt},
        ]
        # max_tokens: a real truncation bug hit during testing (default cap
        # cut off a valid-but-long JSON response mid-string) once the
        # dataset catalog got large enough to eat into the completion budget.
        options = {"response_format": {"type": "json", "schema": schema}, "max_tokens": 4096}
        # Snowpark's qmark binding can't map nested dict/list params directly
        # (a real error hit during testing) — JSON-encode them as strings and
        # let PARSE_JSON build the ARRAY/OBJECT server-side instead.
        row = self.session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, PARSE_JSON(?), PARSE_JSON(?)) AS RESP",
            params=[self.model, json.dumps(messages), json.dumps(options)],
        ).collect()[0]

        wrapper = json.loads(row["RESP"])
        return wrapper["structured_output"][0]["raw_message"]

    def generate_text(self, prompt: str) -> str:
        """Plain-string form for free-text answers with no fixed shape
        (e.g. the final natural-language answer field inside a larger
        schema is still structured — this is only for genuinely free text).
        """
        combined = f"{self.system_instruction}\n\n{prompt}"
        row = self.session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS RESP", params=[self.model, combined]
        ).collect()[0]
        return (row["RESP"] or "").strip()
