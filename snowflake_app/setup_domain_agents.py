"""One-time (idempotent, safe to rerun) setup: MERGE_TABLE_PROC + RUN_SELECT_PROC
+ ASK_AGENT_PROC (shared by every domain agent), one real CREATE AGENT per
sf_lib/domain_agents.py entry (the "primary" tier our own code calls
directly), and a second "_SUB" tier of the same agents with a reduced tool
set (RunDomainQuery only) used ONLY as agent-to-agent delegation targets.

The two-tier split is a hard, structural guard against infinite agent-to-
agent recursion: a primary agent can ask a _SUB agent a question via the new
AskAnotherAgent tool, but _SUB agents have no AskAnotherAgent tool at all, so
a delegated question can never itself delegate further. Depth is capped at
exactly 1 hop by construction, not by an instruction the model could ignore.

Run from the backend venv (has snowflake-connector-python + the .env creds):
    cd backend && source venv/bin/activate
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 ../snowflake_app/setup_domain_agents.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import snowflake_service  # noqa: E402
from sf_lib.domain_agents import DOMAIN_AGENTS  # noqa: E402

DATABASE = "EGLE_VIEW"
SCHEMA = "PUBLIC"

MERGE_TABLE_PROC_SQL = f"""
CREATE OR REPLACE PROCEDURE {SCHEMA}.MERGE_TABLE_PROC(
  p_database VARCHAR, p_schema VARCHAR, p_table_name VARCHAR, p_columns_json VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
  cols ARRAY DEFAULT PARSE_JSON(:p_columns_json);
  n INT;
  i INT DEFAULT 0;
  col VARIANT;
  col_name VARCHAR;
  col_type VARCHAR;
  col_nullable BOOLEAN;
  col_def VARCHAR;
  col_defs VARCHAR DEFAULT '';
  ddl VARCHAR;
  table_exists_count INT DEFAULT 0;
  existing_cols ARRAY DEFAULT ARRAY_CONSTRUCT();
  added_cols VARCHAR DEFAULT '';
  is_new BOOLEAN;
  info_tables VARCHAR;
  info_columns VARCHAR;
BEGIN
  n := ARRAY_SIZE(cols);
  info_tables := :p_database || '.INFORMATION_SCHEMA.TABLES';
  info_columns := :p_database || '.INFORMATION_SCHEMA.COLUMNS';

  SELECT COUNT(*) INTO :table_exists_count
    FROM IDENTIFIER(:info_tables)
   WHERE TABLE_SCHEMA = :p_schema AND TABLE_NAME = :p_table_name;

  IF (table_exists_count = 0) THEN
    FOR i IN 0 TO n - 1 DO
      col := cols[i];
      col_name := col:name::VARCHAR;
      col_type := col:type::VARCHAR;
      col_nullable := col:nullable::BOOLEAN;
      col_def := '"' || col_name || '" ' || col_type;
      IF (col_nullable = FALSE) THEN
        col_def := col_def || ' NOT NULL';
      END IF;
      IF (i > 0) THEN
        col_defs := col_defs || ', ';
      END IF;
      col_defs := col_defs || col_def;
    END FOR;

    ddl := 'CREATE TABLE "' || :p_database || '"."' || :p_schema || '"."' || :p_table_name || '" (' || col_defs || ')';
    EXECUTE IMMEDIATE :ddl;
    RETURN 'Created new table ' || :p_table_name || ' with ' || n || ' columns.';
  ELSE
    SELECT ARRAY_AGG(UPPER(COLUMN_NAME)) INTO :existing_cols
      FROM IDENTIFIER(:info_columns)
     WHERE TABLE_SCHEMA = :p_schema AND TABLE_NAME = :p_table_name;

    FOR i IN 0 TO n - 1 DO
      col := cols[i];
      col_name := col:name::VARCHAR;
      col_type := col:type::VARCHAR;
      is_new := NOT ARRAY_CONTAINS(UPPER(col_name)::VARIANT, :existing_cols);
      IF (is_new) THEN
        ddl := 'ALTER TABLE "' || :p_database || '"."' || :p_schema || '"."' || :p_table_name ||
               '" ADD COLUMN "' || col_name || '" ' || col_type;
        EXECUTE IMMEDIATE :ddl;
        IF (LENGTH(added_cols) > 0) THEN
          added_cols := added_cols || ', ';
        END IF;
        added_cols := added_cols || col_name;
      END IF;
    END FOR;

    IF (LENGTH(added_cols) = 0) THEN
      RETURN 'Table ' || :p_table_name || ' already has all given columns, nothing to add.';
    END IF;
    RETURN 'Extended existing table ' || :p_table_name || ' with new columns: ' || added_cols;
  END IF;
END;
$$;
"""

RUN_SELECT_PROC_SQL = f"""
CREATE OR REPLACE PROCEDURE {SCHEMA}.RUN_SELECT_PROC(p_sql VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'run'
PACKAGES = ('snowflake-snowpark-python')
EXECUTE AS CALLER
AS
$$
import json

def run(session, p_sql):
    stripped = (p_sql or "").strip()
    first_word = stripped.split(None, 1)[0].upper() if stripped else ""
    if first_word not in ("SELECT", "WITH"):
        raise ValueError("Only SELECT/WITH statements may be run through this tool")
    rows = session.sql(p_sql).collect()
    return json.dumps([r.as_dict() for r in rows], default=str)
$$;
"""

# Takes p_database/p_schema (same explicit pattern as MergeDomainTable/
# RunDomainQuery — the calling agent is told these values in its own prompt,
# see domain_agent.py) and p_agent_key, constrained by the calling agent's
# tool input_schema enum. Always appends "_SUB" to the target itself — the
# calling model can never name a primary agent as its delegation target,
# only ever the tool-restricted sub tier, regardless of what it tries to
# pass. Critically, this proc looks up the target table's LIVE schema and
# hands it to the sub-agent along with the question — otherwise the
# sub-agent has no idea what its own columns are named and can only guess.
ASK_AGENT_PROC_SQL = f"""
CREATE OR REPLACE PROCEDURE {SCHEMA}.ASK_AGENT_PROC(
  p_database VARCHAR, p_schema VARCHAR, p_agent_key VARCHAR, p_question VARCHAR
)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'run'
PACKAGES = ('snowflake-snowpark-python')
EXECUTE AS CALLER
AS
$$
import json
import re

_SAFE_KEY = re.compile(r'^[A-Z_]+$')

def run(session, p_database, p_schema, p_agent_key, p_question):
    key = (p_agent_key or "").upper()
    if not _SAFE_KEY.match(key):
        raise ValueError("Invalid agent key")
    base_key = key.replace("_AGENT", "")
    table_name = f"{{base_key}}_DATA"
    sub_agent_fqn = f"{{p_database}}.PUBLIC.{{base_key}}_AGENT_SUB"

    cols = session.sql(
        f"SELECT COLUMN_NAME, DATA_TYPE FROM IDENTIFIER(?) WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
        params=[p_database + ".INFORMATION_SCHEMA.COLUMNS", p_schema, table_name],
    ).collect()
    if cols:
        cols_desc = ", ".join(f"{{r['COLUMN_NAME']}} ({{r['DATA_TYPE']}})" for r in cols)
        schema_line = f"Your table is {{p_database}}.{{p_schema}}.{{table_name}} with columns: {{cols_desc}}. "
    else:
        schema_line = f"Your table {{p_database}}.{{p_schema}}.{{table_name}} does not exist yet, say so. "

    full_question = schema_line + (p_question or "")
    payload = {{
        "messages": [{{"role": "user", "content": [{{"type": "text", "text": full_question}}]}}],
        "stream": False,
    }}
    payload_literal = json.dumps(payload).replace("'", "''")
    row = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{{sub_agent_fqn}}', '{{payload_literal}}') AS RESP"
    ).collect()[0]
    resp = json.loads(row["RESP"])
    texts = [item.get("text", "") for item in resp.get("content", []) if item.get("type") == "text"]
    return " ".join(texts).strip() or "(no answer)"
$$;
"""


def primary_agent_spec_sql(agent_key: str, domain: dict) -> str:
    agent_name = agent_key.upper()
    concepts = ", ".join(domain["concepts"])
    other_keys = [k.upper() for k in DOMAIN_AGENTS if k != agent_key]
    other_keys_yaml = ", ".join(f'"{k}"' for k in other_keys)
    system = (
        f"You are the {domain['label']} of a multi-agent business data platform. "
        f"You are the expert in: {concepts}. Other agents handle other domains; stay focused on yours."
    )
    orchestration = (
        "If asked to merge/create a table with a given column schema, ALWAYS call MergeDomainTable "
        "with exactly those columns as given, never modify them, never ask for confirmation, the "
        "schema is already final when you're asked to create it. If asked to run a SELECT query to "
        "fetch data, write and run an appropriate SELECT query against your own table via "
        "RunDomainQuery, then reply with a plain one-sentence confirmation of what you found — never "
        "a long write-up, the caller only needs the data, not your commentary. Only call AskAnotherAgent "
        "if the question is EXPLICITLY about a fact that only another domain would have and your own "
        "table genuinely cannot answer it at all — never call it just to add extra detail, to be "
        "thorough, or to double-check something you can already answer yourself; if you do call it, "
        "at most once per turn, always passing the same database and schema you were given. If asked "
        "about ambiguous fields without being asked to create anything or run any query, respond only "
        "with a short clarifying question or a short reassurance in plain text, never call a tool in "
        "that case."
    )
    return f"""
CREATE OR REPLACE AGENT {SCHEMA}.{agent_name}
  COMMENT = 'Domain expert for: {concepts}'
  FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  budget:
    seconds: 120
    tokens: 8000
instructions:
  system: "{system}"
  orchestration: "{orchestration}"
tools:
  - tool_spec:
      type: "generic"
      name: "MergeDomainTable"
      description: "Creates or extends this domain's Snowflake table for a confirmed column schema"
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
            description: "JSON array of {{name, type, nullable}}"
        required: ["p_database", "p_schema", "p_table_name", "p_columns_json"]
  - tool_spec:
      type: "generic"
      name: "RunDomainQuery"
      description: "Runs a read-only SELECT query against this domain's table and returns the rows"
      input_schema:
        type: "object"
        properties:
          p_sql:
            type: "string"
            description: "A single-line SELECT or WITH statement"
        required: ["p_sql"]
  - tool_spec:
      type: "generic"
      name: "AskAnotherAgent"
      description: "Asks ONE other domain agent a direct question and returns its answer. That agent cannot delegate further."
      input_schema:
        type: "object"
        properties:
          p_database:
            type: "string"
          p_schema:
            type: "string"
          p_agent_key:
            type: "string"
            description: "Which other domain agent to ask"
            enum: [{other_keys_yaml}]
          p_question:
            type: "string"
            description: "A direct, self-contained question for that agent"
        required: ["p_database", "p_schema", "p_agent_key", "p_question"]
tool_resources:
  MergeDomainTable:
    type: "procedure"
    identifier: "{DATABASE}.{SCHEMA}.MERGE_TABLE_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
  RunDomainQuery:
    type: "procedure"
    identifier: "{DATABASE}.{SCHEMA}.RUN_SELECT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
  AskAnotherAgent:
    type: "procedure"
    identifier: "{DATABASE}.{SCHEMA}.ASK_AGENT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
$$;
"""


def sub_agent_spec_sql(agent_key: str, domain: dict) -> str:
    """The delegation target for AskAnotherAgent: same persona, but ONLY the
    RunDomainQuery tool — no MergeDomainTable (sub agents are never asked to
    change schema) and, critically, no AskAnotherAgent (this is what makes
    recursion structurally impossible, not just discouraged).
    """
    agent_name = f"{agent_key.upper()}_SUB"
    concepts = ", ".join(domain["concepts"])
    system = (
        f"You are the {domain['label']} of a multi-agent business data platform, being asked a direct "
        f"question by ANOTHER agent (not the end user) about your domain: {concepts}. Answer only from "
        "your own table's data."
    )
    orchestration = (
        "Write and run an appropriate SELECT query against your own table via RunDomainQuery to answer "
        "the question, then summarize the answer in one short sentence. If nothing in your table is "
        "relevant, say so in one short sentence instead of calling the tool."
    )
    return f"""
CREATE OR REPLACE AGENT {SCHEMA}.{agent_name}
  COMMENT = 'Delegation-only sub-agent for: {concepts} (no further delegation possible)'
  FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  budget:
    seconds: 60
    tokens: 8000
instructions:
  system: "{system}"
  orchestration: "{orchestration}"
tools:
  - tool_spec:
      type: "generic"
      name: "RunDomainQuery"
      description: "Runs a read-only SELECT query against this domain's table and returns the rows"
      input_schema:
        type: "object"
        properties:
          p_sql:
            type: "string"
            description: "A single-line SELECT or WITH statement"
        required: ["p_sql"]
tool_resources:
  RunDomainQuery:
    type: "procedure"
    identifier: "{DATABASE}.{SCHEMA}.RUN_SELECT_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
$$;
"""


def main():
    with snowflake_service.get_connection() as conn:
        cur = conn.cursor()

        print("Creating MERGE_TABLE_PROC...")
        cur.execute(MERGE_TABLE_PROC_SQL)

        print("Creating RUN_SELECT_PROC...")
        cur.execute(RUN_SELECT_PROC_SQL)

        print("Creating ASK_AGENT_PROC...")
        # CREATE OR REPLACE only replaces a matching signature — an earlier
        # 2-arg version of this proc would otherwise be left behind as a
        # stale duplicate overload.
        cur.execute(f"DROP PROCEDURE IF EXISTS {SCHEMA}.ASK_AGENT_PROC(VARCHAR, VARCHAR)")
        cur.execute(ASK_AGENT_PROC_SQL)

        cur.execute(f"GRANT USAGE ON PROCEDURE {SCHEMA}.MERGE_TABLE_PROC(VARCHAR, VARCHAR, VARCHAR, VARCHAR) TO ROLE PUBLIC")
        cur.execute(f"GRANT USAGE ON PROCEDURE {SCHEMA}.RUN_SELECT_PROC(VARCHAR) TO ROLE PUBLIC")
        cur.execute(f"GRANT USAGE ON PROCEDURE {SCHEMA}.ASK_AGENT_PROC(VARCHAR, VARCHAR, VARCHAR, VARCHAR) TO ROLE PUBLIC")

        for agent_key, domain in DOMAIN_AGENTS.items():
            sub_name = f"{agent_key.upper()}_SUB"
            print(f"Creating agent {sub_name}...")
            cur.execute(sub_agent_spec_sql(agent_key, domain))
            cur.execute(f"GRANT USAGE ON AGENT {SCHEMA}.{sub_name} TO ROLE PUBLIC")

        for agent_key, domain in DOMAIN_AGENTS.items():
            agent_name = agent_key.upper()
            print(f"Creating agent {agent_name}...")
            cur.execute(primary_agent_spec_sql(agent_key, domain))
            cur.execute(f"GRANT USAGE ON AGENT {SCHEMA}.{agent_name} TO ROLE PUBLIC")

        print("Done.")
        cur.close()


if __name__ == "__main__":
    main()
