import contextlib
import logging
from typing import Any

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from app.config import get_settings
from app.utils.naming import safe_identifier

logger = logging.getLogger("app.snowflake")
settings = get_settings()


def _load_private_key_bytes() -> bytes | None:
    if not settings.snowflake_private_key_path:
        return None
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    with open(settings.snowflake_private_key_path, "rb") as f:
        key_data = f.read()

    passphrase = settings.snowflake_private_key_passphrase.encode() if settings.snowflake_private_key_passphrase else None
    private_key = serialization.load_pem_private_key(key_data, password=passphrase, backend=default_backend())
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@contextlib.contextmanager
def get_connection():
    if not settings.snowflake_account or not settings.snowflake_user:
        raise RuntimeError("Snowflake is not configured. Set SNOWFLAKE_* vars in backend/.env")

    kwargs: dict[str, Any] = dict(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        role=settings.snowflake_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        client_session_keep_alive=True,
    )

    private_key = _load_private_key_bytes()
    if private_key:
        kwargs["private_key"] = private_key
    else:
        kwargs["password"] = settings.snowflake_password

    conn = snowflake.connector.connect(**kwargs)
    try:
        yield conn
    finally:
        conn.close()


def ensure_user_schema(schema_name: str) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{settings.snowflake_database}"."{schema_name}"')
        finally:
            cur.close()


def create_or_replace_table(schema_name: str, table_name: str, columns: list[dict]) -> None:
    """columns: [{"name": str, "type": str, "nullable": bool}, ...]"""
    col_defs = []
    for col in columns:
        null_clause = "" if col.get("nullable", True) else " NOT NULL"
        col_defs.append(f'"{col["name"]}" {col["type"]}{null_clause}')
    ddl = (
        f'CREATE OR REPLACE TABLE "{settings.snowflake_database}"."{schema_name}"."{table_name}" '
        f"({', '.join(col_defs)})"
    )
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(ddl)
        finally:
            cur.close()


def load_dataframe(schema_name: str, table_name: str, df: pd.DataFrame) -> int:
    """df must already have final target column names as its column headers (uppercase)."""
    with get_connection() as conn:
        success, chunks, rows, _ = write_pandas(
            conn,
            df,
            table_name=table_name,
            database=settings.snowflake_database,
            schema=schema_name,
            quote_identifiers=True,
            auto_create_table=False,
            # Without this, pyarrow's Parquet encoding of datetime64 columns is
            # misread by Snowflake's COPY INTO as raw nanosecond integers, so
            # every TIMESTAMP/DATE column comes back ~1e9x too large on fetch.
            use_logical_type=True,
        )
        if not success:
            raise RuntimeError("Failed to load data into Snowflake")
        return rows


def execute_query(sql: str) -> tuple[list[str], list[dict]]:
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql)
            columns = [safe_identifier(d[0]) for d in cur.description]
            rows = cur.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            return columns, results
        finally:
            cur.close()


def table_row_count(schema_name: str, table_name: str) -> int:
    _, rows = execute_query(
        f'SELECT COUNT(*) AS CNT FROM "{settings.snowflake_database}"."{schema_name}"."{table_name}"'
    )
    return int(rows[0]["CNT"]) if rows else 0
