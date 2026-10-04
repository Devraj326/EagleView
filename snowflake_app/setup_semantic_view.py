"""Deploy the supply-chain semantic view to Snowflake.

Reads the YAML template, substitutes the target schema, and creates
the semantic view via CREATE OR REPLACE SEMANTIC VIEW.

Usage:
    python setup_semantic_view.py [SCHEMA]    # default: DEMO_A
"""

import sys, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import snowflake_service  # noqa: E402

DATABASE = "EGLE_VIEW"
YAML_PATH = Path(__file__).resolve().parent / "ontology" / "sc_supply_chain.sv.yaml"


def deploy(schema: str = "DEMO_A"):
    yaml_raw = YAML_PATH.read_text(encoding="utf-8")
    yaml_body = yaml_raw.replace("{{SCHEMA}}", schema)

    sv_name = f'"{DATABASE}"."{schema}"."SC_SUPPLY_CHAIN"'
    sql = f"""
CREATE OR REPLACE SEMANTIC VIEW {sv_name}
  COMMENT = 'Supply chain ontology — governed metrics for OTD, fill rate, DOI, landed cost'
AS $$
{yaml_body}
$$;
"""

    with snowflake_service.get_connection() as conn:
        cur = conn.cursor()
        print(f"Creating semantic view {sv_name}...")
        cur.execute(sql)
        cur.execute(f"GRANT SELECT ON SEMANTIC VIEW {sv_name} TO ROLE PUBLIC")
        print("Semantic view deployed.")
        cur.close()


if __name__ == "__main__":
    schema = sys.argv[1] if len(sys.argv) > 1 else "DEMO_A"
    deploy(schema)
