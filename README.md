# EgleView — Multi-Agent Data Platform on Snowflake Cortex

Upload raw business files (CSV/Excel/JSON). An **Orchestrator Agent** splits each upload
across however many business domains it touches. **N real, tool-calling Cortex Agents**
(seven today — not a fixed count) each own one persistent table for their domain, extending
it across uploads via `ALTER TABLE` instead of replacing it on every upload. Ask a question
in plain English and the relevant domain agent(s) write and run their own SQL, consult each
other directly when needed, and a final step writes the plain-English answer.

## Why this is real agents, not "an LLM writing SQL"

Everything that touches Snowflake data goes through a real `CREATE AGENT` object invoked via
`SNOWFLAKE.CORTEX.DATA_AGENT_RUN` — not a plain `COMPLETE` call that happens to return SQL:

- **Two tiers, by construction**: 7 *primary* agents (callable directly, can delegate) and 7
  `_SUB` agents (delegation target only). `_SUB` agents simply have no `AskAnotherAgent` tool
  in their spec, so a delegated question can never itself delegate further — recursion is
  capped at exactly one hop structurally, not by an instruction the model could ignore.
- **SQL is authored *and* executed inside the same agent call.** A domain agent writes its
  own query and calls its `RunDomainQuery` tool in one turn — there's no separate
  SQL-generation step handing it pre-written SQL.
- **Agent-to-agent delegation is real**: a primary agent can call `AskAnotherAgent` to ask a
  different domain's `_SUB` agent a direct question when a query needs a shared key it
  doesn't own.
- **Verified against the live account from the command line**, independent of the app code —
  see `snowflake_app/snow_cli_tools.sh` below.

## Stack

Two runtimes share one pipeline (`snowflake_app/sf_lib`) — they differ only in how a
Snowpark session is obtained and how the caller's schema is resolved:

- **Streamlit-in-Snowflake** (`snowflake_app/streamlit_app.py`) — real per-user Snowflake
  logins, isolated by Snowflake's own RBAC.
- **FastAPI + React** (`backend/`, `frontend/`) — one shared privileged connection, isolates
  users via a dynamically provisioned schema name (`USER_<hash>`).

| Layer | Tech |
|---|---|
| Agents / data | Snowflake Cortex Agents, Snowpark, stored procedures |
| Backend | FastAPI (Python 3.12), SQLite for app metadata, Google Sign-In |
| Frontend | React + TypeScript + Vite |
| Ops / CLI | Snowflake CLI (`snow`) — inspect and test live agents from the terminal |

## Architecture — `sf_lib` module map

One module, one responsibility, imported identically by both runtimes:

```
snowflake_app/
  sf_lib/
    orchestrator.py          splits an upload's columns across domains; force-propagates
                             _id-suffixed columns so cross-domain joins have a shared key
    classification.py        per-domain schema proposal (plain structured Cortex COMPLETE call)
    cortex.py                shared wrapper around SNOWFLAKE.CORTEX.COMPLETE (structured JSON)
    domain_agent.py          every real Cortex Agent call: merge table, run query, ask another agent
    domain_agents.py         registry — label, concepts, fixed table name per domain
    ingestion.py             parses an uploaded file (CSV/Excel/JSON) into a DataFrame
    ingestion_pipeline.py    Stage 1 orchestration: analyze -> review -> confirm -> merge -> load
    query_understanding.py  plain Cortex COMPLETE call: intent, entity, relevant tables
    query_pipeline.py        Stage 2 orchestration: understand -> dispatch (parallel) -> interpret
    result_interpretation.py plain Cortex COMPLETE call: final answer, timeline, summary
    catalog_service.py       renders live domain tables + relationships as prompt text
    metadata.py              CRUD against the APP_* Snowflake metadata tables
    schema_service.py        column-mapping normalization, cast-and-load, upsert-vs-append
    sql_validator.py         post-hoc safety check on agent-authored SQL
    conversation.py          follow-up context per chat session
    naming.py                sanitizes arbitrary strings into safe Snowflake identifiers
    rbac.py                  Streamlit-only viewer identity (local-dev picker fallback)
    activity_log.py          framework-agnostic trace: st.session_state in Streamlit,
                             contextvars in FastAPI
    demo_seed.py             loads the bundled demo CSVs straight through the real pipeline
  setup_domain_agents.py     generates MERGE_TABLE_PROC / RUN_SELECT_PROC / ASK_AGENT_PROC
                             plus the 14 CREATE AGENT objects (7 primary + 7 _SUB)
  snow_cli_tools.sh          snow CLI ops: list-agents, ask <AGENT_NAME> "<question>"
  streamlit_app.py
backend/
  app/
    routers/                 auth.py, datasets.py, query.py — call sf_lib directly
    services/snowpark_service.py   bridges the FastAPI process into sf_lib's Snowpark session
frontend/
  src/pages/                LoginPage, OnboardingPage, DashboardPage
  src/components/           ResultView, SchemaMappingTable, NavBar, ...
```

## The domain agents (today)

| Agent | Table | Handles |
|---|---|---|
| Customer Agent | `CUSTOMER_DATA` | customer, user id, registration, segment |
| Order Agent | `ORDER_DATA` | order, items, totals, status, payment |
| Finance Agent | `FINANCIAL_DATA` | revenue, expenses, margin, transactions |
| Delivery Agent | `DELIVERY_DATA` | shipment, ETA, carrier, delay, on-time rate |
| Product Agent | `PRODUCT_DATA` | product, SKU, category, price |
| Inventory Agent | `INVENTORY_DATA` | stock level, reorder level, warehouse |
| Supplier Agent | `SUPPLIER_DATA` | supplier, procurement, lead time, reliability |

Adding an eighth is a registry entry in `sf_lib/domain_agents.py` plus rerunning
`setup_domain_agents.py` — N is not hardcoded anywhere in the pipeline.

## Using the Snowflake CLI against the live agents

`snowflake_app/snow_cli_tools.sh` is a thin wrapper around `snow sql`, hitting the exact same
`SNOWFLAKE.CORTEX.DATA_AGENT_RUN` call `sf_lib/domain_agent.py` makes — just triggered from a
terminal instead of a request handler. Useful for ops, debugging, and demoing the agents
independent of either app.

```bash
pip install snowflake-cli
snow connection add --connection-name egleview \
  --account <SNOWFLAKE_ACCOUNT> --user <SNOWFLAKE_USER> --password <SNOWFLAKE_PASSWORD> \
  --warehouse <SNOWFLAKE_WAREHOUSE> --database <SNOWFLAKE_DATABASE> --schema PUBLIC \
  --role <SNOWFLAKE_ROLE>

cd snowflake_app
./snow_cli_tools.sh list-agents
./snow_cli_tools.sh ask CUSTOMER_AGENT "how many customers are there"
```

## Diagrams

Static, hand-authored reference images in `docs/diagrams/`:
`01_workflow.png`, `02_entity_relationship.png`, `03_architecture.png`, `04_low_level_design.png`.

## Setup

### 1. Snowflake objects

```bash
cd backend && source venv/bin/activate   # needs snowflake-connector-python + .env creds
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 ../snowflake_app/setup_domain_agents.py
```

Idempotent — safe to rerun after adding a new domain or changing an agent's instructions.

### 2. Backend

```bash
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
uvicorn app.main:app --reload --port 8001
```

Fill in `backend/.env`:
- `JWT_SECRET` — any long random string.
- `GOOGLE_CLIENT_ID` — OAuth 2.0 Client ID from console.cloud.google.com (Web application;
  add every origin that will call it — `http://localhost:5173` for local dev, plus your
  deployed frontend's URL).
- `SNOWFLAKE_ACCOUNT` / `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` (or
  `SNOWFLAKE_PRIVATE_KEY_PATH`) / `SNOWFLAKE_ROLE` / `SNOWFLAKE_WAREHOUSE` /
  `SNOWFLAKE_DATABASE` — the role needs rights to create/alter tables, procedures, and agents
  in that database.
- `ALLOW_DEMO_LOGIN` (defaults `true`) — two fixed demo accounts that bypass Google Sign-In,
  useful for local testing and judging; set to `false` for a real deployment.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_GOOGLE_CLIENT_ID must match the backend's GOOGLE_CLIENT_ID
npm run dev
```

Open http://localhost:5173.

### 4. Deploying

Backend → Render (Root Directory `backend`, start command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Python 3.12). Frontend → Vercel (Root
Directory `frontend`; `VITE_API_BASE_URL` pointed at the Render URL). After both are live,
update the backend's `CORS_ORIGINS` to include the deployed frontend's URL, and add that same
URL as an authorized JavaScript origin in the Google OAuth client.

## Known rough edges

- `backend/app_metadata.db` (SQLite) holds dataset/conversation metadata and is **not**
  durable on most PaaS free tiers (wiped on redeploy/restart) — re-run the demo seed after a
  cold start rather than expecting history to persist indefinitely.
- `backend/app/services/{gemini_client,classification_service,query_understanding_service,
  sql_generation_service,result_interpretation_service}.py` are leftover from an earlier,
  pre-rebuild version of this project that used Gemini for every agent. They are **not**
  imported by anything (`app/routers/*.py` import from `sf_lib` exclusively) — dead code kept
  around only because nothing has deleted it yet.
- Ingestion handles structured/semi-structured files (CSV/Excel/JSON) only — there's no
  unstructured document (PDF/image) ingestion path.
