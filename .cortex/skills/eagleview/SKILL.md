# EagleView — Cortex Code Skill

EagleView is a multi-agent data platform built on Snowflake. Users upload files (CSV/Excel/JSON), an AI orchestrator splits columns across business-domain agents, each agent proposes and manages its own table schema, data is loaded via MERGE upserts, cross-domain relationships are discovered automatically, and natural-language questions are answered by domain-specialist Cortex Agents that write and execute their own SQL.

## Deployment

- **Frontend**: React + Vite on Vercel — https://eagle-view-ten.vercel.app/
- **Backend**: FastAPI on Render (see `render.yaml`)
- **Snowflake-native app**: Streamlit-in-Snowflake (see `snowflake_app/streamlit_app.py`)
- **MCP server**: Thin proxy over the backend API (see `mcp_server/server.py`)

## Tech Stack

- **LLM**: Snowflake Cortex COMPLETE (`llama3.1-70b`) via `sf_lib/cortex.py`
- **Agents**: Real Cortex Agent objects via `SNOWFLAKE.CORTEX.DATA_AGENT_RUN()` — 7 primary agents + 7 sub-agents
- **Backend framework**: FastAPI (Python), routers import from `sf_lib` (NOT from `backend/app/services/`)
- **Frontend framework**: React + TypeScript + Vite, Recharts for visualization
- **Data layer**: Snowpark sessions, Snowflake tables for metadata and user data

> **Important**: The files under `backend/app/services/` that use Gemini (`classification_service.py`, `sql_generation_service.py`, `gemini_client.py`) and the old `domain_agents.py` (6 agents, no table_name) are **dead code**. The routers exclusively import from `sf_lib` via `snowpark_service.py` which adds `snowflake_app/` to `sys.path`.

## Repository Structure

```
SF_hackathon/EagleView/
├── backend/app/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Settings via pydantic-settings
│   ├── db.py, models.py, schemas.py     # SQLAlchemy ORM (legacy, metadata now in Snowflake)
│   ├── security.py                      # JWT auth
│   ├── routers/
│   │   ├── auth.py                      # Google OAuth + demo login
│   │   ├── datasets.py                  # Upload, analyze, confirm, list, delete — imports sf_lib
│   │   └── query.py                     # POST /api/query — imports sf_lib
│   └── services/
│       ├── snowpark_service.py          # ACTIVE: Snowpark session management, adds sf_lib to sys.path
│       ├── catalog_service.py           # DEAD CODE (sf_lib version used)
│       ├── classification_service.py    # DEAD CODE (Gemini-based)
│       ├── sql_generation_service.py    # DEAD CODE (Gemini-based)
│       ├── gemini_client.py             # DEAD CODE
│       └── ...                          # Other legacy service files
├── snowflake_app/
│   ├── streamlit_app.py                 # Streamlit-in-Snowflake app (onboarding + dashboard)
│   ├── setup_domain_agents.py           # Creates Cortex Agents, stored procs, tools
│   ├── setup_agent.sql                  # Agent DDL
│   ├── setup_rbac.sql                   # RBAC DDL
│   ├── deploy.py                        # Deployment script
│   └── sf_lib/                          # THE ACTIVE CODEBASE — all routers import from here
│       ├── cortex.py                    # CortexAgent: SNOWFLAKE.CORTEX.COMPLETE wrapper
│       ├── domain_agent.py              # Real Cortex Agent runtime (DATA_AGENT_RUN)
│       ├── domain_agents.py             # Registry: 7 agents with table_name, concepts, types
│       ├── orchestrator.py              # Multi-domain column splitter
│       ├── classification.py            # Per-domain schema classifier (Cortex COMPLETE)
│       ├── ingestion.py                 # File parsing: CSV/Excel/JSON → DataFrame
│       ├── ingestion_pipeline.py        # 3-stage: upload → analyze → confirm
│       ├── ingestion_agent.py           # Cortex Agent for table creation
│       ├── schema_service.py            # Column building, type casting, MERGE upsert
│       ├── metadata.py                  # All metadata CRUD (Snowflake tables)
│       ├── catalog_service.py           # Builds LLM-readable catalog with relationships
│       ├── query_pipeline.py            # Full Q&A orchestration with parallel agent dispatch
│       ├── query_understanding.py       # Intent classification: analytics/entity/clarification
│       ├── sql_validator.py             # Read-only SQL validation + table scoping
│       ├── result_interpretation.py     # Raw rows → natural language answer
│       ├── conversation.py              # Chat history persistence
│       ├── rbac.py                      # Username → schema mapping
│       ├── naming.py                    # safe_identifier, user_schema_name
│       ├── activity_log.py              # Agent activity logging
│       └── demo_seed.py                 # Demo data seeder
├── mcp_server/
│   └── server.py                        # MCP proxy: upload_data + ask_question tools
├── frontend/src/
│   ├── lib/api.ts                       # API client (all backend endpoints)
│   ├── lib/types.ts                     # TypeScript types (multi-domain aware)
│   ├── pages/OnboardingPage.tsx         # Upload + multi-domain schema review (tabbed UI)
│   ├── pages/DashboardPage.tsx          # Chat interface with domain sidebar
│   ├── components/ResultView.tsx        # Answer + charts + timeline + data table
│   └── components/SchemaMappingTable.tsx # Per-domain editable column grid
└── docs/                                # Architecture diagrams + query flow docs
```

## Architecture Deep Dive

### 1. Data Ingestion Pipeline (3-stage)

**Stage 1 — Upload** (`sf_lib/ingestion.py`):
- `parse_upload_to_dataframe()`: routes by extension (CSV/Excel/JSON), 25 MB limit, strips whitespace from column names.

**Stage 2 — Analyze** (`sf_lib/ingestion_pipeline.py:29`):
- Orchestrator Agent (`sf_lib/orchestrator.py:62`) splits file columns across multiple domains via Cortex COMPLETE. Force-propagates all `*_ID` columns to every domain for join-key coverage.
- Per-domain classifier (`sf_lib/classification.py:86`) proposes column schemas, seeing existing table schema. Uses `isNewColumn` flag to reuse existing columns.
- Creates metadata rows: `APP_DATASET_DOMAINS` + `APP_DATASET_COLUMNS`.

**Stage 3 — Confirm** (`sf_lib/ingestion_pipeline.py:82`):
- Per domain: casts DataFrame → real Cortex Agent calls `MergeDomainTable` to CREATE/ALTER TABLE → MERGE-based upsert via staging table (`sf_lib/schema_service.py:117`) → detect cross-domain relationships.

### 2. Domain Agents (7 domains)

| Agent Key | Label | Table Name |
|-----------|-------|------------|
| `inventory_agent` | Inventory Agent | `INVENTORY_DATA` |
| `customer_agent` | Customer Agent | `CUSTOMER_DATA` |
| `financial_agent` | Financial Agent | `FINANCIAL_DATA` |
| `order_agent` | Order Agent | `ORDER_DATA` |
| `delivery_agent` | Delivery Agent | `DELIVERY_DATA` |
| `product_agent` | Product Agent | `PRODUCT_DATA` |
| `supplier_agent` | Supplier Agent | `SUPPLIER_DATA` |

**Two-tier agent architecture** (`setup_domain_agents.py`):
- Primary agents have 3 tools: `MergeDomainTable`, `RunDomainQuery`, `AskAnotherAgent`
- Sub-agents (e.g. `INVENTORY_AGENT_SUB`) have only `RunDomainQuery` — no `AskAnotherAgent`, preventing infinite recursion (depth capped at 1 hop)

### 3. Query Pipeline (`sf_lib/query_pipeline.py`)

1. Build dataset catalog with table schemas + discovered relationships
2. Query Understanding Agent classifies intent: `analytics` | `entity_investigation` | `clarification`
3. Resolve relevant tables → agent keys (fuzzy table-name matching)
4. Dispatch: `entity_investigation` → all relevant agents in parallel (ThreadPoolExecutor); `analytics` → single agent (can use `AskAnotherAgent` for cross-domain)
5. SQL validation per agent (`sf_lib/sql_validator.py`) — read-only, scoped to user's tables
6. Result Interpretation Agent → structured answer with timeline, summary, visualization hints

### 4. SQL Validation (`sf_lib/sql_validator.py`)

- Single statement only (no semicolons)
- SELECT/WITH only (16 forbidden keywords: DROP, DELETE, TRUNCATE, UPDATE, INSERT, ALTER, MERGE, CREATE, GRANT, REVOKE, CALL, COPY, PUT, GET, EXECUTE, UNLOAD)
- 3-part qualified name enforcement (database.schema.table scoping)
- Comment stripping before validation
- Defense-in-depth: `RUN_SELECT_PROC` independently validates inside the stored procedure

### 5. Relationship Discovery (`sf_lib/schema_service.py:176`)

- After each domain's data is loaded, scans FK candidates (columns ending in `_ID` or flagged as FK)
- For each FK column, runs `DESCRIBE TABLE` on every other READY domain
- Exact column name match → confidence 0.9
- Relationships rendered in the catalog as join paths for LLM context

### 6. MCP Server (`mcp_server/server.py`)

Pure proxy — 2 tools:
- `upload_data(filename, content_base64)`: validates → uploads → analyzes → auto-confirms (skips human review)
- `ask_question(question, session_id)`: validates → forwards to `/api/query`

Auth via `EGLEVIEW_API_TOKEN` env var (JWT). No direct Snowflake access.

### 7. Metadata Tables (in user's schema)

| Table | Purpose |
|-------|---------|
| `APP_DATASETS` | Upload tracking: ID, name, filename, status, row count |
| `APP_DATASET_DOMAINS` | Per-domain slice: agent key, table name, classification JSON |
| `APP_DATASET_COLUMNS` | Per-column mapping: source/target names, types, PK/FK, include, isNewColumn |
| `APP_RELATIONSHIPS` | Cross-domain joins: source/target agent keys + columns, confidence |
| `APP_CONVERSATIONS` | Chat history |

### 8. Frontend Architecture

**Onboarding** (`OnboardingPage.tsx`): State machine (idle → uploading → analyzing → review → confirming → success). Multi-domain aware: tabbed UI per domain, editable `SchemaMappingTable` per tab, per-domain confirm payloads.

**Dashboard** (`DashboardPage.tsx`): Chat interface. Sidebar shows loaded domains with row counts. Responses rendered via `ResultView`: answer text, agents consulted, entity info, summary KPIs, Recharts visualizations (bar/line/pie/kpi), timeline, data table, missing info.

**API types** (`types.ts`): `AnalyzeResponse.domains: DomainResult[]`, `DomainColumn` with `is_new_column`, `QueryResponse` with `agents_consulted[]`, `agent_log[]`, `visualization`, `timeline[]`.

## Key Design Decisions

1. **Multi-domain orchestration**: A single uploaded file can span multiple business domains. The orchestrator splits columns, and each domain agent independently manages its own table.
2. **Schema evolution**: Domain classifiers see existing table schemas and reuse columns via `isNewColumn`, allowing incremental extension of tables across multiple uploads.
3. **MERGE upserts**: When a PK exists, data is upserted (not appended), preventing duplicates on re-upload.
4. **Two-tier agent recursion prevention**: Sub-agents lack `AskAnotherAgent`, structurally capping cross-domain delegation at 1 hop.
5. **Parallel agent dispatch**: Entity investigations query multiple domain agents concurrently via ThreadPoolExecutor with independent Snowpark sessions.
6. **Defense-in-depth SQL validation**: Both application-level validator and stored procedure validate SQL independently.
