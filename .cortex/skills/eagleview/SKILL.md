---
name: eagleview
description: How to work safely and correctly in the EgleView multi-agent Snowflake Cortex codebase — architecture, conventions, and hard constraints discovered through real testing against the live account.
---

# EgleView project skill

EgleView is a multi-agent data platform: an Orchestrator Agent splits an uploaded file across
however many business domains it touches, N real Snowflake Cortex Agents (today: 7) each own
one persistent table for their domain, and a second tier of delegation-only agents lets them
consult each other. Two client surfaces (Streamlit-in-Snowflake, FastAPI+React) share one
pipeline package: `snowflake_app/sf_lib`.

## Before touching anything

Read `README.md` first — it documents the real, current architecture (module map, domain list,
setup, known rough edges). Do not trust any description of this project that mentions Gemini for
every agent or a single generic ingestion agent — that's the pre-rebuild version;
`backend/app/services/{gemini_client,classification_service,query_understanding_service,
sql_generation_service,result_interpretation_service}.py` are its orphaned leftovers, not
imported by anything current.

## Hard rules for this codebase

- **Both runtimes import `sf_lib` directly.** Never duplicate pipeline logic into
  `backend/app/` or `snowflake_app/streamlit_app.py` — add it to `sf_lib` once.
- **Cortex Agent calls, not just `COMPLETE` calls, for anything that touches data.** Schema
  proposal, intent/entity extraction, and final-answer writing are plain structured
  `SNOWFLAKE.CORTEX.COMPLETE` calls (`sf_lib/cortex.py`) — reasoning only, no tools. Creating or
  altering a table, running a query, and asking another domain agent a question MUST go through
  a real `CREATE AGENT` object via `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`
  (`sf_lib/domain_agent.py`). Don't blur this line — it's the difference this project's whole
  pitch rests on.
- **The two-tier agent split is structural, not instructional.** `_SUB` agents have no
  `AskAnotherAgent` tool in their spec. Never add one — that's the entire recursion guard.
- **`DATA_AGENT_RUN` quirks, confirmed by real testing, not documented by Snowflake**: both
  arguments must be literal SQL constants (no bind params, no `PARSE_JSON(?)` around one);
  `stream: false` must always be present; message text must not contain literal `"`, `[`, `{`,
  `}`, `]`, or newlines (strip/collapse before sending). Violating any of these fails with an
  opaque "Request is malformed" — if you see that error, check this list first.
- **Tool execution runs under a different privilege context than the calling role.** Every
  shared proc and agent needs `GRANT USAGE ... TO ROLE PUBLIC`, or tool calls fail with "unknown
  user-defined function" even when the calling role can run the proc directly.
- **A Snowpark session can only run one query at a time.** True parallel dispatch
  (`query_pipeline._dispatch_agents`) needs one independent session per concurrent call, and
  each `contextvars.Context` needs its own `copy_context()` per worker — sharing either across
  threads breaks silently or raises a confusing `RuntimeError`.
- **Domain tables accumulate; they are never replaced.** A second upload into an existing
  domain extends its table via `ALTER TABLE ADD COLUMN` and upserts on the detected primary key
  (`schema_service.load_rows`) — don't "fix" a failed load by dropping and recreating the table.
- **A primary-key column is NOT NULL at the table level.** Drop rows with a null PK before a
  MERGE/INSERT, don't let one bad source row fail the whole batch (this was a real production
  bug, fixed in `schema_service.load_rows`).
- **SQL validation (`sql_validator.py`) is post-hoc**, checked after an agent already authored
  and ran the query, not a pre-filter. Keep it that way — the point is a second independent
  check, not gatekeeping generation.
- **The MCP server (`mcp_server/`) exposes exactly two tools on purpose**: `upload_data` and
  `ask_question`. Don't add more surface area there without an explicit decision to do so — it's
  deliberately minimal.

## Where things live

See `README.md`'s module map for the full picture. The short version: `orchestrator.py`
(routing) → `classification.py` (schema proposal) → `domain_agent.py` (real agent calls) →
`schema_service.py` (cast + load) for ingestion; `query_understanding.py` → `domain_agent.py` →
`result_interpretation.py` for query. `catalog_service.py` and `metadata.py` are the shared
state both paths read/write.

## Testing

`snowflake_app/tests/` holds unit tests for the pieces that don't require a live Snowflake
session (SQL validator, orchestrator routing post-processing). Anything touching real Cortex
Agents has to be verified live — against the account, not mocked — because the quirks above
were themselves only discoverable that way.
