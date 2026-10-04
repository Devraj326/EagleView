# Supply Chain Metrics — Reusable CoCo Skill

A reusable skill that knows the canonical supply chain metric definitions. Use it to generate, validate, or explain supply chain KPI SQL for any Snowflake schema.

## Canonical Metric Definitions

### 1. On-Time Delivery % (OTD)
**Definition**: Percentage of deliveries where the actual delivery date is on or before the promised date.
```sql
SELECT
  ROUND(
    SUM(CASE WHEN actual_delivery_dt::TIMESTAMP_NTZ <= promised_delivery_dt::TIMESTAMP_NTZ THEN 1 ELSE 0 END)
    * 100.0 / NULLIF(COUNT(*), 0)
  , 2) AS on_time_delivery_pct
FROM deliveries d
JOIN orders o ON d.order_id = o.order_id
WHERE d.actual_delivery_dt IS NOT NULL AND d.actual_delivery_dt != ''
```
**Required columns**: `actual_delivery_dt`, `promised_delivery_dt`, join key between deliveries and orders.
**Common dimensions**: carrier, plant, customer, time period.
**Gotchas**: Exclude undelivered orders (NULL actual dates). Use TIMESTAMP comparison, not DATE, to avoid timezone edge cases.

### 2. Fill Rate %
**Definition**: Percentage of requested quantity that was actually shipped.
```sql
SELECT
  ROUND(SUM(shipped_qty) * 100.0 / NULLIF(SUM(requested_qty), 0), 2) AS fill_rate_pct
FROM orders
```
**Required columns**: `requested_qty`, `shipped_qty`.
**Common dimensions**: product, plant, supplier, time period.
**Gotchas**: A fill rate >100% means over-shipment — decide if this should be capped at 100%.

### 3. Days of Inventory (DOI)
**Definition**: How many days current on-hand inventory will last at the current consumption rate.
```sql
SELECT
  ROUND(qty_on_hand / NULLIF(avg_daily_usage, 0), 1) AS days_of_inventory
FROM (
  SELECT plant_id, part_id,
    LAST_VALUE(qty_on_hand) OVER (PARTITION BY plant_id, part_id ORDER BY snapshot_date) AS qty_on_hand,
    AVG(qty_allocated) OVER (PARTITION BY plant_id, part_id) AS avg_daily_usage
  FROM inventory_snapshots
)
```
**Required columns**: `snapshot_date`, `qty_on_hand`, `qty_allocated` (as proxy for daily usage).
**Common dimensions**: part, plant, commodity group.
**Gotchas**: DOI is undefined when usage is zero — return NULL, not infinity.

### 4. Landed Cost
**Definition**: Total cost of a purchased item delivered to the plant, including unit cost, freight, duty, and insurance.
```sql
SELECT
  ROUND(
    (unit_cost * qty_received) + freight_cost + (unit_cost * qty_received * duty_pct / 100.0) + insurance_cost
  , 2) AS total_landed_cost,
  ROUND(
    unit_cost + freight_cost / NULLIF(qty_received, 0) + unit_cost * duty_pct / 100.0 + insurance_cost / NULLIF(qty_received, 0)
  , 2) AS landed_cost_per_unit
FROM purchase_orders
WHERE qty_received > 0
```
**Required columns**: `unit_cost`, `qty_received`, `freight_cost`, `duty_pct`, `insurance_cost`.
**Common dimensions**: supplier, part, commodity group, plant.
**Gotchas**: Exclude zero-quantity POs (division by zero). Duty is a percentage of goods value, not of total cost.

### 5. Supplier Lead Time
**Definition**: Average days between PO order date and receipt date.
```sql
SELECT
  supplier_id,
  ROUND(AVG(DATEDIFF('day', order_date::DATE, receipt_date::DATE)), 1) AS avg_lead_days
FROM purchase_orders
GROUP BY supplier_id
```

### 6. Supplier Reliability (OTIF — On Time In Full)
**Definition**: Percentage of POs where the supplier delivered on time AND in full quantity.
```sql
SELECT
  supplier_id,
  ROUND(
    SUM(CASE WHEN receipt_date <= promised_date AND qty_received >= qty_ordered THEN 1 ELSE 0 END)
    * 100.0 / NULLIF(COUNT(*), 0)
  , 2) AS otif_pct
FROM purchase_orders
GROUP BY supplier_id
```

## Supply Chain Entity-Relationship Model

```
Supplier ──1:N──▸ Part ──N:M──▸ Plant (via Inventory)
    │                │
    │              1:N
    ▼                ▼
Purchase Order ──▸ Inbound Shipment ──▸ Plant
    │
    ▼
  Order ──1:1──▸ Outbound Delivery ──▸ Customer
    │
    ▼
  Payment
```

## How to Use This Skill

1. **Generate metric SQL**: Ask CoCo to write SQL for any of the 6 canonical metrics, specifying your schema and table names.
2. **Validate existing SQL**: Paste your metric SQL and ask CoCo to check it against the canonical definitions above.
3. **Build semantic views**: Use the metric definitions as verified queries in a semantic view YAML.
4. **Create dynamic tables**: Wrap the metric SQL in `CREATE DYNAMIC TABLE ... TARGET_LAG = '1 hour'` for auto-refresh.
5. **Explain metrics**: Ask CoCo to explain what any metric means in business terms, including required columns and gotchas.
