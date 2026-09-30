"""Dataset/domain/column/relationship/conversation metadata, stored as ordinary
Snowflake tables inside the CALLER's own schema — no external app database.
Each function takes `ctx` (the dict from rbac.current_context) so every
statement is naturally scoped to `ctx['database'].ctx['schema']`.

One uploaded file (APP_DATASETS row) can now be split by the orchestrator
across multiple business domains — each domain gets its own APP_DATASET_DOMAINS
row, pointing at that domain's fixed, persistent Snowflake table (see
sf_lib/domain_agents.py). That table accumulates rows across every upload ever
routed to it; APP_DATASET_COLUMNS records the mapping used for one particular
upload's slice into that domain, not the table's lifetime schema (use
get_existing_table_columns for the table's actual live schema).
"""

import uuid
from datetime import datetime, timezone

DDL = {
    "APP_DATASETS": """
        CREATE TABLE IF NOT EXISTS {fqn} (
            ID STRING, NAME STRING, ORIGINAL_FILENAME STRING,
            STATUS STRING, ERROR_MESSAGE STRING, ROW_COUNT NUMBER,
            CREATED_AT TIMESTAMP_NTZ, UPDATED_AT TIMESTAMP_NTZ
        )
    """,
    "APP_DATASET_DOMAINS": """
        CREATE TABLE IF NOT EXISTS {fqn} (
            ID STRING, DATASET_ID STRING, AGENT_KEY STRING, TABLE_NAME STRING,
            STATUS STRING, ROW_COUNT NUMBER, AGENT_NOTE STRING, ERROR_MESSAGE STRING,
            CLASSIFICATION_JSON VARIANT, CREATED_AT TIMESTAMP_NTZ, UPDATED_AT TIMESTAMP_NTZ
        )
    """,
    "APP_DATASET_COLUMNS": """
        CREATE TABLE IF NOT EXISTS {fqn} (
            ID STRING, DOMAIN_ID STRING, ORDER_INDEX NUMBER,
            SOURCE_COLUMN STRING, SUGGESTED_COLUMN STRING, TARGET_COLUMN STRING,
            SEMANTIC_TYPE STRING, SUGGESTED_TYPE STRING, TARGET_TYPE STRING,
            NULLABLE BOOLEAN, PRIMARY_KEY_CANDIDATE BOOLEAN, FOREIGN_KEY_CANDIDATE BOOLEAN,
            INCLUDE BOOLEAN, CONFIDENCE FLOAT, SOURCE STRING, IS_NEW_COLUMN BOOLEAN
        )
    """,
    "APP_RELATIONSHIPS": """
        CREATE TABLE IF NOT EXISTS {fqn} (
            ID STRING, SOURCE_AGENT_KEY STRING, TARGET_AGENT_KEY STRING,
            SOURCE_COLUMN STRING, TARGET_COLUMN STRING, CONFIDENCE FLOAT
        )
    """,
    "APP_CONVERSATIONS": """
        CREATE TABLE IF NOT EXISTS {fqn} (
            ID STRING, SESSION_ID STRING, ROLE STRING, CONTENT STRING,
            ENTITY_TYPE STRING, ENTITY_ID STRING, SQL_GENERATED STRING,
            CREATED_AT TIMESTAMP_NTZ
        )
    """,
}


def _fqn(ctx: dict, table: str) -> str:
    return f'"{ctx["database"]}"."{ctx["schema"]}"."{table}"'


def ensure_metadata_tables(session, ctx: dict) -> None:
    for table, ddl in DDL.items():
        session.sql(ddl.format(fqn=_fqn(ctx, table))).collect()


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


def _generic_update(session, ctx: dict, table: str, row_id: str, fields: dict) -> None:
    if not fields:
        return
    import json

    sets = []
    params = []
    for k, v in fields.items():
        col = k.upper()
        if col == "CLASSIFICATION_JSON":
            sets.append(f"{col} = PARSE_JSON(?)")
            params.append(json.dumps(v))
        else:
            sets.append(f"{col} = ?")
            params.append(v)
    sets.append("UPDATED_AT = ?")
    params.append(now())
    params.append(row_id)
    session.sql(
        f"UPDATE {_fqn(ctx, table)} SET {', '.join(sets)} WHERE ID = ?", params=params
    ).collect()


# ------------------------------------------------------------------ datasets --
def create_dataset(session, ctx: dict, name: str, original_filename: str) -> str:
    dataset_id = new_id()
    ts = now()
    session.sql(
        f"""INSERT INTO {_fqn(ctx, "APP_DATASETS")}
            (ID, NAME, ORIGINAL_FILENAME, STATUS, ERROR_MESSAGE, ROW_COUNT, CREATED_AT, UPDATED_AT)
            SELECT ?, ?, ?, 'UPLOADED', '', 0, ?, ?""",
        params=[dataset_id, name, original_filename, ts, ts],
    ).collect()
    return dataset_id


def update_dataset(session, ctx: dict, dataset_id: str, **fields) -> None:
    _generic_update(session, ctx, "APP_DATASETS", dataset_id, fields)


def get_dataset(session, ctx: dict, dataset_id: str) -> dict | None:
    rows = session.sql(
        f"SELECT * FROM {_fqn(ctx, 'APP_DATASETS')} WHERE ID = ?", params=[dataset_id]
    ).collect()
    return rows[0].as_dict() if rows else None


def list_datasets(session, ctx: dict) -> list[dict]:
    rows = session.sql(
        f"SELECT * FROM {_fqn(ctx, 'APP_DATASETS')} ORDER BY CREATED_AT DESC"
    ).collect()
    return [r.as_dict() for r in rows]


def delete_dataset(session, ctx: dict, dataset_id: str) -> None:
    domain_ids = [
        d["ID"] for d in session.sql(
            f"SELECT ID FROM {_fqn(ctx, 'APP_DATASET_DOMAINS')} WHERE DATASET_ID = ?",
            params=[dataset_id],
        ).collect()
    ]
    for domain_id in domain_ids:
        session.sql(
            f"DELETE FROM {_fqn(ctx, 'APP_DATASET_COLUMNS')} WHERE DOMAIN_ID = ?", params=[domain_id]
        ).collect()
    session.sql(
        f"DELETE FROM {_fqn(ctx, 'APP_DATASET_DOMAINS')} WHERE DATASET_ID = ?", params=[dataset_id]
    ).collect()
    session.sql(
        f"DELETE FROM {_fqn(ctx, 'APP_DATASETS')} WHERE ID = ?", params=[dataset_id]
    ).collect()


# ------------------------------------------------------------ domain slices --
def create_domain_slice(session, ctx: dict, dataset_id: str, agent_key: str, table_name: str) -> str:
    domain_id = new_id()
    ts = now()
    session.sql(
        f"""INSERT INTO {_fqn(ctx, "APP_DATASET_DOMAINS")}
            (ID, DATASET_ID, AGENT_KEY, TABLE_NAME, STATUS, ROW_COUNT, AGENT_NOTE,
             ERROR_MESSAGE, CLASSIFICATION_JSON, CREATED_AT, UPDATED_AT)
            SELECT ?, ?, ?, ?, 'SCHEMA_PROPOSED', 0, '', '', PARSE_JSON('{{}}'), ?, ?""",
        params=[domain_id, dataset_id, agent_key, table_name, ts, ts],
    ).collect()
    return domain_id


def update_domain_slice(session, ctx: dict, domain_id: str, **fields) -> None:
    _generic_update(session, ctx, "APP_DATASET_DOMAINS", domain_id, fields)


def get_domain_slice(session, ctx: dict, domain_id: str) -> dict | None:
    rows = session.sql(
        f"SELECT * FROM {_fqn(ctx, 'APP_DATASET_DOMAINS')} WHERE ID = ?", params=[domain_id]
    ).collect()
    return rows[0].as_dict() if rows else None


def list_domain_slices_for_dataset(session, ctx: dict, dataset_id: str) -> list[dict]:
    rows = session.sql(
        f"SELECT * FROM {_fqn(ctx, 'APP_DATASET_DOMAINS')} WHERE DATASET_ID = ? ORDER BY CREATED_AT",
        params=[dataset_id],
    ).collect()
    return [r.as_dict() for r in rows]


def list_ready_domains(session, ctx: dict) -> list[dict]:
    """One row per business domain the user has EVER loaded data into
    (distinct AGENT_KEY among READY slices), with a live row count queried
    straight from that domain's persistent table — authoritative even though
    many uploads may have merged into it over time.
    """
    rows = session.sql(
        f"""SELECT DISTINCT AGENT_KEY, TABLE_NAME FROM {_fqn(ctx, 'APP_DATASET_DOMAINS')}
            WHERE STATUS = 'READY'"""
    ).collect()
    result = []
    for r in rows:
        d = r.as_dict()
        table_fqn = f'"{ctx["database"]}"."{ctx["schema"]}"."{d["TABLE_NAME"]}"'
        count_row = session.sql(f"SELECT COUNT(*) AS CNT FROM {table_fqn}").collect()[0]
        d["ROW_COUNT"] = count_row["CNT"]
        result.append(d)
    return result


def get_existing_table_columns(session, ctx: dict, table_name: str) -> list[dict]:
    """The domain table's actual live schema (empty if the table doesn't exist
    yet) — used so schema proposals reuse existing column names/types instead
    of re-inventing them, and only ever ADD what's genuinely new.
    """
    try:
        rows = session.sql(f'DESCRIBE TABLE {_fqn(ctx, table_name)}').collect()
    except Exception:  # noqa: BLE001 - table doesn't exist yet
        return []
    return [{"name": r["name"], "type": r["type"]} for r in rows]


# ---------------------------------------------------------------- columns --
def replace_columns_for_domain(session, ctx: dict, domain_id: str, columns: list[dict]) -> None:
    session.sql(
        f"DELETE FROM {_fqn(ctx, 'APP_DATASET_COLUMNS')} WHERE DOMAIN_ID = ?", params=[domain_id]
    ).collect()
    for col in columns:
        session.sql(
            f"""INSERT INTO {_fqn(ctx, "APP_DATASET_COLUMNS")}
                (ID, DOMAIN_ID, ORDER_INDEX, SOURCE_COLUMN, SUGGESTED_COLUMN, TARGET_COLUMN,
                 SEMANTIC_TYPE, SUGGESTED_TYPE, TARGET_TYPE, NULLABLE, PRIMARY_KEY_CANDIDATE,
                 FOREIGN_KEY_CANDIDATE, INCLUDE, CONFIDENCE, SOURCE, IS_NEW_COLUMN)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?""",
            params=[
                new_id(), domain_id, col["order_index"], col["source_column"],
                col["suggested_column"], col["target_column"], col["semantic_type"],
                col["suggested_type"], col["target_type"], col["nullable"],
                col["primary_key_candidate"], col["foreign_key_candidate"], col["include"],
                col["confidence"], col["source"], col.get("is_new_column", True),
            ],
        ).collect()


def get_columns_for_domain(session, ctx: dict, domain_id: str) -> list[dict]:
    rows = session.sql(
        f"SELECT * FROM {_fqn(ctx, 'APP_DATASET_COLUMNS')} WHERE DOMAIN_ID = ? ORDER BY ORDER_INDEX",
        params=[domain_id],
    ).collect()
    return [r.as_dict() for r in rows]


def update_column(session, ctx: dict, column_id: str, **fields) -> None:
    if not fields:
        return
    sets = [f"{k.upper()} = ?" for k in fields]
    params = list(fields.values()) + [column_id]
    session.sql(
        f"UPDATE {_fqn(ctx, 'APP_DATASET_COLUMNS')} SET {', '.join(sets)} WHERE ID = ?", params=params
    ).collect()


# ----------------------------------------------------------- relationships --
def add_relationship_if_new(session, ctx: dict, rel: dict) -> None:
    existing = session.sql(
        f"""SELECT ID FROM {_fqn(ctx, 'APP_RELATIONSHIPS')}
            WHERE SOURCE_AGENT_KEY = ? AND TARGET_AGENT_KEY = ?
              AND SOURCE_COLUMN = ? AND TARGET_COLUMN = ?""",
        params=[rel["source_agent_key"], rel["target_agent_key"], rel["source_column"], rel["target_column"]],
    ).collect()
    if existing:
        return
    session.sql(
        f"""INSERT INTO {_fqn(ctx, "APP_RELATIONSHIPS")}
            (ID, SOURCE_AGENT_KEY, TARGET_AGENT_KEY, SOURCE_COLUMN, TARGET_COLUMN, CONFIDENCE)
            SELECT ?, ?, ?, ?, ?, ?""",
        params=[
            new_id(), rel["source_agent_key"], rel["target_agent_key"],
            rel["source_column"], rel["target_column"], rel["confidence"],
        ],
    ).collect()


def list_relationships(session, ctx: dict) -> list[dict]:
    rows = session.sql(f"SELECT * FROM {_fqn(ctx, 'APP_RELATIONSHIPS')}").collect()
    return [r.as_dict() for r in rows]


# ---------------------------------------------------------- conversation --
def append_message(
    session, ctx: dict, session_id: str, role: str, content: str,
    entity_type: str = "", entity_id: str = "", sql_generated: str = "",
) -> None:
    session.sql(
        f"""INSERT INTO {_fqn(ctx, "APP_CONVERSATIONS")}
            (ID, SESSION_ID, ROLE, CONTENT, ENTITY_TYPE, ENTITY_ID, SQL_GENERATED, CREATED_AT)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?""",
        params=[new_id(), session_id, role, content, entity_type, entity_id, sql_generated, now()],
    ).collect()


def get_recent_history(session, ctx: dict, session_id: str, limit: int = 8) -> list[dict]:
    rows = session.sql(
        f"""SELECT * FROM {_fqn(ctx, "APP_CONVERSATIONS")} WHERE SESSION_ID = ?
            ORDER BY CREATED_AT DESC LIMIT {int(limit)}""",
        params=[session_id],
    ).collect()
    return [r.as_dict() for r in rows][::-1]
