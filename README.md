# EagleView — AI-Powered Supply Chain Intelligence Platform

> **Governed ontology + multi-agent analytics on Snowflake, built entirely with CoCo**

Supply chain data is scattered across ERP, logistics, supplier, and IoT systems with inconsistent definitions. The same question — *"What is our on-time delivery rate?"* — yields different answers across teams because each team queries different tables with different logic.

EagleView solves this by combining **runtime flexibility** (any file, any domain, auto-discovered relationships) with **governed consistency** (semantic views, verified queries, Cortex Analyst) — so every team gets one trustworthy answer.

---

## Hackathon Problem Statement

> Build an industry ontology — a business entity and relationship model (Supplier → Part → Plant → Shipment → Order → Customer) — expressed as governed semantic views, so that a natural-language layer returns consistent, trustworthy answers grounded in shared definitions and metrics.

### What EagleView Delivers

| Requirement | How We Address It |
|---|---|
| **Define the ontology** | Formal ER model: Supplier → Part → Plant → Purchase Order → Inbound Shipment → Order → Delivery → Customer |
| **Encode as semantic views** | `SC_SUPPLY_CHAIN` semantic view with 9 verified queries for canonical metrics |
| **Governed conversational analytics** | Cortex Analyst routes metric questions through the semantic view — same SQL every time |
| **Cross-domain questions, one answer** | 12 domain agents collaborate via `AskAnotherAgent` (1-hop max) |
| **Same metric across personas** | Built-in consistency proof: Planning, Procurement, Logistics all get identical results |

---

## Architecture

### High-Level Overview

![EagleView Architecture](docs/diagrams/eagleview_sc_architecture.png)

<details>
<summary>Text version (click to expand)</summary>

```
┌─────────────────────────────────────────────────────────────────┐
│  DATA SOURCES: ERP, Logistics, Supplier DBs, IoT, Spreadsheets │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  INGESTION LAYER (CoCo-built)                                   │
│  File Upload → Orchestrator LLM (Cortex COMPLETE)               │
│  → Splits columns across domains → Per-domain classification    │
│  → Human-in-the-loop schema review → MERGE upsert into tables   │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  SNOWFLAKE DATA LAYER                                           │
│                                                                 │
│  Base Tables (11)              Dynamic Tables (5)               │
│  SUPPLIER · PLANT · PARTS      SC_OTD_METRICS                  │
│  PO · ORDER · DELIVERY         SC_FILL_RATE                    │
│  CUSTOMER · PRODUCT             SC_INVENTORY_POSITION           │
│  FINANCIAL · INBOUND_SHIPMENT   SC_LANDED_COST                 │
│  INVENTORY_SNAPSHOT             SC_SUPPLIER_SCORECARD           │
│                                                                 │
│  Semantic View: SC_SUPPLY_CHAIN                                 │
│  → 8 entity tables, 9 relationships, 9 verified queries        │
│  → Canonical metrics: OTD%, Fill Rate, DOI, Landed Cost         │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  DUAL-PATH QUERY LAYER                                          │
│                                                                 │
│  GOVERNED PATH              │  EXPLORATORY PATH                 │
│  Metric questions           │  Ad-hoc questions                 │
│  → Cortex Analyst           │  → 12 Cortex Agents               │
│  → Semantic View            │  → Agents write their own SQL     │
│  → Verified Queries         │  → AskAnotherAgent (1-hop max)    │
│  → SAME answer every time   │  → SQL validation (defense-in-    │
│                             │    depth)                         │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                             │
│  React (Vercel) · Streamlit (Snowflake) · MCP Server            │
│  Persona Selector: Planning / Procurement / Logistics           │
└─────────────────────────────────────────────────────────────────┘
```

</details>

---

## Supply Chain Ontology

### Entity-Relationship Model

```
Supplier ──1:N──▸ Part ──N:M──▸ Plant (via Inventory)
    │                │
    │              1:N
    ▼                ▼
Purchase Order ──▸ Inbound Shipment ──▸ Plant
    │
    ▼
  Order ──1:1──▸ Delivery ──▸ Customer
    │
    ▼
  Payment
```

### Canonical Metrics (locked in verified queries)

| Metric | Formula | Live Value |
|---|---|---|
| **On-Time Delivery %** | `delivered_on_time / total_delivered × 100` | 78.87% |
| **Fill Rate %** | `shipped_qty / requested_qty × 100` | 92.10% |
| **Days of Inventory** | `qty_on_hand / avg_daily_usage` | 3.3 days |
| **Landed Cost** | `unit_cost + freight + duty + insurance` | ₹2,837/unit |
| **Supplier Reliability (OTIF)** | `on_time_and_full_POs / total_POs × 100` | Per supplier |

### 12 Domain Agents (Cortex Agents)

| Agent | Table | Domain |
|---|---|---|
| `inventory_agent` | INVENTORY_DATA | Stock levels, warehouse |
| `customer_agent` | CUSTOMER_DATA | Customer profiles, segments |
| `financial_agent` | FINANCIAL_DATA | Payments, transactions |
| `order_agent` | ORDER_DATA | Sales orders, fulfillment |
| `delivery_agent` | DELIVERY_DATA | Outbound logistics |
| `product_agent` | PRODUCT_DATA | Product catalog |
| `supplier_agent` | SUPPLIER_DATA | Supplier profiles, contracts |
| `plant_agent` | PLANT_DATA | Plants, DCs, warehouses |
| `parts_agent` | PARTS_DATA | Parts, BOM, components |
| `purchase_order_agent` | PURCHASE_ORDER_DATA | Procurement, POs |
| `inbound_shipment_agent` | INBOUND_SHIPMENT_DATA | Inbound freight |
| `inventory_snapshot_agent` | INVENTORY_SNAPSHOT_DATA | Inventory positions |

Each agent is a **real Cortex Agent object** created via `SNOWFLAKE.CORTEX.DATA_AGENT_RUN()` with 3 tools:
- **MergeDomainTable** — CREATE or ALTER TABLE via stored procedure
- **RunDomainQuery** — Execute read-only SELECT queries
- **AskAnotherAgent** — Cross-domain delegation (1-hop max via sub-agent architecture)

---

## CoCo Usage — Full Lifecycle

EagleView was built **entirely with Snowflake CoCo** (Cortex Code) across every phase:

### Planning
- Codebase architecture analysis and gap identification
- Entity-relationship model design
- Implementation plan with judging criteria alignment

### Development
- Synthetic data generation (11 CSVs, 81K+ rows, referentially consistent)
- Semantic view YAML authoring (607 lines, 9 verified queries)
- Dynamic table SQL creation (5 auto-refreshing metric tables)
- Domain agent setup (24 Cortex Agents via `create_all_agents.py`)
- Query pipeline update: Cortex Analyst governed path integration
- Streamlit SC Command Center page with KPI ribbon and persona proof
- Frontend persona selector and supply-chain-focused suggestions

### Execution
- SQL execution against Snowflake (DDL, COPY INTO, queries)
- Data loading via PUT + COPY INTO (11 tables)
- Semantic view deployment via `cortex agent-studio sv-deploy`
- Git commit and push to GitHub (auto-triggers Render + Vercel deploys)

### Testing
- Canonical metric verification (all 4 KPIs returning expected values)
- Cortex Agent response testing (ORDER_AGENT writes and executes own SQL)
- Persona consistency proof (same metric → same answer across 3 personas)

### Reusable CoCo Skills
| Skill | Lines | Purpose |
|---|---|---|
| `eagleview` | 243 | Full architecture context — any CoCo session instantly knows the codebase |
| `sc-metrics` | 113 | Canonical supply chain metric definitions — shareable across teams |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Snowflake Cortex COMPLETE (llama3.1-70b) |
| **Agents** | 24 Cortex Agents (12 primary + 12 sub) via `DATA_AGENT_RUN()` |
| **Governed Analytics** | Cortex Analyst + Semantic View with Verified Queries |
| **Derived Metrics** | 5 Dynamic Tables (`TARGET_LAG = '1 hour'`) |
| **Data Loading** | MERGE-based upserts with PK deduplication |
| **Backend** | FastAPI (Python) on Render |
| **Frontend** | React + TypeScript + Recharts on Vercel |
| **Streamlit** | Streamlit-in-Snowflake (3 pages) |
| **MCP** | MCP server with 2 tools (upload_data, ask_question) |
| **RBAC** | Per-user schema isolation, EXECUTE AS CALLER |

---

## Key Innovation: Dual-Path Architecture

Most solutions offer either governed analytics OR flexible exploration. EagleView offers **both**:

**Governed Path** — When a user asks about a canonical supply chain metric (OTD%, fill rate, DOI, landed cost), the query routes through **Cortex Analyst** against the **semantic view**. The verified query produces the **same SQL every time**, regardless of who asks or which persona they select.

**Exploratory Path** — When a user asks an ad-hoc question ("Tell me about order ORD100775"), the query routes through **domain agents** that write their own SQL, can delegate to other agents via `AskAnotherAgent`, and return flexible, contextual answers.

**Runtime Relationship Discovery** — When users upload new data, the orchestrator discovers relationships at runtime by matching FK/PK columns across domains. This means any new data source can be onboarded without changing the ontology.

This combination of governed consistency + runtime flexibility is EagleView's core value proposition.

---

## How It Works

### 1. Data Onboarding
Upload a CSV, Excel, or JSON file. The **Orchestrator Agent** (Cortex COMPLETE) analyzes the columns and splits them across the relevant domain agents. Each agent proposes a schema — seeing its existing table structure to reuse columns when possible. A human reviews and confirms. Data is loaded via MERGE-based upserts (no duplicates on re-upload).

### 2. Supply Chain Command Center
The SC Command Center page shows **live KPIs** from dynamic tables (OTD%, fill rate, DOI, landed cost). Users select a **persona** (Planning, Procurement, Logistics) and ask questions in natural language. Metric questions route through Cortex Analyst for governed answers.

### 3. Persona Consistency Proof
A built-in test fires the same metric question across all 3 personas and displays results side-by-side. All return identical values, proving the semantic view delivers consistent answers regardless of who asks.

### 4. Ad-hoc Exploration
The Dashboard page allows free-form questions. Domain agents write and execute their own SQL, can delegate across domains, and return rich answers with charts, timelines, and entity details.

---

## Repository Structure

```
EagleView/
├── .cortex/skills/
│   ├── eagleview/SKILL.md          Full architecture CoCo skill (243 lines)
│   └── sc-metrics/SKILL.md         Reusable metric definitions skill (113 lines)
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI entry point
│   │   ├── routers/                API endpoints (auth, datasets, query)
│   │   └── services/               snowpark_service.py (active), others (legacy)
│   └── demo_data/                  Supply chain CSVs (11 files)
├── frontend/
│   └── src/
│       ├── pages/                  DashboardPage (persona selector), OnboardingPage
│       ├── components/             ResultView, SchemaMappingTable, charts
│       └── lib/                    API client, TypeScript types
├── snowflake_app/
│   ├── sf_lib/                     THE ACTIVE CODEBASE
│   │   ├── domain_agents.py        12 agent registry with table names
│   │   ├── query_pipeline.py       Dual-path: Cortex Analyst + domain agents
│   │   ├── ingestion_pipeline.py   3-stage: upload → analyze → confirm
│   │   ├── orchestrator.py         Multi-domain column splitter
│   │   ├── classification.py       Per-domain schema classifier
│   │   ├── schema_service.py       MERGE upsert + relationship detection
│   │   ├── sql_validator.py        Read-only SQL validation
│   │   └── ...                     metadata, catalog, conversation, RBAC
│   ├── ontology/
│   │   └── sc_supply_chain.sv.yaml Semantic view YAML (607 lines)
│   ├── streamlit_app.py            3-page app (Onboard, Dashboard, SC Command Center)
│   ├── setup_domain_agents.py      Stored procs + agent DDL
│   ├── setup_dynamic_tables.py     5 dynamic tables
│   ├── setup_semantic_view.py      Semantic view deployment
│   ├── generate_sc_data.py         Synthetic data generator
│   ├── create_all_agents.py        Batch agent creation
│   └── demo_data/                  Supply chain CSVs (11 files)
├── mcp_server/
│   └── server.py                   MCP proxy (upload_data, ask_question)
└── docs/                           Architecture diagrams, query flow docs
```

---

## Deployment

| Surface | URL / Location | Auto-deploys from |
|---|---|---|
| **Frontend** | https://eagle-view-ten.vercel.app/ | GitHub push |
| **Backend** | Render (see `render.yaml`) | GitHub push |
| **Streamlit** | `EGLE_VIEW.PUBLIC.DATAMIND` | `deploy.py` script |
| **Snowflake Objects** | `EGLE_VIEW.DEMO_A` (tables, dynamic tables, semantic view) | Setup scripts |
| **Cortex Agents** | `EGLE_VIEW.PUBLIC` (24 agents) | `create_all_agents.py` |

### Setup Order
```bash
# 1. Generate synthetic supply chain data
python snowflake_app/generate_sc_data.py

# 2. Create stored procedures and all 24 Cortex Agents
python snowflake_app/create_all_agents.py

# 3. Load data into Snowflake tables
python snowflake_app/load_data.py

# 4. Create dynamic tables for derived metrics
python snowflake_app/setup_dynamic_tables.py DEMO_A

# 5. Deploy semantic view
python snowflake_app/setup_semantic_view.py DEMO_A

# 6. Deploy Streamlit app
python snowflake_app/deploy.py
```

---

## License

No license file is currently included in the repository.
