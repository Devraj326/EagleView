"""Split the architecture diagram into 5 smaller PlantUML diagrams and render each as PNG."""

import subprocess
from pathlib import Path

OUT_DIR = Path(r"C:\Users\anujs\Downloads\Demo Data\SF_hackathon\EagleView\docs\diagrams")
PLANTUML_JAR = Path(r"C:\Users\anujs\Downloads\Demo Data\plantuml.jar")

SKIN = """
skinparam backgroundColor #FFFFFF
skinparam shadowing true
skinparam defaultFontName Arial
skinparam ParticipantPadding 20
skinparam BoxPadding 14
skinparam sequence {
  ArrowColor #2F80ED
  ActorBorderColor #5B9BD5
  ActorBackgroundColor #EAF3FF
  ParticipantBorderColor #8AA9C7
  ParticipantBackgroundColor #F5F9FE
  LifeLineBorderColor #B9D3EA
  LifeLineBackgroundColor #F9FCFF
  GroupBorderColor #6B6B6B
  GroupBackgroundColor #FFFFFF
  ReferenceBackgroundColor #FFF8DC
  ReferenceBorderColor #C8B458
  DividerBackgroundColor #FFFFFF
  DividerBorderColor #666666
}
"""

diagrams = {}

# ── 1. DATA INGESTION ──────────────────────────────────────────────
diagrams["01_data_ingestion"] = f"""@startuml
title EagleView — Part 1: Data Ingestion & Supply Chain Onboarding
caption Upload → Orchestrator → Classify → Review → MERGE Upsert
{SKIN}

actor "Business User" as user
participant "React Frontend\\n(Vercel)" as ui
participant "FastAPI Backend\\n(Render)" as api
participant "Snowpark Bridge\\nsf_lib pipeline" as bridge
database "Snowflake\\nEGLE_VIEW" as sf
participant "Cortex COMPLETE\\n(llama3.1-70b)" as cortex
participant "12 Domain\\nCortex Agents" as agents

user -> ui : Upload supply chain CSV\\n(ERP, logistics, supplier, IoT)
ui -> api : POST /api/datasets/upload
api -> bridge : ready_context(user)
bridge -> sf : Create user schema\\nEnsure APP_* metadata tables
api -> api : Parse CSV/Excel/JSON → DataFrame\\n(25 MB limit, column sanitization)
api -> sf : Create APP_DATASETS row\\nstatus = UPLOADED
api --> ui : Upload accepted (dataset_id)

ui -> api : POST /api/datasets/{{id}}/analyze
api -> cortex : **Orchestrator Agent**\\nSplit columns across domains

note right of cortex
  Analyzes column names + sample rows
  Routes to relevant domain agents
  Force-propagates _ID columns to
  all domains for join-key coverage
end note

cortex --> api : Domain assignments\\n(e.g. SUPPLIER + ORDER + DELIVERY)

loop Each assigned domain slice
  api -> sf : DESCRIBE TABLE (existing domain schema)
  api -> cortex : **Per-Domain Classifier**\\nProposes column mapping + types\\nSees existing columns (isNewColumn flag)
  cortex --> api : Proposed mapping + confidence
  api -> sf : Save APP_DATASET_DOMAINS\\nand APP_DATASET_COLUMNS
end

api -> sf : Mark dataset SCHEMA_PROPOSED
api --> ui : Domain mappings + agent notes

note over ui
  **Tabbed Schema Review UI**
  One tab per domain agent
  Editable: column names, types,
  nullable, include/exclude
  Shows: confidence scores,
  data quality issues, agent notes
end note

user -> ui : Review mappings per domain tab\\nEdit types, rename columns
ui -> api : POST /api/datasets/{{id}}/confirm\\n{{domains: [{{domain_id, columns}}]}}

loop Each confirmed domain
  api -> agents : **MergeDomainTable** tool call\\n(CREATE or ALTER TABLE ADD COLUMN)
  agents -> sf : Execute DDL via MERGE_TABLE_PROC
  sf --> agents : Table ready
  api -> sf : **MERGE-based upsert**\\n(staging table → MERGE INTO → drop staging)\\nPK dedup, no duplicates on re-upload
  sf --> api : Loaded row count
  api -> sf : **Detect relationships**\\nScan _ID columns across READY domains\\nExact name match → confidence 0.9
end

api -> sf : Mark dataset READY
api --> ui : All domains loaded + discovered relationships

note over sf
  **11 Base Tables (81K+ rows)**
  SUPPLIER · PLANT · PARTS · PO · ORDER
  DELIVERY · CUSTOMER · PRODUCT · FINANCIAL
  INBOUND_SHIPMENT · INVENTORY_SNAPSHOT

  **5 Dynamic Tables (TARGET_LAG = 1 hour)**
  SC_OTD_METRICS · SC_FILL_RATE
  SC_INVENTORY_POSITION · SC_LANDED_COST
  SC_SUPPLIER_SCORECARD
end note

@enduml"""

# ── 2. GOVERNED ANALYTICS ──────────────────────────────────────────
diagrams["02_governed_analytics"] = f"""@startuml
title EagleView — Part 2: Governed Analytics (Cortex Analyst Path)
caption Metric questions → Semantic View → Verified Query → Same answer every time
{SKIN}

actor "Business User\\n(Planning / Procurement\\n/ Logistics)" as user
participant "React Frontend\\n(Vercel)" as ui
participant "FastAPI Backend\\n(Render)" as api
database "Snowflake\\nEGLE_VIEW" as sf
participant "Cortex Analyst\\nSemantic View" as analyst

user -> ui : "What is the on-time delivery % by carrier?"
ui -> api : POST /api/query\\n{{question, session_id, persona: "Procurement"}}
api -> api : **Keyword detection**\\nMatches "on-time delivery" → governed path

api -> analyst : **CORTEX.ANALYST_RUN()**\\nSemantic View: SC_SUPPLY_CHAIN\\nPersona hint: "Procurement perspective"

note right of analyst
  **Semantic View: SC_SUPPLY_CHAIN**
  8 entity tables, 9 relationships
  9 verified queries with canonical SQL

  Canonical Metrics:
  · OTD% = delivered_on_time / total × 100
  · Fill Rate = shipped / requested × 100
  · DOI = qty_on_hand / avg_daily_usage
  · Landed Cost = unit + freight + duty + insurance

  → Same SQL every time,
    regardless of persona
end note

analyst -> sf : Execute verified query SQL\\n(deterministic, governed)
sf --> analyst : Query results
analyst --> api : SQL used + rows + answer text

api -> sf : Save response in APP_CONVERSATIONS
api --> ui : {{answer, result rows, sql,\\nagents_consulted: ["cortex_analyst"],\\nsummary: {{governed_by: "SC_SUPPLY_CHAIN",\\npersona: "Procurement"}}}}

ui --> user : **Governed Answer**\\nOTD% by carrier table + bar chart\\n"Routed via: cortex_analyst (semantic view)"

@enduml"""

# ── 3. EXPLORATORY ANALYTICS ──────────────────────────────────────
diagrams["03_exploratory_analytics"] = f"""@startuml
title EagleView — Part 3: Exploratory Analytics (Domain Agent Path)
caption Ad-hoc questions → Domain Agents → Freestyle SQL → SQL Validation
{SKIN}

actor "Business User" as user
participant "React Frontend\\n(Vercel)" as ui
participant "FastAPI Backend\\n(Render)" as api
database "Snowflake\\nEGLE_VIEW" as sf
participant "Cortex COMPLETE\\n(llama3.1-70b)" as cortex
participant "12 Domain\\nCortex Agents" as agents
participant "SQL Validator\\nDefense-in-Depth" as validator

user -> ui : "Tell me about order ORD100775"
ui -> api : POST /api/query\\n{{question, session_id}}
api -> cortex : **Query Understanding Agent**\\nClassify intent + entity + relevant tables
cortex --> api : intent=entity_investigation\\nentityId=ORD100775\\nrelevantTables=[ORDER_DATA, DELIVERY_DATA]

api -> api : Resolve tables → agent keys\\n[order_agent, delivery_agent]

par Parallel dispatch (ThreadPoolExecutor)
  api -> agents : **ORDER_AGENT**\\nDATA_AGENT_RUN()\\n"Look up ORD100775 in your table"
  agents -> sf : **RunDomainQuery** tool\\nAgent writes its own SELECT SQL
  sf --> agents : Order details rows
  agents --> api : SQL + rows

  api -> agents : **DELIVERY_AGENT**\\nDATA_AGENT_RUN()\\n"Look up delivery for ORD100775"
  agents -> sf : **RunDomainQuery** tool
  sf --> agents : Delivery status rows
  agents --> api : SQL + rows
end

api -> validator : Validate each agent's SQL
validator -> validator : Single statement check\\nSELECT/WITH only (16 forbidden keywords)\\n3-part name scoping (db.schema.table)\\nComment stripping

note right of validator
  **Defense-in-Depth**
  App-level: sql_validator.py
  Proc-level: RUN_SELECT_PROC
  independently validates
end note

validator --> api : Approved SQL + rows

api -> cortex : **Result Interpretation Agent**\\nCombine multi-agent results into\\nnatural language answer
cortex --> api : {{answer, timeline, summary, missingInfo}}

api -> sf : Save answer + SQL in APP_CONVERSATIONS
api --> ui : Unified response with\\ntimeline + charts + entity badge
ui --> user : Rich answer:\\n"ORD100775 was placed Apr 17, total $101K,\\ncurrently Returned status"

note over agents
  **Two-Tier Agent Architecture (24 total)**
  12 Primary agents: MergeDomainTable + RunDomainQuery + AskAnotherAgent
  12 Sub agents (_SUB): RunDomainQuery only — NO AskAnotherAgent
  → Recursion structurally impossible (1-hop max by construction)
end note

@enduml"""

# ── 4. PERSONA CONSISTENCY + KPI DASHBOARD ────────────────────────
diagrams["04_persona_kpi"] = f"""@startuml
title EagleView — Part 4: Persona Consistency Proof & KPI Dashboard
caption Same metric → Same answer across Planning, Procurement, Logistics
{SKIN}

actor "Business User\\n(Planning / Procurement\\n/ Logistics)" as user
participant "React Frontend\\n(Vercel)" as ui
participant "FastAPI Backend\\n(Render)" as api
database "Snowflake\\nEGLE_VIEW" as sf
participant "Cortex Analyst\\nSemantic View" as analyst

== Persona Consistency Proof ==

user -> ui : **SC Command Center** page\\nRun consistency test
ui -> api : Same question × 3 personas

par Planning, Procurement, Logistics
  api -> analyst : "What is overall OTD%" (Planning)
  analyst --> api : 78.87%
  api -> analyst : "What is overall OTD%" (Procurement)
  analyst --> api : 78.87%
  api -> analyst : "What is overall OTD%" (Logistics)
  analyst --> api : 78.87%
end

api --> ui : 3 identical results side-by-side
ui --> user : **"All 3 personas returned SAME answer.\\nGoverned consistency confirmed."**

== Supply Chain KPI Dashboard ==

user -> ui : Open SC Command Center
ui -> sf : Query 4 dynamic tables directly

note over sf
  **Live KPI Ribbon**
  OTD% = 78.87% (SC_OTD_METRICS)
  Fill Rate = 92.10% (SC_FILL_RATE)
  DOI = 3.3 days (SC_INVENTORY_POSITION)
  Landed Cost = ₹2,837 (SC_LANDED_COST)

  Auto-refresh via TARGET_LAG = 1 hour
  New data → dynamic tables update → KPIs update
end note

sf --> ui : KPI values
ui --> user : 4 metric cards + governed chat + persona selector

@enduml"""

# ── 5. AUTH + MCP + STREAMLIT + COCO ──────────────────────────────
diagrams["05_auth_mcp_coco"] = f"""@startuml
title EagleView — Part 5: Auth, MCP, Streamlit & CoCo
caption RBAC isolation, MCP integration, Streamlit app, CoCo usage
{SKIN}

actor "Business User" as user
participant "React Frontend\\n(Vercel)" as ui
participant "FastAPI Backend\\n(Render)" as api
participant "Snowpark Bridge\\nsf_lib pipeline" as bridge
database "Snowflake\\nEGLE_VIEW" as sf
participant "Cortex Analyst\\nSemantic View" as analyst
participant "12 Domain\\nCortex Agents" as agents

== Authentication & RBAC Isolation ==

user -> ui : Google sign-in or demo login
ui -> api : POST /api/auth/google or /demo
api --> ui : Application JWT
ui -> api : Bearer JWT on every request
api -> bridge : Resolve user → schema mapping
bridge -> sf : All queries scoped to\\nuser's own schema (DEMO_A / DEMO_B)

note over sf
  **Per-user schema isolation**
  Each user's data, metadata, and
  domain tables live in their own schema.
  EXECUTE AS CALLER for Streamlit.
  SQL validator enforces db/schema/table scope.
end note

== MCP Server (External Tool Integration) ==

participant "MCP Client\\n(Claude, CoCo, etc.)" as mcp

mcp -> api : **upload_data** tool\\n(filename, content_base64)
api -> bridge : Full pipeline:\\nupload → analyze → auto-confirm
bridge -> sf : Data loaded via agents
api --> mcp : Upload result

mcp -> api : **ask_question** tool\\n(question, session_id)
api -> api : Dual-path routing\\n(governed or exploratory)
api --> mcp : Answer + SQL + agents_consulted

== Snowflake-Native Streamlit App ==

participant "Streamlit-in-Snowflake\\n3 Pages" as streamlit

streamlit -> sf : **Page 1: Onboard Data**\\nUpload → Orchestrator → Review → Confirm
streamlit -> sf : **Page 2: Dashboard**\\nChat interface with domain agents
streamlit -> sf : **Page 3: SC Command Center**\\nKPI ribbon + persona selector\\n+ governed chat + consistency proof
streamlit -> analyst : Metric questions → Cortex Analyst
streamlit -> agents : Ad-hoc questions → Domain Agents

== Built with CoCo ==

note over ui, agents
  **Built Entirely with Snowflake CoCo (Desktop)**
  Planning: Architecture analysis, gap identification, ontology design
  Development: Data gen, semantic views, dynamic tables, agents, pipeline code
  Execution: SQL execution, data loading, sv-deploy, agent creation
  Testing: Metric verification, agent testing, persona consistency proof

  **Reusable CoCo Skills**
  eagleview (243 lines) — full architecture context
  sc-metrics (113 lines) — canonical metric definitions (shareable)

  **CoCo Tools Used**
  sql_execute · cortex agent-studio sv-deploy · Task subagents
  Plan mode · Git integration · Chart visualization
end note

legend right
  |= Convention |= Meaning |
  | Blue solid arrow | Request or command |
  | Dashed arrow | Response or data |
  | Yellow note | Architecture boundary |
  | par block | Parallel execution |
  |= Surface |= URL |
  | React Frontend | eagle-view-ten.vercel.app |
  | FastAPI Backend | Render (auto-deploy) |
  | Streamlit App | EGLE_VIEW.PUBLIC.DATAMIND |
  | GitHub | github.com/Devraj326/EagleView |
endlegend

@enduml"""

# ── Write and render all ──────────────────────────────────────────
for name, puml_content in diagrams.items():
    puml_path = OUT_DIR / f"{name}.puml"
    puml_path.write_text(puml_content, encoding="utf-8")
    print(f"Written: {puml_path.name}")

    result = subprocess.run(
        ["java", "-jar", str(PLANTUML_JAR), "-tpng", str(puml_path), "-o", str(OUT_DIR)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        png_path = OUT_DIR / f"{name}.png"
        if png_path.exists():
            size_kb = png_path.stat().st_size / 1024
            print(f"  -> {png_path.name} ({size_kb:.0f} KB)")
        else:
            # PlantUML may capitalize the name
            for f in OUT_DIR.glob(f"{name}*.png"):
                size_kb = f.stat().st_size / 1024
                print(f"  -> {f.name} ({size_kb:.0f} KB)")
    else:
        print(f"  ERROR: {result.stderr}")

print("\nDone! All 5 diagrams rendered.")
