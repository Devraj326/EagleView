import snowflake.connector
import os, sys
from pathlib import Path

# Load .env
env_path = Path(r"C:\Users\anujs\Downloads\Demo Data\SF_hackathon\EagleView\backend\.env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"')

account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
user = os.environ.get("SNOWFLAKE_USER", "")
password = os.environ.get("SNOWFLAKE_PASSWORD", "")
pk_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH", "")

print(f"Account: {account}")
print(f"User: {user}")
print(f"Has password: {bool(password)}")
print(f"Has key: {bool(pk_path)}")

if not account or not user:
    print("ERROR: Missing SNOWFLAKE_ACCOUNT or SNOWFLAKE_USER")
    sys.exit(1)

connect_params = dict(
    account=account,
    user=user,
    warehouse="COMPUTE_WH",
    database="EGLE_VIEW",
    schema="DEMO_A",
    role="ACCOUNTADMIN",
)

if pk_path and Path(pk_path).exists():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    pk_passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "")
    p_key = serialization.load_pem_private_key(
        Path(pk_path).read_bytes(),
        password=pk_passphrase.encode() if pk_passphrase else None,
        backend=default_backend(),
    )
    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    connect_params["private_key"] = pkb
elif password:
    connect_params["password"] = password
else:
    print("ERROR: No password or private key")
    sys.exit(1)

conn = snowflake.connector.connect(**connect_params)
cur = conn.cursor()

DEMO_DIR = Path(r"C:\Users\anujs\Downloads\Demo Data\SF_hackathon\EagleView\snowflake_app\demo_data")

TABLE_MAP = {
    "suppliers.csv": "SUPPLIER_DATA",
    "plants.csv": "PLANT_DATA",
    "parts.csv": "PARTS_DATA",
    "customers.csv": "CUSTOMER_DATA",
    "products.csv": "PRODUCT_DATA",
    "orders.csv": "ORDER_DATA",
    "payments.csv": "FINANCIAL_DATA",
    "deliveries.csv": "DELIVERY_DATA",
    "purchase_orders.csv": "PURCHASE_ORDER_DATA",
    "inbound_shipments.csv": "INBOUND_SHIPMENT_DATA",
    "inventory_snapshots.csv": "INVENTORY_SNAPSHOT_DATA",
}

for csv_file, table_name in TABLE_MAP.items():
    csv_path = DEMO_DIR / csv_file
    if not csv_path.exists():
        print(f"SKIP {csv_file}: not found")
        continue

    stage_path = f"@EGLE_VIEW.DEMO_A.LOAD_STAGE/{csv_file}"
    print(f"\nLoading {csv_file} -> {table_name}...")

    # PUT file to stage
    put_sql = f"PUT 'file://{csv_path.as_posix()}' @EGLE_VIEW.DEMO_A.LOAD_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
    cur.execute(put_sql)
    print(f"  PUT complete")

    # COPY INTO table
    copy_sql = f"""
    COPY INTO EGLE_VIEW.DEMO_A.{table_name}
    FROM {stage_path}
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1 NULL_IF = (''))
    ON_ERROR = 'CONTINUE'
    PURGE = TRUE
    """
    cur.execute(copy_sql)
    result = cur.fetchone()
    print(f"  COPY: {result}")

# Verify row counts
print("\n--- Row Counts ---")
for table_name in TABLE_MAP.values():
    cur.execute(f"SELECT COUNT(*) FROM EGLE_VIEW.DEMO_A.{table_name}")
    count = cur.fetchone()[0]
    print(f"  {table_name}: {count}")

cur.close()
conn.close()
print("\nDone!")
