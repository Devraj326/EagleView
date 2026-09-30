import re

_FORBIDDEN_KEYWORDS = [
    "DROP",
    "DELETE",
    "TRUNCATE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "MERGE",
    "CREATE",
    "GRANT",
    "REVOKE",
    "CALL",
    "COPY",
    "PUT",
    "GET",
    "EXECUTE",
    "UNLOAD",
]
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)

# db.schema.table or schema.table, optionally quoted identifiers
_QUALIFIED_REF_RE = re.compile(
    r'(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+))\s*\.\s*(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+))'
    r'(?:\s*\.\s*(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+)))?'
)


class SqlValidationError(Exception):
    pass


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate_read_only_sql(
    sql: str, allowed_database: str, allowed_schema: str, allowed_tables: set[str] | None = None
) -> None:
    """Raises SqlValidationError if the SQL is anything other than a single
    read-only SELECT/WITH statement scoped to the user's own Snowflake schema
    (and, if given, an explicit allowlist of table names within it).
    """
    if not sql or not sql.strip():
        raise SqlValidationError("Generated SQL is empty")

    cleaned = _strip_comments(sql).strip()
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) != 1:
        raise SqlValidationError("Only a single SQL statement is allowed")

    stmt = statements[0]
    first_word = re.match(r"^\s*([A-Za-z]+)", stmt)
    if not first_word or first_word.group(1).upper() not in ("SELECT", "WITH"):
        raise SqlValidationError("Only read-only SELECT/WITH queries are allowed")

    forbidden = _FORBIDDEN_RE.search(stmt)
    if forbidden:
        raise SqlValidationError(f"Disallowed keyword in query: {forbidden.group(1).upper()}")

    for match in _QUALIFIED_REF_RE.finditer(stmt):
        groups = [g for g in match.groups() if g]
        if len(groups) < 2:
            continue
        # 3-part db.schema.table -> groups = [db, schema, table]; 2-part schema.table -> [schema, table]
        if len(groups) >= 3:
            db, schema, table = groups[0], groups[1], groups[2]
            if db.upper() != allowed_database.upper():
                raise SqlValidationError(f"Query references an unauthorized database: {db}")
            if schema.upper() != allowed_schema.upper():
                raise SqlValidationError(f"Query references an unauthorized schema: {schema}")
            if allowed_tables is not None and table.upper() not in allowed_tables:
                raise SqlValidationError(f"Query references an unauthorized table: {table}")
        else:
            schema = groups[0]
            if schema.upper() not in (allowed_schema.upper(), allowed_database.upper()):
                raise SqlValidationError(f"Query references an unauthorized schema: {schema}")
