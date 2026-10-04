"""Setup supply-chain ontology layer: dynamic tables for derived metrics.

Run after domain tables are populated (demo seed or manual uploads).
Dynamic tables auto-refresh as base tables receive new data.

Usage:
    cd backend && source venv/bin/activate
    python3 ../snowflake_app/setup_dynamic_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import snowflake_service  # noqa: E402

DATABASE = "EGLE_VIEW"
WH = "COMPUTE_WH"


def _dt_sql(schema: str) -> list[str]:
    fq = f'"{DATABASE}"."{schema}"'
    return [
        # ── 1. On-Time Delivery % ─────────────────────────────────────────
        f"""
CREATE OR REPLACE DYNAMIC TABLE {fq}."SC_OTD_METRICS"
  TARGET_LAG = '1 hour'
  WAREHOUSE = {WH}
AS
SELECT
    d.PARTNER                                         AS carrier,
    o.PLANT_ID                                        AS plant_id,
    DATE_TRUNC('month', d.ACTUAL_DELIVERY_DT::DATE)   AS period_month,
    COUNT(*)                                           AS total_delivered,
    SUM(CASE
        WHEN d.ACTUAL_DELIVERY_DT::TIMESTAMP_NTZ <= o.PROMISED_DELIVERY_DT::TIMESTAMP_NTZ
        THEN 1 ELSE 0
    END)                                               AS on_time_count,
    ROUND(on_time_count * 100.0 / NULLIF(total_delivered, 0), 2) AS otd_pct
FROM {fq}."DELIVERY_DATA"   d
JOIN {fq}."ORDER_DATA"      o  ON d.ORDER_ID = o.ORDER_ID
WHERE d.ACTUAL_DELIVERY_DT IS NOT NULL
  AND d.ACTUAL_DELIVERY_DT != ''
GROUP BY carrier, plant_id, period_month
""",
        # ── 2. Fill Rate % ────────────────────────────────────────────────
        f"""
CREATE OR REPLACE DYNAMIC TABLE {fq}."SC_FILL_RATE"
  TARGET_LAG = '1 hour'
  WAREHOUSE = {WH}
AS
SELECT
    o.PLANT_ID                                       AS plant_id,
    o.PROD_ID                                        AS product_id,
    DATE_TRUNC('month', o.ORDER_DT::DATE)            AS period_month,
    SUM(o.REQUESTED_QTY)                             AS total_requested,
    SUM(o.SHIPPED_QTY)                               AS total_shipped,
    ROUND(total_shipped * 100.0 / NULLIF(total_requested, 0), 2) AS fill_rate_pct
FROM {fq}."ORDER_DATA" o
GROUP BY plant_id, product_id, period_month
""",
        # ── 3. Days of Inventory (DOI) ────────────────────────────────────
        f"""
CREATE OR REPLACE DYNAMIC TABLE {fq}."SC_INVENTORY_POSITION"
  TARGET_LAG = '1 hour'
  WAREHOUSE = {WH}
AS
WITH latest AS (
    SELECT
        PLANT_ID,
        PART_ID,
        QTY_ON_HAND,
        QTY_ALLOCATED,
        QTY_IN_TRANSIT,
        REORDER_POINT,
        SAFETY_STOCK,
        ROW_NUMBER() OVER (PARTITION BY PLANT_ID, PART_ID ORDER BY SNAPSHOT_DATE DESC) AS rn
    FROM {fq}."INVENTORY_SNAPSHOT_DATA"
),
avg_daily AS (
    SELECT
        PLANT_ID,
        PART_ID,
        AVG(QTY_ALLOCATED) AS avg_daily_usage
    FROM {fq}."INVENTORY_SNAPSHOT_DATA"
    GROUP BY PLANT_ID, PART_ID
)
SELECT
    l.PLANT_ID,
    l.PART_ID,
    l.QTY_ON_HAND,
    l.QTY_ALLOCATED,
    l.QTY_IN_TRANSIT,
    l.REORDER_POINT,
    l.SAFETY_STOCK,
    a.avg_daily_usage,
    CASE WHEN a.avg_daily_usage > 0
         THEN ROUND(l.QTY_ON_HAND / a.avg_daily_usage, 1)
         ELSE NULL
    END AS days_of_inventory
FROM latest l
JOIN avg_daily a ON l.PLANT_ID = a.PLANT_ID AND l.PART_ID = a.PART_ID
WHERE l.rn = 1
""",
        # ── 4. Landed Cost per PO line ────────────────────────────────────
        f"""
CREATE OR REPLACE DYNAMIC TABLE {fq}."SC_LANDED_COST"
  TARGET_LAG = '1 hour'
  WAREHOUSE = {WH}
AS
SELECT
    po.PO_ID,
    po.SUPPLIER_ID,
    po.PART_ID,
    po.PLANT_ID,
    po.QTY_ORDERED,
    po.QTY_RECEIVED,
    po.UNIT_COST,
    po.FREIGHT_COST,
    po.DUTY_PCT,
    po.INSURANCE_COST,
    ROUND(
        (po.UNIT_COST * po.QTY_RECEIVED)
        + po.FREIGHT_COST
        + (po.UNIT_COST * po.QTY_RECEIVED * po.DUTY_PCT / 100.0)
        + po.INSURANCE_COST
    , 2)                                              AS total_landed_cost,
    CASE WHEN po.QTY_RECEIVED > 0
         THEN ROUND(
              (po.UNIT_COST + po.FREIGHT_COST / po.QTY_RECEIVED
               + po.UNIT_COST * po.DUTY_PCT / 100.0
               + po.INSURANCE_COST / po.QTY_RECEIVED)
         , 2) ELSE NULL
    END                                                AS landed_cost_per_unit
FROM {fq}."PURCHASE_ORDER_DATA" po
WHERE po.QTY_RECEIVED > 0
""",
        # ── 5. Supplier Scorecard ─────────────────────────────────────────
        f"""
CREATE OR REPLACE DYNAMIC TABLE {fq}."SC_SUPPLIER_SCORECARD"
  TARGET_LAG = '1 hour'
  WAREHOUSE = {WH}
AS
WITH po_stats AS (
    SELECT
        SUPPLIER_ID,
        COUNT(*)                                       AS total_pos,
        SUM(CASE WHEN RECEIPT_DATE::TIMESTAMP_NTZ <= PROMISED_DATE::TIMESTAMP_NTZ
                 THEN 1 ELSE 0 END)                    AS on_time_pos,
        SUM(CASE WHEN QTY_RECEIVED >= QTY_ORDERED
                 THEN 1 ELSE 0 END)                    AS full_fill_pos,
        AVG(DATEDIFF('day', ORDER_DATE::DATE, RECEIPT_DATE::DATE)) AS avg_lead_days,
        AVG(
            (UNIT_COST * QTY_RECEIVED + FREIGHT_COST
             + UNIT_COST * QTY_RECEIVED * DUTY_PCT / 100.0
             + INSURANCE_COST)
            / NULLIF(QTY_RECEIVED, 0)
        )                                              AS avg_landed_cost_per_unit
    FROM {fq}."PURCHASE_ORDER_DATA"
    WHERE QTY_RECEIVED > 0
    GROUP BY SUPPLIER_ID
)
SELECT
    s.SUPPLIER_ID,
    s.SUPPLIER_NAME,
    s.COUNTRY,
    s.CONTRACT_TIER,
    s.LEAD_TIME_DAYS           AS contracted_lead_days,
    p.total_pos,
    ROUND(p.on_time_pos * 100.0 / NULLIF(p.total_pos, 0), 2)    AS on_time_delivery_pct,
    ROUND(p.full_fill_pos * 100.0 / NULLIF(p.total_pos, 0), 2)  AS full_fill_rate_pct,
    ROUND(p.avg_lead_days, 1)  AS actual_avg_lead_days,
    ROUND(p.avg_landed_cost_per_unit, 2) AS avg_landed_cost_per_unit
FROM {fq}."SUPPLIER_DATA" s
LEFT JOIN po_stats p ON s.SUPPLIER_ID = p.SUPPLIER_ID
""",
    ]


def setup(schema: str = "DEMO_A"):
    stmts = _dt_sql(schema)
    with snowflake_service.get_connection() as conn:
        cur = conn.cursor()
        names = ["SC_OTD_METRICS", "SC_FILL_RATE", "SC_INVENTORY_POSITION",
                 "SC_LANDED_COST", "SC_SUPPLIER_SCORECARD"]
        for sql, name in zip(stmts, names):
            print(f"Creating dynamic table {name}...")
            cur.execute(sql)
        print("Dynamic tables created.")
        cur.close()


if __name__ == "__main__":
    schema = sys.argv[1] if len(sys.argv) > 1 else "DEMO_A"
    setup(schema)
