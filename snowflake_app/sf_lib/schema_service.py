import pandas as pd

from sf_lib import metadata
from sf_lib.activity_log import log
from sf_lib.naming import safe_identifier

_VALID_TYPES = {
    "INTEGER", "FLOAT", "NUMBER(18,2)", "VARCHAR", "BOOLEAN", "DATE", "TIMESTAMP_NTZ", "TIME",
}


def _normalize_type(t: str) -> str:
    if not t:
        return "VARCHAR"
    t_upper = t.strip().upper()
    if t_upper in _VALID_TYPES:
        return t_upper
    if t_upper.startswith("NUMBER") or t_upper.startswith("DECIMAL") or t_upper.startswith("VARCHAR"):
        return t_upper
    return "VARCHAR"


def build_columns_from_classification(classification: dict, existing_columns: list[dict] | None = None) -> list[dict]:
    """Returns plain dicts (not yet persisted) shaped like an APP_DATASET_COLUMNS row.
    `existing_columns` (the domain table's current live schema, if any) lets a
    proposed column that matches an existing one keep its exact name/type
    instead of being deduped/renamed as if it were a brand new column.
    """
    columns: list[dict] = []
    existing_names = {c["name"].upper() for c in (existing_columns or [])}
    seen_targets: set[str] = set()

    for idx, col in enumerate(classification.get("columns", [])):
        source_column = str(col.get("sourceColumn", f"column_{idx}"))
        suggested = safe_identifier(col.get("suggestedColumn") or source_column)
        is_new = bool(col.get("isNewColumn", suggested.upper() not in existing_names))

        target = suggested
        if is_new:
            n = 2
            while target in seen_targets:
                target = f"{suggested}_{n}"
                n += 1
        seen_targets.add(target)

        is_pk = bool(col.get("primaryKeyCandidate", False))
        norm_type = _normalize_type(col.get("suggestedType", "VARCHAR"))

        columns.append({
            "order_index": idx,
            "source_column": source_column,
            "suggested_column": suggested,
            "target_column": target,
            "semantic_type": str(col.get("semanticType", "")),
            "suggested_type": norm_type,
            "target_type": norm_type,
            "nullable": not is_pk,
            "primary_key_candidate": is_pk,
            "foreign_key_candidate": bool(col.get("foreignKeyCandidate", False)),
            "include": True,
            "confidence": float(col.get("confidence", 0.0)),
            "source": "AI_SUGGESTED",
            "is_new_column": is_new,
        })
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
    return series.astype(object).where(series.notna(), None).apply(lambda v: None if v is None else str(v))


def build_load_dataframe(raw_df: pd.DataFrame, columns: list[dict]) -> pd.DataFrame:
    included = [c for c in columns if c["include"]]
    out = pd.DataFrame(index=raw_df.index)
    for col in included:
        if col["source_column"] not in raw_df.columns:
            out[col["target_column"]] = None
            continue
        out[col["target_column"]] = _cast_column(raw_df[col["source_column"]], col["target_type"])
    return out


def load_rows(session, ctx: dict, table_name: str, load_df: pd.DataFrame, columns: list[dict]) -> int:
    """Loads rows into a domain's persistent table. When a primary-key column
    was identified, upserts on it (MERGE) so re-uploading data for an entity
    already in the table UPDATES its row instead of appending a duplicate
    with nulls in the columns this upload didn't provide. Falls back to a
    plain append when no primary key is known (e.g. a pure log/event table).
    """
    pk_cols = [c["target_column"] for c in columns if c.get("primary_key_candidate")]
    if not pk_cols:
        session.write_pandas(
            load_df, table_name, database=ctx["database"], schema=ctx["schema"],
            quote_identifiers=True, auto_create_table=False, use_logical_type=True,
        )
        return len(load_df)

    pk_col = pk_cols[0]
    # A primary key column is NOT NULL at the Snowflake table level (see
    # schema_service.build_columns_from_classification: "nullable": not
    # is_pk), but source files routinely have a stray blank cell in an ID
    # column. Snowflake rejects the ENTIRE batch — not just the bad row — on
    # a NOT NULL violation, so drop null-PK rows before they ever reach a
    # MERGE/INSERT rather than letting one bad row block every good one.
    null_pk_count = int(load_df[pk_col].isna().sum())
    if null_pk_count:
        log(f"Dropping {null_pk_count} row(s) with a missing {pk_col} before loading into {table_name}")
        load_df = load_df[load_df[pk_col].notna()]

    # The same entity can legitimately repeat within one upload (e.g. a
    # customer with two orders in the same file) — MERGE rejects a source
    # side with more than one row matching the same target key, so dedupe
    # the batch on the PK first (last occurrence wins).
    deduped_df = load_df.drop_duplicates(subset=[pk_col], keep="last")
    staging_name = f"{table_name}_STAGE_{metadata.new_id()[:8]}"
    session.write_pandas(
        deduped_df, staging_name, database=ctx["database"], schema=ctx["schema"],
        quote_identifiers=True, auto_create_table=True, overwrite=True, use_logical_type=True,
    )
    target_fqn = f'"{ctx["database"]}"."{ctx["schema"]}"."{table_name}"'
    staging_fqn = f'"{ctx["database"]}"."{ctx["schema"]}"."{staging_name}"'
    other_cols = [c["target_column"] for c in columns if c["target_column"] != pk_col]
    all_cols = [pk_col] + other_cols

    update_clause = (
        f"WHEN MATCHED THEN UPDATE SET {', '.join(f'\"{c}\" = s.\"{c}\"' for c in other_cols)}\n"
        if other_cols else ""
    )
    merge_sql = f"""
        MERGE INTO {target_fqn} t
        USING {staging_fqn} s
        ON t."{pk_col}" = s."{pk_col}"
        {update_clause}WHEN NOT MATCHED THEN INSERT ({', '.join(f'"{c}"' for c in all_cols)})
        VALUES ({', '.join(f's."{c}"' for c in all_cols)})
    """
    session.sql(merge_sql).collect()
    session.sql(f"DROP TABLE {staging_fqn}").collect()
    return len(load_df)


def detect_relationships(session, ctx: dict, agent_key: str, columns: list[dict]) -> list[dict]:
    """Exact-column-name-match heuristic across domains: if this domain's FK
    column shares an exact name with a column in another domain's persistent
    table, they're joinable. Scoped to the caller's own schema (RBAC already
    guarantees other domains here belong to this same user).
    """
    included_fks = [
        c for c in columns
        if c["include"] and (c["foreign_key_candidate"] or c["target_column"].upper().endswith("_ID"))
    ]
    if not included_fks:
        return []

    other_domains = [d for d in metadata.list_ready_domains(session, ctx) if d["AGENT_KEY"] != agent_key]
    if not other_domains:
        return []

    relationships: list[dict] = []
    for fk in included_fks:
        fk_name = fk["target_column"].upper()
        for other in other_domains:
            other_cols = metadata.get_existing_table_columns(session, ctx, other["TABLE_NAME"])
            if any(c["name"].upper() == fk_name for c in other_cols):
                relationships.append({
                    "source_agent_key": agent_key,
                    "target_agent_key": other["AGENT_KEY"],
                    "source_column": fk["target_column"],
                    "target_column": fk_name,
                    "confidence": 0.9,
                })
    return relationships
