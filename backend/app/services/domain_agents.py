"""Registry of specialized domain agents.

Each agent is not a separate running process — it's a named persona with a
focused vocabulary/prompt fragment that the classification, schema, and query
services use to keep domain reasoning modular instead of one giant prompt.
New domains can be added here without touching the pipeline code.
"""

DOMAIN_AGENTS: dict[str, dict] = {
    "inventory_agent": {
        "label": "Inventory Agent",
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
        "label": "User/Customer Agent",
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
        "label": "Financial Agent",
        "dataset_types": ["financial_transaction", "revenue", "expense", "payment"],
        "concepts": [
            "revenue",
            "expenses",
            "transactions",
            "profit",
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
        "dataset_types": ["delivery", "shipment", "logistics"],
        "concepts": [
            "shipment",
            "delivery",
            "pickup",
            "destination",
            "current location",
            "delivery status",
            "delivery date",
            "ETA",
            "driver",
            "delivery partner",
            "logistics provider",
            "delay",
            "delivery timeline",
        ],
    },
    "product_agent": {
        "label": "Product Agent",
        "dataset_types": ["product", "catalog"],
        "concepts": ["product", "SKU", "category", "price", "description", "brand", "attributes"],
    },
}


def agent_catalog_text() -> str:
    lines = []
    for key, agent in DOMAIN_AGENTS.items():
        lines.append(f"- {key} ({agent['label']}): handles {', '.join(agent['concepts'])}")
    return "\n".join(lines)


def is_known_agent(agent_key: str) -> bool:
    return agent_key in DOMAIN_AGENTS
