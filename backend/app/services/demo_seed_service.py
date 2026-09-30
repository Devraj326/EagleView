"""Loads the bundled demo CSVs straight through the full Stage-1 pipeline
(classify -> propose schema -> auto-confirm with the AI-suggested mapping)
for quickly testing the dashboard without manually uploading and reviewing
5 files by hand. Skips human review by design — this is a testing shortcut,
not the primary onboarding flow.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Dataset, User
from app.schemas import DemoSeedResult
from app.services import ingestion_pipeline
from app.services.storage import save_raw_file

logger = logging.getLogger("app.demo_seed")

DEMO_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"

# Order matters: customers/products load before orders, which the other two
# reference, so relationship discovery (FK column -> another dataset's PK)
# has something to link against by the time it runs.
DEMO_FILES: list[tuple[str, str]] = [
    ("customers.csv", "Customers"),
    ("products.csv", "Products"),
    ("orders.csv", "Orders"),
    ("payments.csv", "Payments"),
    ("deliveries.csv", "Deliveries"),
]


def seed_demo_datasets(db: Session, user: User) -> list[DemoSeedResult]:
    results: list[DemoSeedResult] = []

    for filename, label in DEMO_FILES:
        path = DEMO_DATA_DIR / filename
        if not path.exists():
            results.append(
                DemoSeedResult(
                    name=label, filename=filename, status="FAILED", error="Demo file not found on server"
                )
            )
            continue

        dataset = Dataset(user_id=user.id, name=label, original_filename=filename, status="UPLOADED")
        db.add(dataset)
        db.flush()
        save_raw_file(dataset.id, filename, path.read_bytes())
        db.commit()
        db.refresh(dataset)

        try:
            ingestion_pipeline.analyze_dataset_pipeline(db, dataset)
            ingestion_pipeline.confirm_dataset_pipeline(db, user, dataset, dataset.snowflake_table)
            results.append(
                DemoSeedResult(name=label, filename=filename, status=dataset.status, dataset_id=dataset.id)
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Demo seed failed for %s", filename)
            results.append(
                DemoSeedResult(
                    name=label,
                    filename=filename,
                    status="FAILED",
                    error=str(exc),
                    dataset_id=dataset.id,
                )
            )

    return results
