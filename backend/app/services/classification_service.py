import json

from app.services.domain_agents import agent_catalog_text
from app.services.gemini_client import GeminiAgent

SYSTEM_INSTRUCTION = """You are the Classification Agent of a multi-agent data ingestion platform.
Given raw tabular data (column names + sample rows), you determine:
1. The dataset type (a short snake_case label, e.g. "inventory", "orders", "customers")
2. The relevant domain and which specialized agent should own it
3. A confidence score (0-1) for the overall classification
4. For every source column: its semantic meaning, a clean suggested column name (snake_case),
   a suggested Snowflake data type (INTEGER, FLOAT, NUMBER(18,2), VARCHAR, BOOLEAN, DATE, TIMESTAMP_NTZ),
   whether it looks like a primary key candidate, whether it looks like a foreign key candidate
   (references another entity, e.g. customer_id, product_id, order_id), and a confidence score.
5. Data quality issues you notice (e.g. "quantity column contains negative values")
6. Ambiguous fields you are not confident about
7. Any transformations you'd recommend (e.g. "trim whitespace", "parse date format DD/MM/YYYY")

You must choose the agent from exactly this catalog (use the key, e.g. "inventory_agent"):
{agent_catalog}

If nothing fits well, use "unknown_agent" with a low confidence and dataset_type "unknown".

Respond with ONLY minified JSON matching this exact shape, no markdown fences, no commentary:
{{
  "datasetType": "string",
  "confidence": 0.0,
  "agent": "string",
  "suggestedTableName": "string (snake_case)",
  "columns": [
    {{
      "sourceColumn": "string",
      "semanticType": "string",
      "suggestedColumn": "string",
      "suggestedType": "string",
      "primaryKeyCandidate": false,
      "foreignKeyCandidate": false,
      "confidence": 0.0
    }}
  ],
  "dataQualityIssues": ["string"],
  "ambiguousFields": ["string"],
  "recommendedTransformations": ["string"]
}}"""


def classify_dataset(columns: list[str], sample_rows: list[dict]) -> dict:
    agent = GeminiAgent(SYSTEM_INSTRUCTION.format(agent_catalog=agent_catalog_text()), temperature=0.1)
    prompt = (
        f"Columns: {json.dumps(columns)}\n\n"
        f"Sample rows (up to 10):\n{json.dumps(sample_rows, default=str)}\n\n"
        "Classify this dataset and propose the column mapping now."
    )
    result = agent.generate_json(prompt)

    # Defensive normalization so a slightly malformed model response never 500s the request.
    result.setdefault("datasetType", "unknown")
    result.setdefault("confidence", 0.0)
    result.setdefault("agent", "unknown_agent")
    result.setdefault("suggestedTableName", result["datasetType"])
    result.setdefault("columns", [])
    result.setdefault("dataQualityIssues", [])
    result.setdefault("ambiguousFields", [])
    result.setdefault("recommendedTransformations", [])
    return result
