import re

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Dataset, DatasetColumn, DatasetRelationship
from app.utils.naming import safe_identifier

_VALID_TYPES = {
    "INTEGER",
    "FLOAT",
    "NUMBER(18,2)",
    "VARCHAR",
    "BOOLEAN",
    "DATE",
    "TIMESTAMP_NTZ",
    "TIME",
}


def _normalize_type(t: str) -> str:
    if not t:
        return "VARCHAR"
    t_upper = t.strip().upper()
    if t_upper in _VALID_TYPES:
        return t_upper
    if t_upper.startswith("NUMBER") or t_upper.startswith("DECIMAL"):
        return t_upper
    if t_upper.startswith("VARCHAR"):
        return t_upper
    return "VARCHAR"


def build_columns_from_classification(dataset_id: str, classification: dict) -> list[DatasetColumn]:
    columns: list[DatasetColumn] = []
    seen_targets: set[str] = set()

    for idx, col in enumerate(classification.get("columns", [])):
        source_column = str(col.get("sourceColumn", f"column_{idx}"))
        suggested = safe_identifier(col.get("suggestedColumn") or source_column)

        target = suggested
        n = 2
        while target in seen_targets:
            target = f"{suggested}_{n}"
            n += 1
        seen_targets.add(target)

        is_pk = bool(col.get("primaryKeyCandidate", False))

        columns.append(
            DatasetColumn(
                dataset_id=dataset_id,
                order_index=idx,
                source_column=source_column,
                suggested_column=suggested,
                target_column=target,
                semantic_type=str(col.get("semanticType", "")),
                suggested_type=_normalize_type(col.get("suggestedType", "VARCHAR")),
                target_type=_normalize_type(col.get("suggestedType", "VARCHAR")),
                nullable=not is_pk,
                primary_key_candidate=is_pk,
                foreign_key_candidate=bool(col.get("foreignKeyCandidate", False)),
                include=True,
                confidence=float(col.get("confidence", 0.0)),
                source="AI_SUGGESTED",
            )
        )
    return columns


def suggested_table_name(classification: dict, fallback: str) -> str:
    raw = classification.get("suggestedTableName") or classification.get("datasetType") or fallback
    return safe_identifier(raw, default="DATASET")


def safe_identifier_table(name: str) -> str:
    return safe_identifier(name, default="DATASET")


_TRUE_STRINGS = {"true", "1", "yes", "y"}
_FALSE_STRINGS = {"false", "0", "no", "n"}


def _cast_column(series: pd.Series, target_type: str) -> pd.Series:
    t = (target_type or "VARCHAR").upper()
    if t == "INTEGER":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    if t == "FLOAT" or t.startswith("NUMBER") or t.startswith("DECIMAL"):
        return pd.to_numeric(series, errors="coerce").astype(float)
    if t == "BOOLEAN":
        def to_bool(v):
            if pd.isna(v):
                return None
            s = str(v).strip().lower()
            if s in _TRUE_STRINGS:
                return True
            if s in _FALSE_STRINGS:
                return False
            return None

        return series.apply(to_bool)
    if t == "DATE":
        return pd.to_datetime(series, errors="coerce").dt.date.astype(object).where(series.notna(), None)
    if t in ("TIMESTAMP_NTZ", "TIMESTAMP", "DATETIME"):
        return pd.to_datetime(series, errors="coerce")
    # VARCHAR / fallback
    return series.astype(object).where(series.notna(), None).apply(lambda v: None if v is None else str(v))


def build_load_dataframe(raw_df: pd.DataFrame, columns: list[DatasetColumn]) -> pd.DataFrame:
    """Select, rename, cast, and order columns for the confirmed schema before loading to Snowflake."""
    included = [c for c in columns if c.include]
    out = pd.DataFrame(index=raw_df.index)
    for col in included:
        if col.source_column not in raw_df.columns:
            out[col.target_column] = None
            continue
        out[col.target_column] = _cast_column(raw_df[col.source_column], col.target_type)
    return out


_ID_SUFFIX_RE = re.compile(r"_ID$")


def detect_relationships(db: Session, user_id: str, dataset: Dataset) -> list[DatasetRelationship]:
    """Heuristic relationship discovery across a user's other READY datasets.

    A foreign-key-candidate column like CUSTOMER_ID on `orders` is linked to the
    primary-key column of a dataset whose type/table looks like "customer(s)",
    falling back to any dataset that has a primary-key column with the same name.
    """
    other_datasets = (
        db.query(Dataset)
        .filter(Dataset.user_id == user_id, Dataset.status == "READY", Dataset.id != dataset.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    if not other_datasets:
        return []

    relationships: list[DatasetRelationship] = []
    fk_columns = [c for c in dataset.columns if c.include and c.foreign_key_candidate]

    for fk in fk_columns:
        entity_hint = _ID_SUFFIX_RE.sub("", fk.target_column).rstrip("_")
        # An exact column-name match is a far stronger signal than the fuzzy
        # entity-hint fallback, so it must always win regardless of which
        # dataset happens to be checked first — never short-circuit on the
        # first candidate that satisfies *either* condition.
        name_match_candidate: tuple[Dataset, DatasetColumn] | None = None
        entity_match_candidate: tuple[Dataset, DatasetColumn] | None = None

        for other in other_datasets:
            for pk in other.columns:
                if not (pk.include and pk.primary_key_candidate):
                    continue
                if pk.target_column == fk.target_column:
                    if name_match_candidate is None:
                        name_match_candidate = (other, pk)
                elif entity_hint and entity_match_candidate is None:
                    if entity_hint in other.dataset_type.upper() or entity_hint in other.snowflake_table.upper():
                        entity_match_candidate = (other, pk)

        best_match = name_match_candidate or entity_match_candidate

        if best_match:
            target_dataset, pk_col = best_match
            relationships.append(
                DatasetRelationship(
                    user_id=user_id,
                    source_dataset_id=dataset.id,
                    target_dataset_id=target_dataset.id,
                    source_column=fk.target_column,
                    target_column=pk_col.target_column,
                    confidence=0.75 if not (pk_col.target_column == fk.target_column) else 0.9,
                )
            )

    return relationships
