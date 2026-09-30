import hashlib
import re


def user_schema_name(user_id: str) -> str:
    """Derive a stable, non-reversible Snowflake schema name for a user.

    Never expose the raw internal user id in Snowflake object names.
    """
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:20]
    return f"USER_{digest.upper()}"


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
