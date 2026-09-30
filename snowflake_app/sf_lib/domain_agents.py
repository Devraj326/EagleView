"""Registry of specialized domain agents.

Each entry now corresponds to a REAL Cortex Agent object (`<KEY_UPPER>_AGENT`,
created by setup_domain_agents.py) plus one persistent Snowflake table per
domain per user schema (`table_name`) that accumulates rows across every
upload routed to that domain — new uploads either match its existing columns
or extend it via ALTER TABLE ADD COLUMN, they never replace it.

New domains can be added here (registry entry + rerun setup_domain_agents.py)
without touching pipeline code — N is not fixed at any particular count.
"""

DOMAIN_AGENTS: dict[str, dict] = {
    "inventory_agent": {
        "label": "Inventory Agent",
        "table_name": "INVENTORY_DATA",
        "dataset_types": ["inventory", "stock", "warehouse"],
        "concepts": [
            "product",
            "SKU",
            "quantity",
            "warehouse",
            "stock level",
            "reorder level",
            "inventory value",
            "supplier",
            "stock status",
        ],
    },
    "customer_agent": {
        "label": "Customer Agent",
        "table_name": "CUSTOMER_DATA",
        "dataset_types": ["customer", "user", "member"],
        "concepts": [
            "customer",
            "user id",
            "name",
            "email",
            "registration date",
            "location",
            "account status",
            "customer segment",
            "customer activity",
        ],
    },
    "financial_agent": {
        "label": "Finance Agent",
        "table_name": "FINANCIAL_DATA",
        "dataset_types": ["financial_transaction", "revenue", "expense", "payment"],
        "concepts": [
            "revenue",
            "expenses",
            "transactions",
            "profit",
            "margin",
            "landed cost",
            "cost",
            "currency",
            "transaction date",
            "account",
            "payment status",
            "refunds",
        ],
    },
    "order_agent": {
        "label": "Order Agent",
        "table_name": "ORDER_DATA",
        "dataset_types": ["order", "order_items", "sales"],
        "concepts": [
            "order",
            "order id",
            "customer",
            "order items",
            "product",
            "quantity",
            "price",
            "discount",
            "tax",
            "total amount",
            "order status",
            "order date",
            "payment status",
            "shipment",
            "delivery",
        ],
    },
    "delivery_agent": {
        "label": "Delivery Agent",
        "table_name": "DELIVERY_DATA",
        "dataset_types": ["delivery", "shipment", "logistics"],
        "concepts": [
            "shipment",
            "delivery",
            "pickup",
            "destination",
            "current location",
            "delivery status",
            "delivery date",
            "expected vs actual delivery",
            "ETA",
            "driver",
            "carrier",
            "delivery partner",
            "logistics provider",
            "delay",
            "on-time delivery",
            "delivery timeline",
        ],
    },
    "product_agent": {
        "label": "Product Agent",
        "table_name": "PRODUCT_DATA",
        "dataset_types": ["product", "catalog"],
        "concepts": ["product", "SKU", "category", "price", "description", "brand", "attributes"],
    },
    "supplier_agent": {
        "label": "Supplier Agent",
        "table_name": "SUPPLIER_DATA",
        "dataset_types": ["supplier", "procurement", "vendor"],
        "concepts": [
            "supplier",
            "vendor",
            "procurement",
            "purchase order",
            "lead time",
            "supplier reliability",
            "supplier rating",
            "contract",
            "supplier contact",
        ],
    },
}


def agent_catalog_text() -> str:
    lines = []
    for key, agent in DOMAIN_AGENTS.items():
        lines.append(f"- {key} ({agent['label']}): handles {', '.join(agent['concepts'])}")
    return "\n".join(lines)


def is_known_agent(agent_key: str) -> bool:
    return agent_key in DOMAIN_AGENTS


def table_name_for(agent_key: str) -> str:
    return DOMAIN_AGENTS[agent_key]["table_name"]


def cortex_agent_name(agent_key: str) -> str:
    return agent_key.upper()
