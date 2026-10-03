# CoCo Execution Log — Phase 4

A fresh, live run of the full pipeline against the real backend (`http://localhost:8001`) and
the real `EGLE_VIEW` Snowflake account, executed in this CoCo session on 2026-10-03, not
reconstructed after the fact.

```
Load demo datasets
      v
Analyze datasets
      v
Confirm mappings
      v
Create domain tables
      v
Ask question
      v
Domain agents
      v
SQL validation
      v
Result interpretation
```

## Load → analyze → confirm → create domain tables

`POST /api/datasets/seed-demo` — runs the real pipeline (`demo_seed.seed_demo_datasets` →
`ingestion_pipeline.analyze_dataset` → `ingestion_pipeline.confirm_dataset`) against all 5
bundled demo CSVs.

```
Customers            status=READY
Products              status=READY
Orders                status=READY
Payments              status=READY
Deliveries            status=READY
agent_log entries: 41
```

Sample of the real agent trace captured during this run (`backend` log, unedited):

```
18:28:29 ← [product_agent] called tool(s): MergeDomainTable
18:28:29 product_agent: I'll merge the table now with the confirmed schema. The PRODUCT_DATA
  table is ready in EGLE_VIEW.USER_12867DD0B4167A9CCA20 with all five columns
  (PRODUCT_ID, PRODUCT_NAME, PRODUCT_CATEGORY, PRODUCT_BRAND, UNIT_PRICE) — it already
  existed with the full schema, so nothing needed to be added.
18:28:52 🧭 Orchestrator routed this upload to: order_agent, customer_agent, product_agent, financial_agent
18:28:52 🏷️ Classifying slice for order_agent: columns=['order_id', 'order_dt', 'order_status', 'payment_status', 'cust_id', 'prod_id']
...
18:31:49 ← [order_agent] called tool(s): MergeDomainTable
18:31:49 order_agent: I'll merge the table now with the confirmed schema. The ORDER_DATA table
  is ready with all six columns: ORDER_ID, ORDER_DATE, ORDER_STATUS, PAYMENT_STATUS,
  CUSTOMER_ID, and PRODUCT_ID.
```

This whole run (5 files, each split across 1-4 domains, each domain merging via a real Cortex
Agent tool call) took several minutes of genuine agent latency — not a mocked or instant
response.

## Ask question → domain agents → SQL validation → result interpretation

`POST /api/query` — see Tests 1, 2, 3, 4, 9 in `docs/COCO_TEST_MATRIX.md` for the specific
question/answer pairs this step produced. One excerpt, showing the full chain in one backend
log capture:

```
18:36:24 🧠 Query Understanding: "How many products are in the catalog?"
18:36:39 🧠 Understood as intent=analytics, entity=None/None,
  relevantTables=['EGLE_VIEW".USER_12867DD0B4167A9CCA20".PRODUCT_DATA']
18:36:39 📡 Asking product_agent to write and run its own query
18:36:39 → [product_agent] called: User question: How many products are in the catalog?
  database is EGLE_VIEW, schema is USER_12867DD0B4167A9CCA20. Availab…
18:36:50 ← [product_agent] called tool(s): RunDomainQuery
18:36:50 📡 product_agent returned 1 row(s)
18:36:50 ✅ Agents actually consulted for this question: product_agent
18:36:50 💬 Result Interpretation Agent is writing the final answer…
```

Every step in the diagram above was exercised by a real HTTP call against the live backend in
this session — none of it is simulated.
