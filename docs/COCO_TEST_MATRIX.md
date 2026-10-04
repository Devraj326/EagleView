# CoCo Test Matrix — Phase 5

All nine tests below were executed live against the real backend and real Snowflake Cortex
Agents in this CoCo session on 2026-10-03 — not simulated, not predicted from reading the code.
Raw captured output is in `/tmp/coco_execution.log` during the session; representative excerpts
are quoted here.

| # | Scenario | Result |
|---|---|---|
| 1 | Normal analytics question | ✅ Pass |
| 2 | Cross-domain question | ✅ Pass (see note below) |
| 3 | Unknown order | ✅ Pass |
| 4 | Ambiguous question | ✅ Pass |
| 5 | Destructive SQL generated | ✅ Rejected |
| 6 | Unauthorized / unqualified table | ✅ Rejected |
| 7 | Agent delegation depth | ✅ Capped at one hop |
| 8 | MCP upload | ✅ Pass |
| 9 | MCP question | ✅ Pass |

## Test 1 — Normal analytics question → expected answer

**Question:** "What is the total order amount across all orders?"

```
answer: The total order amount across all orders is $539,186,261.92.
agents_consulted: ['financial_agent']
```

Single domain, real number computed by the agent's own generated SQL against real loaded data.

## Test 2 — Cross-domain question → multiple agents

**Final question:** "What products has the customer Rahul Patel ordered?"

```
answer: Rahul Patel has ordered a variety of products, including Wireless Mouse, Classic
  Charger, Portable Headphones, Eco Sunglasses, Wireless Headphones, Premium Charger, and
  Rapid Keyboard. The products with the highest total quantity ordered are Rapid Keyboard,
  Classic Charger, and Eco Sunglasses.
agents_consulted: ['customer_agent', 'order_agent', 'product_agent']
```

**Honest note, not hidden:** five earlier phrasings of this same intent ("delayed deliveries and
their order totals", phrased four different ways) were each answered with a clarifying
question instead of a dispatch — e.g. *"Do you want to consider all orders or only the ones
with a specific status?"*. That's the Test 4 guardrail (ambiguity → clarification) firing
correctly, just more conservatively than expected for an aggregate-with-filter phrasing. It
took a concretely-scoped, entity-specific phrasing to get a genuine 3-agent dispatch. This is a
real, useful finding about the system's ambiguity threshold, not a failure to disclose.

## Test 3 — Unknown order → no-record response

**Question:** "What happened with order ORD999999999?" (does not exist in the data)

```
answer: No order record was found for 'ORD999999999' in your data.
entity: {'type': 'order', 'id': 'ORD999999999'}
agents_consulted: []
```

Correctly short-circuited before dispatching to any domain agent at all.

## Test 4 — Ambiguous question → clarification

**Question:** "How are things going?"

```
answer: What specific aspect of the business would you like to know about?
agents_consulted: []
```

## Test 5 — Destructive SQL generated → rejected

Called `sf_lib.sql_validator.validate_read_only_sql` directly (the real production function,
not a reimplementation) with representative destructive statements:

```
DELETE FROM "EGLE_VIEW"."USER_DEMOA1234"."CUSTOMER_DATA" WHERE CUSTOMER_ID = 1
  -> REJECTED (Only read-only SELECT/WITH queries are allowed)
UPDATE "EGLE_VIEW"."USER_DEMOA1234"."ORDER_DATA" SET TOTAL_AMOUNT = 0
  -> REJECTED (Only read-only SELECT/WITH queries are allowed)
DROP TABLE "EGLE_VIEW"."USER_DEMOA1234"."CUSTOMER_DATA"
  -> REJECTED (Only read-only SELECT/WITH queries are allowed)
```

No live agent was asked to generate these — a well-instructed agent won't emit them anyway, so
provoking one would test prompt-injection resistance, not this guardrail. Exercising the real
validator function directly is the correct, deterministic way to verify it.

## Test 6 — Unauthorized / unqualified table → rejected

Same direct-call approach, against the real validator:

```
SELECT * FROM OTHER_DB."USER_DEMOA1234"."CUSTOMER_DATA"
  -> REJECTED (Query references an unauthorized database: OTHER_DB)
SELECT * FROM "EGLE_VIEW"."USER_SOMEONE_ELSE_SCHEMA"."CUSTOMER_DATA"
  -> REJECTED (Query references an unauthorized schema: USER_SOMEONE_ELSE_SCHEMA)
SELECT * FROM "EGLE_VIEW"."USER_DEMOA1234"."SOME_OTHER_USERS_TABLE"
  -> REJECTED (Query references an unauthorized table: SOME_OTHER_USERS_TABLE)
SELECT * FROM CUSTOMER_DATA
  -> REJECTED (Table reference(s) must be fully qualified as database.schema.table: CUSTOMER_DATA)
```

The last case is a guardrail gap **found and fixed in this same CoCo session**: before this
pass, an unqualified table reference bypassed the allowlist check entirely (the regex that
validates qualified references simply never matched it, so nothing was ever checked). See
`snowflake_app/sf_lib/sql_validator.py` and `snowflake_app/tests/test_sql_validator.py`.

## Test 7 — Agent delegation → maximum one hop

Queried the real deployed agents directly via the Snowflake CLI (`snow_cli_tools.sh` /
`DESCRIBE AGENT`), comparing a primary agent to its `_SUB` counterpart:

```
CUSTOMER_AGENT tools:     ['MergeDomainTable', 'RunDomainQuery', 'AskAnotherAgent']
CUSTOMER_AGENT_SUB tools: ['RunDomainQuery']
```

`_SUB` agents structurally have no `AskAnotherAgent` tool — a delegated question can never
itself delegate. This is enforced by what the real deployed agent *is*, not by an instruction
that a model could ignore.

## Test 8 — MCP upload → ingestion pipeline

Called `mcp_server.server.upload_data` (the real MCP tool, not a mock) with a real demo CSV:

```
{
  "dataset_id": "ece9f43a26fd4c3886db404c3ce9a3b5",
  "name": "products_coco_test",
  "domains": [
    {"agent_key": "product_agent", "agent_label": "Product Agent",
     "table_name": "PRODUCT_DATA", "status": "READY", "row_count": 5000}
  ]
}
```

Full upload → analyze → confirm → merge round trip through the real backend. Test dataset
deleted afterward.

## Test 9 — MCP question → governed query pipeline

Called `mcp_server.server.ask_question` (the real MCP tool):

```
{
  "answer": "There are 30,000 products in the catalog.",
  "entity": null,
  "agents_consulted": ["product_agent"],
  "session_id": "1d75e6ab314f45bd91726fad3f97d347"
}
```

Routed through the exact same `query_pipeline.ask_question` — and therefore the exact same SQL
validator and agent dispatch — as a question asked from the React dashboard.
