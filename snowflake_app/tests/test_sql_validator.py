import pytest

from sf_lib.sql_validator import SqlValidationError, validate_read_only_sql

DB = "EGLE_VIEW"
SCHEMA = "USER_ABC123"


def test_valid_fully_qualified_select_passes():
    validate_read_only_sql(
        f'SELECT * FROM "{DB}"."{SCHEMA}"."CUSTOMER_DATA"', DB, SCHEMA, {"CUSTOMER_DATA"}
    )


def test_valid_cte_passes():
    sql = (
        f'WITH recent AS (SELECT * FROM "{DB}"."{SCHEMA}"."ORDER_DATA" WHERE ORDER_DATE > \'2024-01-01\') '
        "SELECT COUNT(*) FROM recent"
    )
    validate_read_only_sql(sql, DB, SCHEMA, {"ORDER_DATA"})


def test_join_alias_dot_column_not_flagged_as_unauthorized_schema():
    sql = (
        f'SELECT t1.ORDER_ID FROM "{DB}"."{SCHEMA}"."ORDER_DATA" t1 '
        f'JOIN "{DB}"."{SCHEMA}"."DELIVERY_DATA" t2 ON t1.ORDER_ID = t2.ORDER_ID'
    )
    validate_read_only_sql(sql, DB, SCHEMA, {"ORDER_DATA", "DELIVERY_DATA"})


def test_rejects_non_select():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(f'DELETE FROM "{DB}"."{SCHEMA}"."CUSTOMER_DATA"', DB, SCHEMA)


def test_rejects_stacked_statements():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(
            f'SELECT 1; DROP TABLE "{DB}"."{SCHEMA}"."CUSTOMER_DATA"', DB, SCHEMA
        )


def test_rejects_forbidden_keyword_even_mid_query():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(
            f'SELECT * FROM "{DB}"."{SCHEMA}"."CUSTOMER_DATA"; UPDATE X SET Y=1', DB, SCHEMA
        )


def test_rejects_unauthorized_database():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(f'SELECT * FROM OTHER_DB."{SCHEMA}"."CUSTOMER_DATA"', DB, SCHEMA)


def test_rejects_unauthorized_schema():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(f'SELECT * FROM "{DB}".OTHER_SCHEMA."CUSTOMER_DATA"', DB, SCHEMA)


def test_rejects_unauthorized_table_not_in_allowlist():
    with pytest.raises(SqlValidationError):
        validate_read_only_sql(
            f'SELECT * FROM "{DB}"."{SCHEMA}"."SOME_OTHER_TABLE"', DB, SCHEMA, {"CUSTOMER_DATA"}
        )


# --- edge cases found and fixed in this pass ---


def test_forbidden_keyword_inside_string_literal_is_not_a_false_positive():
    """A legitimate value like 'DELETE_REQUESTED' must not trip the
    forbidden-keyword scan just because the word DELETE appears inside a
    quoted string, not as a SQL keyword.
    """
    sql = f"""SELECT * FROM "{DB}"."{SCHEMA}"."ORDER_DATA" WHERE STATUS = 'DELETE_REQUESTED'"""
    validate_read_only_sql(sql, DB, SCHEMA, {"ORDER_DATA"})


def test_forbidden_keyword_survives_doubled_quote_escape_in_literal():
    sql = f"""SELECT * FROM "{DB}"."{SCHEMA}"."ORDER_DATA" WHERE NOTE = 'it''s a DROP-off point'"""
    validate_read_only_sql(sql, DB, SCHEMA, {"ORDER_DATA"})


def test_rejects_unqualified_table_reference():
    """Previously, an unqualified FROM clause (e.g. a lazy model response
    that didn't bother to fully-qualify the table) was never checked against
    the allowlist at all — the qualified-ref regex simply never matched it,
    so it silently passed validation and would have run against whatever the
    session's own ambient default schema happened to be.
    """
    with pytest.raises(SqlValidationError, match="fully qualified"):
        validate_read_only_sql("SELECT * FROM CUSTOMER_DATA", DB, SCHEMA, {"CUSTOMER_DATA"})


def test_rejects_two_part_unqualified_reference():
    with pytest.raises(SqlValidationError, match="fully qualified"):
        validate_read_only_sql(f'SELECT * FROM "{SCHEMA}"."CUSTOMER_DATA"', DB, SCHEMA, {"CUSTOMER_DATA"})


def test_cte_self_reference_is_not_flagged_as_unqualified_table():
    """A CTE name used unqualified in a later clause (standard SQL — that's
    the whole point of a CTE) must not be rejected as an unqualified table
    reference.
    """
    sql = (
        f'WITH recent AS (SELECT * FROM "{DB}"."{SCHEMA}"."ORDER_DATA"), '
        "totals AS (SELECT COUNT(*) AS c FROM recent) "
        "SELECT * FROM totals"
    )
    validate_read_only_sql(sql, DB, SCHEMA, {"ORDER_DATA"})
