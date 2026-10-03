# EgleView × CoCo — Hackathon Implementation Plan

This is an analysis of the **existing** EgleView codebase and Snowflake architecture — nothing
here was rewritten to produce this plan. It documents what's actually built, what's actually
verified live, and what's genuinely still a gap, so it can stand as planning evidence without
overstating anything.

## 1. Data sources

- **Ingestion input**: structured/semi-structured file uploads only — CSV, Excel (`.xlsx`/`.xls`),
  JSON (`snowflake_app/sf_lib/ingestion.py`, `MAX_UPLOAD_MB = 25`). No unstructured document
  (PDF/image) ingestion exists — a real, acknowledged gap, not a hidden one.
- **Query input**: free-text natural-language questions (`DashboardPage.tsx` → `/api/query`).
- **Output data**: one persistent Snowflake table per domain (`CUSTOMER_DATA`, `ORDER_DATA`,
  `FINANCIAL_DATA`, `DELIVERY_DATA`, `PRODUCT_DATA`, `INVENTORY_DATA`, `SUPPLIER_DATA`), plus
  `APP_*` metadata tables (`APP_DATASETS`, `APP_DATASET_DOMAINS`, `APP_DATASET_COLUMNS`,
  `APP_RELATIONSHIPS`, `APP_CONVERSATIONS`) tracking upload/column/relationship/session state.

## 2. Domain ontology

Registry-driven, not hardcoded into pipeline logic (`sf_lib/domain_agents.py`):

| Agent key | Table | Core concepts |
|---|---|---|
| `customer_agent` | `CUSTOMER_DATA` | customer, user id, registration, segment |
| `order_agent` | `ORDER_DATA` | order, items, total, status, payment |
| `financial_agent` | `FINANCIAL_DATA` | revenue, expenses, margin, transactions |
| `delivery_agent` | `DELIVERY_DATA` | shipment, ETA, carrier, delay |
| `product_agent` | `PRODUCT_DATA` | product, SKU, category, price |
| `inventory_agent` | `INVENTORY_DATA` | stock level, reorder level, warehouse |
| `supplier_agent` | `SUPPLIER_DATA` | supplier, procurement, lead time |

Adding an 8th domain is a registry entry plus rerunning `setup_domain_agents.py` — nothing in
`orchestrator.py`, `query_pipeline.py`, or `ingestion_pipeline.py` hardcodes a domain count.

## 3. Ingestion workflow

```
Upload file -> Orchestrator Agent (plain structured Cortex COMPLETE call) routes columns
  across domain(s), force-propagating every _id-suffixed column to every domain touched
  (code-level guarantee, not trusted to the model alone — see orchestrator.py:87-97)
-> per-domain Classification Agent proposes a schema against that domain's EXISTING columns
  (new upload either matches or extends, never replaces)
-> user reviews/edits the proposed mapping per domain
-> confirm -> each domain's real Cortex Agent calls MergeDomainTable
  (CREATE TABLE IF NOT EXISTS, or ALTER TABLE ADD COLUMN for new ones)
-> schema_service.load_rows() upserts (MERGE on detected PK, deduped first) or appends
  (no PK known) -> domain table status flips to READY
```

## 4. Cortex Agents

Real `CREATE AGENT` objects invoked via `SNOWFLAKE.CORTEX.DATA_AGENT_RUN`
(`setup_domain_agents.py`), not plain `COMPLETE` calls pretending to be agentic:

- **Two tiers**: 7 *primary* agents (tools: `MergeDomainTable`, `RunDomainQuery`,
  `AskAnotherAgent`) and 7 `_SUB` agents (tool: `RunDomainQuery` only — delegation target,
  cannot delegate further).
- SQL is authored **and** executed inside one agent turn — no separate SQL-generation step
  hands it pre-written SQL (`sf_lib/domain_agent.py:answer_via_agent`).
- Verified live independent of either app surface via `snow_cli_tools.sh` — see Phase 5.

## 5. Agent-to-agent delegation

A primary agent calls its `AskAnotherAgent` tool when it needs a shared key it doesn't own;
`ASK_AGENT_PROC` resolves the target's live column list and forwards the question to that
domain's `_SUB` agent. Recursion is capped at exactly **one hop by construction**: `_SUB`
agents simply have no `AskAnotherAgent` tool in their spec, so a delegated question can never
itself delegate — this is a structural guarantee, not an instruction the model could ignore.

## 6. MCP

`mcp_server/server.py` exposes exactly two tools — `upload_data` and `ask_question` — as thin,
validated, authenticated proxies onto the real FastAPI backend. No pipeline logic is
reimplemented in the MCP layer. See `mcp_server/README.md` for the auth/validation model.

## 7. Guardrails

- `sql_validator.py` — post-hoc check on agent-authored SQL: single statement only, must start
  `SELECT`/`WITH`, no DDL/DML keywords, every qualified table reference must resolve to the
  caller's own database/schema (and an explicit table allowlist when given).
- One-hop delegation cap (see §5) — structural, not instructional.
- Per-request isolation: each domain agent call in `query_pipeline.py` is wrapped in its own
  try/except so one failing agent can't crash the whole request.
- Per-tenant isolation: Streamlit path uses real per-user Snowflake logins (RBAC); FastAPI path
  uses one shared connection + a per-user schema name (`USER_<hash>`).
- Ingestion-time data-quality guard: `schema_service.load_rows()` drops rows with a null
  primary key before loading instead of letting one bad row fail an entire batch MERGE.

## 8. Testing strategy

Two layers, both real:

- **Unit tests** (`snowflake_app/tests/`) — pure-logic pieces that don't require a live
  Snowflake session: SQL validator edge cases, orchestrator column-routing post-processing
  (dedup, unknown-key filtering, `_id` force-propagation).
- **Live test matrix** (Phase 5, `docs/COCO_TEST_MATRIX.md`) — nine scenarios run against the
  actual deployed backend and real Cortex Agents: normal analytics, cross-domain, unknown
  entity, ambiguous question, destructive SQL rejected, unauthorized table rejected, delegation
  depth capped at one hop, MCP upload, MCP question.

## 9. CoCo lifecycle usage in this project

This plan itself, the project skill (`.cortex/skills/eagleview/SKILL.md`), a real security fix
plus new unit tests, a fresh live pipeline execution, and the nine-test live matrix were all
produced in one continuous CoCo (Claude Code) session — not retrofitted after the fact. Every
claim above that says "verified live" was actually executed and checked in this session, not
asserted from reading the code alone.
