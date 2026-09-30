"""Shared Stage-1 pipeline steps, used by both the manual upload/review/confirm
routes and the one-shot demo seeding route, so the two paths can't drift apart.
"""

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Dataset, DatasetColumn, User
from app.services import schema_service, snowflake_service
from app.services.classification_service import classify_dataset
from app.services.domain_agents import DOMAIN_AGENTS
from app.services.ingestion_service import dataframe_sample, parse_upload_to_dataframe
from app.services.storage import raw_file_path

logger = logging.getLogger("app.ingestion_pipeline")
settings = get_settings()


def read_dataset_dataframe(dataset: Dataset):
    path = raw_file_path(dataset.id, dataset.original_filename)
    if not path.exists():
        raise FileNotFoundError("Raw file missing; re-upload the dataset")

    with open(path, "rb") as f:
        raw_bytes = f.read()

    class _Stub:
        filename = dataset.original_filename

    return parse_upload_to_dataframe(_Stub(), raw_bytes)  # type: ignore[arg-type]


def analyze_dataset_pipeline(db: Session, dataset: Dataset) -> tuple[dict, list]:
    """Classify the dataset and persist the proposed column mapping.

    Returns (classification, sample_rows). Marks the dataset FAILED and
    re-raises on any error.
    """
    dataset.status = "ANALYZING"
    db.commit()

    try:
        df = read_dataset_dataframe(dataset)
        sample = dataframe_sample(df)
        classification = classify_dataset(list(df.columns), sample)

        agent_key = classification.get("agent", "unknown_agent")
        if agent_key not in DOMAIN_AGENTS:
            agent_key = "unknown_agent"

        dataset.dataset_type = classification.get("datasetType", "unknown")
        dataset.agent = agent_key
        dataset.confidence = float(classification.get("confidence", 0.0))
        dataset.classification_json = classification
        dataset.snowflake_table = schema_service.suggested_table_name(classification, dataset.name)
        dataset.status = "SCHEMA_PROPOSED"

        db.query(DatasetColumn).filter(DatasetColumn.dataset_id == dataset.id).delete()
        columns = schema_service.build_columns_from_classification(dataset.id, classification)
        db.add_all(columns)
        db.commit()
        db.refresh(dataset)
        return classification, sample
    except Exception as exc:  # noqa: BLE001
        dataset.status = "FAILED"
        dataset.error_message = str(exc)
        db.commit()
        logger.exception("Classification failed for dataset %s", dataset.id)
        raise


def confirm_dataset_pipeline(db: Session, user: User, dataset: Dataset, table_name: str) -> None:
    """Create the Snowflake table and load data using the dataset's CURRENT
    column mappings as-is. The caller applies any user edits beforehand.
    """
    included_columns = [c for c in dataset.columns if c.include]
    if not included_columns:
        raise ValueError("At least one column must be included")

    dataset.status = "LOADING"
    db.commit()

    try:
        raw_df = read_dataset_dataframe(dataset)
        load_df = schema_service.build_load_dataframe(raw_df, included_columns)

        snowflake_service.ensure_user_schema(user.snowflake_schema)
        snowflake_service.create_or_replace_table(
            user.snowflake_schema,
            table_name,
            [
                {"name": c.target_column, "type": c.target_type, "nullable": c.nullable}
                for c in included_columns
            ],
        )
        snowflake_service.load_dataframe(user.snowflake_schema, table_name, load_df)
        row_count = snowflake_service.table_row_count(user.snowflake_schema, table_name)

        dataset.snowflake_database = settings.snowflake_database
        dataset.snowflake_schema = user.snowflake_schema
        dataset.snowflake_table = table_name
        dataset.row_count = row_count
        dataset.status = "READY"
        dataset.error_message = ""
        db.commit()

        relationships = schema_service.detect_relationships(db, user.id, dataset)
        if relationships:
            db.add_all(relationships)
            db.commit()
        db.refresh(dataset)
    except Exception as exc:  # noqa: BLE001
        dataset.status = "FAILED"
        dataset.error_message = str(exc)
        db.commit()
        logger.exception("Load failed for dataset %s", dataset.id)
        raise
