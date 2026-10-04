"""Seeds the 5 bundled demo CSVs straight through the real pipeline. The CSVs
ship as part of the Streamlit app's own staged files (demo_data/*.csv next to
streamlit_app.py) so this works with zero external dependencies at runtime.
"""

import logging
from pathlib import Path

from sf_lib import ingestion_pipeline

logger = logging.getLogger("app.demo_seed")

DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"

DEMO_FILES = [
    ("suppliers.csv", "Suppliers"),
    ("plants.csv", "Plants"),
    ("parts.csv", "Parts"),
    ("customers.csv", "Customers"),
    ("products.csv", "Products"),
    ("orders.csv", "Orders"),
    ("payments.csv", "Payments"),
    ("deliveries.csv", "Deliveries"),
    ("purchase_orders.csv", "Purchase Orders"),
    ("inbound_shipments.csv", "Inbound Shipments"),
    ("inventory_snapshots.csv", "Inventory Snapshots"),
]


def seed_demo_datasets(session, ctx: dict) -> list[dict]:
    results = []
    for filename, label in DEMO_FILES:
        path = DEMO_DATA_DIR / filename
        if not path.exists():
            results.append({"name": label, "status": "FAILED", "error": "Demo file not found on server"})
            continue
        try:
            dataset_id, df = ingestion_pipeline.upload_dataset(session, ctx, filename, path.read_bytes())
            ingestion_pipeline.analyze_dataset(session, ctx, dataset_id, df)
            ingestion_pipeline.confirm_dataset(session, ctx, dataset_id, df)
            results.append({"name": label, "status": "READY", "error": None})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Demo seed failed for %s", filename)
            results.append({"name": label, "status": "FAILED", "error": str(exc)})
    return results
