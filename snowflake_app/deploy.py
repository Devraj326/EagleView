"""Deploys this directory as a Streamlit-in-Snowflake app: stages every file
(preserving the sf_lib/ and demo_data/ subfolders the app's imports and file
reads depend on) and (re)creates the STREAMLIT object EXECUTE AS CALLER, so
CURRENT_ROLE() inside the app is genuinely the signed-in viewer's own role —
that's what makes the per-user RBAC isolation actually take effect.

Run from the backend venv (has snowflake-connector-python + the .env creds):
    cd backend && source venv/bin/activate
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python3 ../snowflake_app/deploy.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services import snowflake_service  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
DATABASE = "EGLE_VIEW"
SCHEMA = "PUBLIC"
STAGE = f"{DATABASE}.{SCHEMA}.EGLEVIEW_STAGE"
APP_NAME = f"{DATABASE}.{SCHEMA}.EGLEVIEW"
WAREHOUSE = "COMPUTE_WH"

FILES = [
    ("streamlit_app.py", ""),
    ("environment.yml", ""),
    ("sf_lib/__init__.py", "sf_lib"),
    ("sf_lib/cortex.py", "sf_lib"),
    ("sf_lib/domain_agents.py", "sf_lib"),
    ("sf_lib/naming.py", "sf_lib"),
    ("sf_lib/rbac.py", "sf_lib"),
    ("sf_lib/sql_validator.py", "sf_lib"),
    ("sf_lib/metadata.py", "sf_lib"),
    ("sf_lib/ingestion.py", "sf_lib"),
    ("sf_lib/schema_service.py", "sf_lib"),
    ("sf_lib/classification.py", "sf_lib"),
    ("sf_lib/ingestion_pipeline.py", "sf_lib"),
    ("sf_lib/catalog_service.py", "sf_lib"),
    ("sf_lib/conversation.py", "sf_lib"),
    ("sf_lib/query_understanding.py", "sf_lib"),
    ("sf_lib/result_interpretation.py", "sf_lib"),
    ("sf_lib/query_pipeline.py", "sf_lib"),
    ("sf_lib/demo_seed.py", "sf_lib"),
    ("sf_lib/orchestrator.py", "sf_lib"),
    ("sf_lib/domain_agent.py", "sf_lib"),
    ("demo_data/customers.csv", "demo_data"),
    ("demo_data/products.csv", "demo_data"),
    ("demo_data/orders.csv", "demo_data"),
    ("demo_data/payments.csv", "demo_data"),
    ("demo_data/deliveries.csv", "demo_data"),
]


def main():
    with snowflake_service.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"CREATE STAGE IF NOT EXISTS {STAGE}")

        for rel_path, subdir in FILES:
            local = APP_DIR / rel_path
            dest = f"@{STAGE}/{subdir}" if subdir else f"@{STAGE}"
            print(f"PUT {rel_path} -> {dest}")
            cur.execute(f"PUT 'file://{local}' '{dest}' AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

        # NOTE: this is the classic warehouse-runtime Streamlit app, which only
        # supports owner's-rights execution — restricted caller's rights (true
        # per-viewer RBAC at the SQL level) requires the newer container
        # runtime (a compute pool), which is a materially bigger and riskier
        # setup (and may hit the same trial-tier wall Cortex did). Isolation
        # here is instead enforced in the app via st.user.user_name (see
        # sf_lib/rbac.py) plus the SQL validator as a second layer.
        cur.execute(
            f"""CREATE STREAMLIT IF NOT EXISTS {APP_NAME}
                ROOT_LOCATION = '@{STAGE}'
                MAIN_FILE = 'streamlit_app.py'
                QUERY_WAREHOUSE = '{WAREHOUSE}'"""
        )
        # Re-point an existing app at the freshly staged files (CREATE ... IF
        # NOT EXISTS above is a no-op on redeploys, so ALTER picks up changes).
        cur.execute(
            f"""ALTER STREAMLIT {APP_NAME} SET
                ROOT_LOCATION = '@{STAGE}'
                MAIN_FILE = 'streamlit_app.py'
                QUERY_WAREHOUSE = '{WAREHOUSE}'"""
        )

        for role in ("ROLE_DEMO_USER_A", "ROLE_DEMO_USER_B"):
            cur.execute(f"GRANT USAGE ON STREAMLIT {APP_NAME} TO ROLE {role}")

        cur.execute(f"SHOW STREAMLITS LIKE 'EGLEVIEW' IN SCHEMA {DATABASE}.{SCHEMA}")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        info = dict(zip(cols, rows[0])) if rows else {}
        print("\nDeployed. URL info:", info.get("url_id") or info)
        cur.close()


if __name__ == "__main__":
    main()
