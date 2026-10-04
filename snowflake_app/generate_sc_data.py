"""Generate referentially consistent supply-chain synthetic data.

Run once:  python generate_sc_data.py
Outputs CSVs into  demo_data/  (overwrites existing + creates new ones).
"""

import csv, random, os, math
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

OUT = Path(__file__).resolve().parent / "demo_data"
OUT.mkdir(exist_ok=True)

# ── helpers ────────────────────────────────────────────────────────────
def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def rand_dt(start, end):
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=random.randint(0, int(delta)))

def write_csv(name, rows, fieldnames):
    path = OUT / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")

NOW = datetime(2026, 7, 15)
START = datetime(2026, 1, 1)

# ── 1. SUPPLIERS (200) ────────────────────────────────────────────────
print("Generating suppliers...")
countries = ["India", "China", "Vietnam", "Germany", "USA", "Japan", "South Korea", "Taiwan", "Mexico", "Thailand"]
supplier_tiers = ["Strategic", "Preferred", "Approved", "Probationary"]
suppliers = []
for i in range(200):
    sid = f"SUP{i:05d}"
    suppliers.append({
        "supplier_id": sid,
        "supplier_name": f"Supplier_{sid}",
        "country": random.choice(countries),
        "lead_time_days": random.choice([7, 10, 14, 21, 30, 45, 60]),
        "reliability_score": round(random.uniform(0.55, 0.99), 2),
        "contract_tier": random.choice(supplier_tiers),
        "payment_terms_days": random.choice([30, 45, 60, 90]),
        "contact_email": f"contact.{sid.lower()}@supplier.example.com",
    })
write_csv("suppliers.csv", suppliers, list(suppliers[0].keys()))
supplier_ids = [s["supplier_id"] for s in suppliers]

# ── 2. PLANTS / WAREHOUSES (30) ──────────────────────────────────────
print("Generating plants...")
plant_types = ["Manufacturing", "Distribution Center", "3PL Warehouse"]
plant_cities = [
    ("Mumbai", "India"), ("Delhi", "India"), ("Chennai", "India"),
    ("Bengaluru", "India"), ("Hyderabad", "India"), ("Pune", "India"),
    ("Ahmedabad", "India"), ("Kolkata", "India"), ("Jaipur", "India"),
    ("Coimbatore", "India"), ("Shanghai", "China"), ("Shenzhen", "China"),
    ("Ho Chi Minh City", "Vietnam"), ("Hanoi", "Vietnam"),
    ("Frankfurt", "Germany"), ("Munich", "Germany"),
    ("Chicago", "USA"), ("Los Angeles", "USA"),
    ("Tokyo", "Japan"), ("Osaka", "Japan"),
    ("Seoul", "South Korea"), ("Taipei", "Taiwan"),
    ("Monterrey", "Mexico"), ("Guadalajara", "Mexico"),
    ("Bangkok", "Thailand"), ("Surat", "India"),
    ("Nagpur", "India"), ("Lucknow", "India"),
    ("Kochi", "India"), ("Chandigarh", "India"),
]
plants = []
for i in range(30):
    pid = f"PLT{i:04d}"
    city, country = plant_cities[i]
    plants.append({
        "plant_id": pid,
        "plant_name": f"{city} {plant_types[i % 3]}",
        "city": city,
        "country": country,
        "plant_type": plant_types[i % 3],
        "capacity_units": random.choice([5000, 10000, 20000, 50000, 100000]),
    })
write_csv("plants.csv", plants, list(plants[0].keys()))
plant_ids = [p["plant_id"] for p in plants]
india_plant_ids = [p["plant_id"] for p in plants if p["country"] == "India"]

# ── 3. PARTS (2000) ──────────────────────────────────────────────────
print("Generating parts...")
commodity_groups = [
    "Electronics", "Mechanical", "Packaging", "Raw Material",
    "Chemical", "Textile", "Plastic", "Metal", "Glass", "Rubber",
]
hs_prefixes = ["8471", "8542", "7318", "3926", "6109", "7010", "4016", "3904", "2918", "8544"]
parts = []
for i in range(2000):
    partid = f"PART{i:05d}"
    cg = commodity_groups[i % len(commodity_groups)]
    parts.append({
        "part_id": partid,
        "part_name": f"{cg}_Component_{i:04d}",
        "commodity_group": cg,
        "hs_code": f"{hs_prefixes[i % len(hs_prefixes)]}.{random.randint(10,99)}.{random.randint(1000,9999)}",
        "unit_cost": round(random.uniform(5, 5000), 2),
        "weight_kg": round(random.uniform(0.01, 50), 2),
        "supplier_id": random.choice(supplier_ids),
    })
write_csv("parts.csv", parts, list(parts[0].keys()))
part_ids = [p["part_id"] for p in parts]
part_cost = {p["part_id"]: p["unit_cost"] for p in parts}
part_supplier = {p["part_id"]: p["supplier_id"] for p in parts}

# ── 4. PURCHASE ORDERS (5000) ────────────────────────────────────────
print("Generating purchase orders...")
purchase_orders = []
for i in range(5000):
    po_id = f"PO{i:06d}"
    part = random.choice(parts)
    plant = random.choice(plants)
    sup_id = part["supplier_id"]
    sup = next(s for s in suppliers if s["supplier_id"] == sup_id)
    lead = sup["lead_time_days"]

    order_date = rand_dt(START, NOW - timedelta(days=lead + 5))
    promised_date = order_date + timedelta(days=lead)
    # ~80% on time, ~20% late receipt
    if random.random() < 0.80:
        receipt_date = promised_date - timedelta(days=random.randint(0, 3))
    else:
        receipt_date = promised_date + timedelta(days=random.randint(1, 15))

    qty_ordered = random.randint(50, 5000)
    # ~85% full fill, ~15% partial
    if random.random() < 0.85:
        qty_received = qty_ordered
    else:
        qty_received = max(1, int(qty_ordered * random.uniform(0.4, 0.95)))

    unit_cost = part["unit_cost"]
    freight = round(unit_cost * qty_ordered * random.uniform(0.02, 0.08), 2)
    duty_pct = round(random.choice([0, 0, 0, 5, 7.5, 10, 12.5, 15, 18]), 1)
    insurance = round(unit_cost * qty_ordered * random.uniform(0.005, 0.02), 2)

    purchase_orders.append({
        "po_id": po_id,
        "supplier_id": sup_id,
        "part_id": part["part_id"],
        "plant_id": plant["plant_id"],
        "order_date": ts(order_date),
        "promised_date": ts(promised_date),
        "receipt_date": ts(receipt_date),
        "qty_ordered": qty_ordered,
        "qty_received": qty_received,
        "unit_cost": unit_cost,
        "freight_cost": freight,
        "duty_pct": duty_pct,
        "insurance_cost": insurance,
        "po_status": "Received" if receipt_date <= NOW else "In Transit",
    })
write_csv("purchase_orders.csv", purchase_orders, list(purchase_orders[0].keys()))

# ── 5. INBOUND SHIPMENTS (3000) ─────────────────────────────────────
print("Generating inbound shipments...")
carriers = ["DHL", "Maersk", "FedEx Freight", "DB Schenker", "Kuehne+Nagel", "BlueDart Cargo", "Delhivery B2B"]
inbound_shipments = []
used_pos = random.sample(purchase_orders, min(3000, len(purchase_orders)))
for i, po in enumerate(used_pos):
    ship_id = f"SHIP{i:06d}"
    order_dt = datetime.strptime(po["order_date"], "%Y-%m-%d %H:%M:%S")
    ship_date = order_dt + timedelta(days=random.randint(1, 5))
    receipt_dt = datetime.strptime(po["receipt_date"], "%Y-%m-%d %H:%M:%S")
    expected_arrival = datetime.strptime(po["promised_date"], "%Y-%m-%d %H:%M:%S")
    # actual arrival = receipt date of PO
    actual_arrival = receipt_dt

    status = "Delivered" if actual_arrival <= NOW else "In Transit"
    if actual_arrival > expected_arrival:
        status = "Delivered Late" if actual_arrival <= NOW else "Delayed"

    inbound_shipments.append({
        "shipment_id": ship_id,
        "po_id": po["po_id"],
        "supplier_id": po["supplier_id"],
        "plant_id": po["plant_id"],
        "ship_date": ts(ship_date),
        "expected_arrival": ts(expected_arrival),
        "actual_arrival": ts(actual_arrival) if actual_arrival <= NOW else "",
        "carrier": random.choice(carriers),
        "freight_cost": po["freight_cost"],
        "shipment_status": status,
    })
write_csv("inbound_shipments.csv", inbound_shipments, list(inbound_shipments[0].keys()))

# ── 6. INVENTORY SNAPSHOTS (50000) ──────────────────────────────────
print("Generating inventory snapshots...")
# Daily snapshots for 60 days, ~833 part-plant combos sampled
inventory = []
tracked_combos = [(random.choice(part_ids), random.choice(india_plant_ids)) for _ in range(833)]
tracked_combos = list(set(tracked_combos))  # dedupe
for day_offset in range(60):
    snap_date = (NOW - timedelta(days=59) + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    for part_id, plant_id in tracked_combos:
        on_hand = random.randint(0, 8000)
        allocated = min(on_hand, random.randint(0, int(on_hand * 0.6) + 1))
        in_transit = random.randint(0, 2000)
        reorder = random.randint(200, 2000)
        safety = int(reorder * 0.5)
        inventory.append({
            "snapshot_date": snap_date,
            "plant_id": plant_id,
            "part_id": part_id,
            "qty_on_hand": on_hand,
            "qty_allocated": allocated,
            "qty_in_transit": in_transit,
            "reorder_point": reorder,
            "safety_stock": safety,
        })
write_csv("inventory_snapshots.csv", inventory, list(inventory[0].keys()))

# ── 7. ENRICH EXISTING CSVs ─────────────────────────────────────────
print("Enriching existing CSVs...")

# 7a. Enrich orders.csv — add plant_id, promised_delivery_date, requested_qty, shipped_qty
orders_path = OUT / "orders.csv"
with open(orders_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    orig_orders = list(reader)

enriched_orders = []
for row in orig_orders:
    order_dt = datetime.strptime(row["order_dt"], "%Y-%m-%d %H:%M:%S")
    promised_dt = order_dt + timedelta(days=random.randint(3, 14))
    req_qty = int(row["qty"])
    # ~80% full ship, ~20% partial
    if random.random() < 0.80:
        shipped_qty = req_qty
    else:
        shipped_qty = max(1, int(req_qty * random.uniform(0.5, 0.95)))

    row["plant_id"] = random.choice(india_plant_ids)
    row["promised_delivery_dt"] = ts(promised_dt)
    row["requested_qty"] = req_qty
    row["shipped_qty"] = shipped_qty
    enriched_orders.append(row)

order_base = ["order_id", "cust_id", "prod_id", "qty", "unit_price", "discount_pct", "tax_pct", "total_amt", "order_dt", "order_status", "payment_status"]
order_fields = order_base + ["plant_id", "promised_delivery_dt", "requested_qty", "shipped_qty"]
write_csv("orders.csv", enriched_orders, order_fields)

# 7b. Enrich products.csv — add supplier_id, unit_cost_cogs, weight_kg
products_path = OUT / "products.csv"
with open(products_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    orig_products = list(reader)

enriched_products = []
for row in orig_products:
    row["supplier_id"] = random.choice(supplier_ids)
    row["unit_cost_cogs"] = round(float(row["unit_price"]) * random.uniform(0.3, 0.7), 2)
    row["weight_kg"] = round(random.uniform(0.1, 25), 2)
    enriched_products.append(row)

prod_base = ["prod_id", "prod_name", "category", "brand", "unit_price"]
prod_fields = prod_base + ["supplier_id", "unit_cost_cogs", "weight_kg"]
write_csv("products.csv", enriched_products, prod_fields)

# 7c. Enrich deliveries.csv — add freight_cost, shipment_type, promised_delivery_dt
deliveries_path = OUT / "deliveries.csv"
with open(deliveries_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    orig_deliveries = list(reader)

enriched_deliveries = []
for row in orig_deliveries:
    eta = datetime.strptime(row["eta_dt"], "%Y-%m-%d %H:%M:%S")
    row["freight_cost"] = round(random.uniform(50, 2000), 2)
    row["shipment_type"] = "Outbound"
    row["promised_delivery_dt"] = ts(eta - timedelta(days=random.randint(0, 2)))
    enriched_deliveries.append(row)

del_base = ["order_id", "cust_id", "pickup_loc", "destination", "curr_location", "delivery_status", "partner", "driver_name", "eta_dt", "actual_delivery_dt"]
del_fields = del_base + ["freight_cost", "shipment_type", "promised_delivery_dt"]
write_csv("deliveries.csv", enriched_deliveries, del_fields)

print("\nDone! All supply-chain CSVs generated in demo_data/")
