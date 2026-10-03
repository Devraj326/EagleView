import re

# Matches a single-quoted string literal, including Snowflake's doubled-quote
# escape for a literal quote inside one ('it''s fine'). Stripped before the
# forbidden-keyword scan so a legitimate value like 'DELETE_REQUESTED' in a
# WHERE clause doesn't false-positive as the DELETE keyword.
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")

# A bare identifier (optionally quoted) immediately preceding `AS (` in a
# WITH clause — i.e. a CTE name, which is legitimately unqualified and must
# not be treated as a table reference requiring db.schema.table.
_CTE_NAME_RE = re.compile(
    r'(?:\bWITH\b|,)\s*(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+))\s*(?:\([^)]*\))?\s+AS\s*\(',
    re.IGNORECASE,
)

# A FROM/JOIN clause's table reference: captures the dotted identifier chain
# that follows, stopping before a `(` (subquery), `AS`/whitespace+alias, or
# end of clause.
_FROM_JOIN_REF_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+((?:"[A-Za-z0-9_]+"|[A-Za-z0-9_]+)(?:\s*\.\s*(?:"[A-Za-z0-9_]+"|[A-Za-z0-9_]+))*)',
    re.IGNORECASE,
)

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


def _unqualified_table_refs(stmt: str) -> list[str]:
    """Returns every FROM/JOIN table reference that is NOT fully qualified as
    db.schema.table (and isn't a CTE name or a subquery/table-function call).

    The SQL generator is instructed to always fully-qualify every real table,
    but that's a prompt instruction, not an enforced guarantee — the existing
    qualified-reference check below only validates refs that already happen
    to be 3-part; it never looks at whether a FROM/JOIN clause is qualified
    at all. An unqualified reference would silently resolve against whatever
    the session's own ambient default database/schema is at execution time
    instead of being checked against the allowlist — this closes that gap.
    """
    cte_names = {(m.group(1) or m.group(2)).upper() for m in _CTE_NAME_RE.finditer(stmt)}

    bad_refs = []
    for match in _FROM_JOIN_REF_RE.finditer(stmt):
        ref = match.group(1)
        # Immediately followed by `(` (ignoring whitespace) -> a table
        # function call or subquery alias (e.g. TABLE(FLATTEN(...)) or a
        # derived table), not a plain table reference.
        if stmt[match.end():].lstrip().startswith("("):
            continue
        parts = [p for p in re.split(r"\s*\.\s*", ref) if p]
        bare_name = parts[0].strip('"').upper()
        if len(parts) == 1 and bare_name in cte_names:
            continue
        if len(parts) < 3:
            bad_refs.append(ref)
    return bad_refs


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

    stmt_no_literals = _STRING_LITERAL_RE.sub("''", stmt)

    forbidden = _FORBIDDEN_RE.search(stmt_no_literals)
    if forbidden:
        raise SqlValidationError(f"Disallowed keyword in query: {forbidden.group(1).upper()}")

    unqualified = _unqualified_table_refs(stmt_no_literals)
    if unqualified:
        raise SqlValidationError(
            f"Table reference(s) must be fully qualified as database.schema.table: {', '.join(unqualified)}"
        )

    for match in _QUALIFIED_REF_RE.finditer(stmt):
        groups = [g for g in match.groups() if g]
        if len(groups) < 3:
            # A 2-part dotted reference is always alias.column here: the SQL
            # generator is instructed to fully-qualify every real table as
            # db.schema.table (3-part), so 2-part can't be a genuine schema
            # reference and would otherwise false-positive on JOIN aliases
            # like T2.ORDER_ID.
            continue
        db, schema, table = groups[0], groups[1], groups[2]
        if db.upper() != allowed_database.upper():
            raise SqlValidationError(f"Query references an unauthorized database: {db}")
        if schema.upper() != allowed_schema.upper():
            raise SqlValidationError(f"Query references an unauthorized schema: {schema}")
        if allowed_tables is not None and table.upper() not in allowed_tables:
            raise SqlValidationError(f"Query references an unauthorized table: {table}")
