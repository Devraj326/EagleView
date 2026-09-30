import re

_IDENT_SAFE = re.compile(r"[^A-Za-z0-9_]")


def safe_identifier(name: str, default: str = "COLUMN") -> str:
    """Sanitize an arbitrary string into a safe Snowflake unquoted identifier."""
    cleaned = _IDENT_SAFE.sub("_", (name or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = default
    if cleaned[0].isdigit():
        cleaned = f"C_{cleaned}"
    return cleaned.upper()[:128]
