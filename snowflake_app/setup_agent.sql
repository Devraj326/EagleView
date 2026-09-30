-- One-time setup: the real tool-calling Cortex Agent for ingestion actions.
-- Lives in <database>.PUBLIC and is shared across every user's isolated
-- schema (the proc is schema-agnostic; it takes the target schema as a
-- parameter and issues dynamic SQL against it).

CREATE OR REPLACE PROCEDURE PUBLIC.CREATE_TABLE_PROC(
  p_database VARCHAR, p_schema VARCHAR, p_table_name VARCHAR, p_columns_json VARCHAR
)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
  col_defs VARCHAR DEFAULT '';
  ddl VARCHAR;
  cols ARRAY DEFAULT PARSE_JSON(:p_columns_json);
  i INT DEFAULT 0;
  col VARIANT;
  col_def VARCHAR;
  n INT;
BEGIN
  n := ARRAY_SIZE(cols);
  FOR i IN 0 TO n - 1 DO
    col := cols[i];
    col_def := '"' || col:name::VARCHAR || '" ' || col:type::VARCHAR;
    IF (col:nullable::BOOLEAN = FALSE) THEN
      col_def := col_def || ' NOT NULL';
    END IF;
    IF (i > 0) THEN
      col_defs := col_defs || ', ';
    END IF;
    col_defs := col_defs || col_def;
  END FOR;

  ddl := 'CREATE OR REPLACE TABLE "' || :p_database || '"."' || :p_schema || '"."' || :p_table_name || '" (' || col_defs || ')';
  EXECUTE IMMEDIATE :ddl;
  RETURN 'Created table ' || :p_table_name || ' with ' || n || ' columns.';
END;
$$;

CREATE OR REPLACE AGENT PUBLIC.INGESTION_AGENT
  COMMENT = 'Creates confirmed dataset tables and asks about ambiguous columns'
  FROM SPECIFICATION $$
models:
  orchestration: auto
orchestration:
  budget:
    seconds: 30
    tokens: 8000
instructions:
  system: "You are the Ingestion Agent for a multi-tenant data platform. Users upload raw business data; you help finalize the Snowflake schema for it."
  orchestration: "If asked to create a table with a given column schema, ALWAYS call CreateDatasetTable with exactly those columns as given — never modify them, never ask for confirmation, the schema is already final when you're asked to create it. If asked about ambiguous fields without being asked to create anything, respond only with a short clarifying question or a short reassurance in plain text — never call a tool in that case."
tools:
  - tool_spec:
      type: "generic"
      name: "CreateDatasetTable"
      description: "Creates a Snowflake table for a confirmed dataset schema"
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
            description: "JSON array of {name, type, nullable}"
        required: ["p_database", "p_schema", "p_table_name", "p_columns_json"]
tool_resources:
  CreateDatasetTable:
    type: "procedure"
    identifier: "EGLE_VIEW.PUBLIC.CREATE_TABLE_PROC"
    execution_environment:
      type: "warehouse"
      warehouse: "COMPUTE_WH"
$$;

-- REQUIRED, not optional: verified live that the agent's tool-execution layer
-- runs under a different privilege context than the calling session's own
-- role (granting the proc to ROLE_DEMO_USER_A alone was NOT enough — the
-- agent's tool call failed with "Unknown user-defined function" even though
-- that exact role could CALL the same procedure directly). Granting to
-- PUBLIC is what actually made tool execution resolve the procedure.
GRANT USAGE ON PROCEDURE PUBLIC.CREATE_TABLE_PROC(VARCHAR, VARCHAR, VARCHAR, VARCHAR) TO ROLE PUBLIC;
GRANT USAGE ON AGENT PUBLIC.INGESTION_AGENT TO ROLE PUBLIC;
