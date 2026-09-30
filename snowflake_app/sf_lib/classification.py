import json

from sf_lib.cortex import CortexAgent
from sf_lib.domain_agents import DOMAIN_AGENTS

SYSTEM_INSTRUCTION = """You are the {label}, a specialist in: {concepts}.

A file upload has been routed to you by the Orchestrator Agent. You have been given only the
columns relevant to YOUR domain (not the whole file) and this domain's EXISTING table schema
(empty if this is the first time your domain has received any data).

For every given source column, decide:
1. Does it MATCH an existing column of your table (same meaning, maybe a different raw name)? If
   so, reuse that EXACT existing column name and type as targetColumn/targetType, and set
   isNewColumn to false — never rename or retype something that already exists.
2. Or is it genuinely NEW information your table doesn't have yet? If so, propose a clean
   snake_case targetColumn name and a Snowflake type, and set isNewColumn to true — this becomes
   an ALTER TABLE ADD COLUMN.

Also determine: a dataset type label for this slice, a confidence score, a suggested table name
(only used the very first time this domain's table is created), data quality issues, ambiguous
fields you're not confident about, and any recommended transformations.

Respond with ONLY minified JSON matching this exact shape, no markdown fences, no commentary:
{{
  "datasetType": "string",
  "confidence": 0.0,
  "suggestedTableName": "string (snake_case)",
  "columns": [
    {{
      "sourceColumn": "string",
      "semanticType": "string",
      "suggestedColumn": "string",
      "suggestedType": "string",
      "primaryKeyCandidate": false,
      "foreignKeyCandidate": false,
      "isNewColumn": true,
      "confidence": 0.0
    }}
  ],
  "dataQualityIssues": ["string"],
  "ambiguousFields": ["string"],
  "recommendedTransformations": ["string"]
}}"""


SCHEMA = {
    "type": "object",
    "properties": {
        "datasetType": {"type": "string"},
        "confidence": {"type": "number"},
        "suggestedTableName": {"type": "string"},
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sourceColumn": {"type": "string"},
                    "semanticType": {"type": "string"},
                    "suggestedColumn": {"type": "string"},
                    "suggestedType": {"type": "string"},
                    "primaryKeyCandidate": {"type": "boolean"},
                    "foreignKeyCandidate": {"type": "boolean"},
                    "isNewColumn": {"type": "boolean"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "sourceColumn", "semanticType", "suggestedColumn", "suggestedType",
                    "primaryKeyCandidate", "foreignKeyCandidate", "isNewColumn", "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "dataQualityIssues": {"type": "array", "items": {"type": "string"}},
        "ambiguousFields": {"type": "array", "items": {"type": "string"}},
        "recommendedTransformations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "datasetType", "confidence", "suggestedTableName", "columns",
        "dataQualityIssues", "ambiguousFields", "recommendedTransformations",
    ],
    "additionalProperties": False,
}


def classify_domain_slice(
    session,
    agent_key: str,
    existing_columns: list[dict],
    source_columns: list[str],
    sample_rows: list[dict],
) -> dict:
    domain = DOMAIN_AGENTS[agent_key]
    system = SYSTEM_INSTRUCTION.format(label=domain["label"], concepts=", ".join(domain["concepts"]))
    agent = CortexAgent(session, system)

    existing_text = (
        json.dumps(existing_columns) if existing_columns else "(this table doesn't exist yet — every column will be new)"
    )
    trimmed_samples = [{k: v for k, v in row.items() if k in source_columns} for row in sample_rows]
    prompt = (
        f"Your existing table's current columns: {existing_text}\n\n"
        f"Columns routed to you from this upload: {json.dumps(source_columns)}\n\n"
        f"Sample rows (up to 10, only your columns):\n{json.dumps(trimmed_samples, default=str)}\n\n"
        "Classify this slice and propose the column mapping now."
    )
    result = agent.generate_json(prompt, SCHEMA)

    result.setdefault("datasetType", agent_key)
    result.setdefault("confidence", 0.0)
    result.setdefault("suggestedTableName", domain["table_name"])
    result.setdefault("columns", [])
    result.setdefault("dataQualityIssues", [])
    result.setdefault("ambiguousFields", [])
    result.setdefault("recommendedTransformations", [])
    return result
