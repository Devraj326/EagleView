"""Execute all agent CREATE + GRANT statements using domain_agents registry."""
import snowflake.connector, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_lib.domain_agents import DOMAIN_AGENTS

env_path = Path(r"C:\Users\anujs\Downloads\Demo Data\SF_hackathon\EagleView\backend\.env")
for line in env_path.read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"')

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    warehouse="COMPUTE_WH",
    database="EGLE_VIEW",
    role="ACCOUNTADMIN",
)
cur = conn.cursor()

DB = "EGLE_VIEW"
SC = "PUBLIC"

def make_sub(key, domain):
    name = f"{key.upper()}_SUB"
    concepts = ", ".join(domain["concepts"])
    sys_prompt = f"You are the {domain['label']}, answering a question from another agent about: {concepts}."
    return f"""CREATE OR REPLACE AGENT {SC}.{name}
  COMMENT = 'Sub-agent for {domain["label"]}'
  FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  budget:
    seconds: 60
    tokens: 8000
instructions:
  system: "{sys_prompt}"
  orchestration: "Write a SELECT via RunDomainQuery, summarize in one sentence."
tools:
  - tool_spec:
      type: "generic"
      name: "RunDomainQuery"
      description: "Runs a read-only SELECT query"
      input_schema:
        type: "object"
        properties:
          p_sql:
            type: "string"
        required: ["p_sql"]
tool_resources:
  RunDomainQuery:
    type: "procedure"
    identifier: "{DB}.{SC}.RUN_SELECT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
$$"""

def make_primary(key, domain):
    name = key.upper()
    concepts = ", ".join(domain["concepts"])
    others = [k.upper() for k in DOMAIN_AGENTS if k != key]
    enum_str = ", ".join(f'"{o}"' for o in others)
    sys_prompt = f"You are the {domain['label']}. Expert in: {concepts}. Stay focused on your domain."
    return f"""CREATE OR REPLACE AGENT {SC}.{name}
  COMMENT = 'Domain expert: {domain["label"]}'
  FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  budget:
    seconds: 120
    tokens: 8000
instructions:
  system: "{sys_prompt}"
  orchestration: "If asked to merge a table, call MergeDomainTable. If asked to query, use RunDomainQuery. Only AskAnotherAgent if genuinely needed."
tools:
  - tool_spec:
      type: "generic"
      name: "MergeDomainTable"
      description: "Creates or extends a domain table"
      input_schema:
        type: "object"
        properties:
          p_database:
            type: "string"
          p_schema:
            type: "string"
          p_table_name:
            type: "string"
          p_columns_json:
            type: "string"
        required: ["p_database", "p_schema", "p_table_name", "p_columns_json"]
  - tool_spec:
      type: "generic"
      name: "RunDomainQuery"
      description: "Runs a read-only SELECT query"
      input_schema:
        type: "object"
        properties:
          p_sql:
            type: "string"
        required: ["p_sql"]
  - tool_spec:
      type: "generic"
      name: "AskAnotherAgent"
      description: "Asks one other domain agent a question"
      input_schema:
        type: "object"
        properties:
          p_database:
            type: "string"
          p_schema:
            type: "string"
          p_agent_key:
            type: "string"
            enum: [{enum_str}]
          p_question:
            type: "string"
        required: ["p_database", "p_schema", "p_agent_key", "p_question"]
tool_resources:
  MergeDomainTable:
    type: "procedure"
    identifier: "{DB}.{SC}.MERGE_TABLE_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
  RunDomainQuery:
    type: "procedure"
    identifier: "{DB}.{SC}.RUN_SELECT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
  AskAnotherAgent:
    type: "procedure"
    identifier: "{DB}.{SC}.ASK_AGENT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
$$"""

# Create all sub-agents first (primaries reference them via AskAnotherAgent)
for key, domain in DOMAIN_AGENTS.items():
    sub_name = f"{key.upper()}_SUB"
    print(f"Creating {sub_name}...")
    try:
        cur.execute(make_sub(key, domain))
        cur.execute(f"GRANT USAGE ON AGENT {SC}.{sub_name} TO ROLE PUBLIC")
        print(f"  OK")
    except Exception as e:
        print(f"  ERROR: {e}")

# Create all primary agents
for key, domain in DOMAIN_AGENTS.items():
    name = key.upper()
    print(f"Creating {name}...")
    try:
        cur.execute(make_primary(key, domain))
        cur.execute(f"GRANT USAGE ON AGENT {SC}.{name} TO ROLE PUBLIC")
        print(f"  OK")
    except Exception as e:
        print(f"  ERROR: {e}")

# Verify
cur.execute("SHOW AGENTS IN EGLE_VIEW.PUBLIC")
rows = cur.fetchall()
print(f"\nTotal agents: {len(rows)}")
for r in rows:
    print(f"  {r[1]}")

cur.close()
conn.close()
