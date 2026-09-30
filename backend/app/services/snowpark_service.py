"""Bridges this FastAPI backend to the real agent pipeline in
snowflake_app/sf_lib (the same code the Streamlit-in-Snowflake app runs) —
one shared Snowpark session, reused across requests, plus a `ctx` builder
matching what sf_lib's functions expect. This backend isolates users by
schema only (one shared, privileged Snowflake connection; see
snowflake_service.py) rather than per-user Snowflake logins, which is a
different (simpler, less strict) isolation model than the Streamlit app's
RBAC-via-separate-roles — acceptable here since it mirrors this backend's
existing SQLite-side per-user-schema design (see app.models.User.snowflake_schema).
"""

import sys
from pathlib import Path
from threading import Lock

_SNOWFLAKE_APP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "snowflake_app"
if str(_SNOWFLAKE_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_SNOWFLAKE_APP_DIR))

from snowflake.snowpark import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models import User  # noqa: E402
from sf_lib import metadata as sf_metadata  # noqa: E402

settings = get_settings()

_session: Session | None = None
_lock = Lock()

_CONNECTION_CONFIG = {
    "account": settings.snowflake_account,
    "user": settings.snowflake_user,
    "password": settings.snowflake_password,
    "role": settings.snowflake_role,
    "warehouse": settings.snowflake_warehouse,
    "database": settings.snowflake_database,
}


def get_session() -> Session:
    global _session
    if _session is None:
        with _lock:
            if _session is None:
                _session = Session.builder.configs(_CONNECTION_CONFIG).create()
    return _session


def new_session() -> Session:
    """A fresh, independent session (its own connection) — a single session
    can only run one query at a time, so real parallel Cortex Agent dispatch
    needs one of these per concurrent call, not the shared singleton above.
    """
    return Session.builder.configs(_CONNECTION_CONFIG).create()


def ctx_for_user(user: User) -> dict:
    return {
        "database": settings.snowflake_database,
        "schema": user.snowflake_schema,
        "user": user.email,
    }


def ready_context(user: User) -> tuple[Session, dict]:
    """A Snowpark session plus this user's ctx, with their schema and the
    sf_lib metadata tables guaranteed to exist (idempotent, cheap to call
    on every request).
    """
    session = get_session()
    ctx = ctx_for_user(user)
    session.sql(f'CREATE SCHEMA IF NOT EXISTS "{ctx["database"]}"."{ctx["schema"]}"').collect()
    sf_metadata.ensure_metadata_tables(session, ctx)
    return session, ctx
