"""Coverage for sql_dialect.py -- had zero direct tests despite being the
central seam every backend-aware module routes through. Focused here on
normalize_datetime_columns(), a real bug fix (see ROADMAP.md #28): pandas
.to_sql() writes a datetime64 column through SQLAlchemy's own DateTime
type, not sqlite3's registered adapter, so it needed its own fix separate
from sql_client.py's adapter registration.
"""
import datetime

import pandas as pd

import sql_dialect
from sql_dialect import MssqlDialect, PostgresDialect, SqliteDialect


def test_sqlite_normalize_datetime_columns_uses_t_separator_no_fraction():
    df = pd.DataFrame({
        "Name": ["Acme", "Globex"],
        "CreatedAt": pd.to_datetime(["2025-08-03 17:16:48", "2026-01-01 00:00:00"]),
    })
    out = SqliteDialect().normalize_datetime_columns(df)
    assert list(out["CreatedAt"]) == ["2025-08-03T17:16:48", "2026-01-01T00:00:00"]
    assert out["Name"].tolist() == ["Acme", "Globex"]  # non-datetime columns untouched


def test_sqlite_normalize_datetime_columns_preserves_nulls():
    df = pd.DataFrame({"CreatedAt": pd.to_datetime(["2025-08-03 17:16:48", None])})
    out = SqliteDialect().normalize_datetime_columns(df)
    assert out["CreatedAt"].iloc[0] == "2025-08-03T17:16:48"
    assert pd.isna(out["CreatedAt"].iloc[1])


def test_mssql_normalize_datetime_columns_is_a_no_op():
    df = pd.DataFrame({"CreatedAt": pd.to_datetime(["2025-08-03 17:16:48"])})
    out = MssqlDialect().normalize_datetime_columns(df)
    assert out["CreatedAt"].iloc[0] == df["CreatedAt"].iloc[0]
    assert pd.api.types.is_datetime64_any_dtype(out["CreatedAt"])


def test_postgres_normalize_datetime_columns_is_a_no_op():
    df = pd.DataFrame({"CreatedAt": pd.to_datetime(["2025-08-03 17:16:48"])})
    out = PostgresDialect().normalize_datetime_columns(df)
    assert out["CreatedAt"].iloc[0] == df["CreatedAt"].iloc[0]
    assert pd.api.types.is_datetime64_any_dtype(out["CreatedAt"])


def test_qualify_and_quote_ident_match_each_backend_convention():
    assert MssqlDialect().qualify("dbo", "Account") == "[dbo].[Account]"
    assert MssqlDialect().quote_ident("Sort") == "[Sort]"
    assert SqliteDialect().qualify("dbo", "Account") == '"dbo"."Account"'
    assert SqliteDialect().quote_ident("Sort") == '"Sort"'
    assert PostgresDialect().qualify("dbo", "Account") == '"dbo"."Account"'
    assert PostgresDialect().quote_ident("Sort") == '"Sort"'


def test_postgres_create_table_as_select_and_select_top_n():
    d = PostgresDialect()
    assert (
        d.create_table_as_select_sql("dbo", "Account_Retry", "*", "FROM \"dbo\".\"Account_Load\"")
        == 'CREATE TABLE "dbo"."Account_Retry" AS SELECT * FROM "dbo"."Account_Load"'
    )
    assert d.select_top_n_sql("*", 'FROM "dbo"."Account"', 10) == 'SELECT * FROM "dbo"."Account" LIMIT 10'


def test_postgres_autoincrement_pk_column_ddl_uses_identity_syntax():
    assert (
        PostgresDialect().autoincrement_pk_column_ddl("LogId")
        == "LogId INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    )


def test_postgres_sf_type_to_sql_matches_mssql_granularity_with_postgres_names():
    d = PostgresDialect()
    assert d.sf_type_to_sql({"type": "id"}) == "VARCHAR(18)"
    assert d.sf_type_to_sql({"type": "string", "length": 80}) == "VARCHAR(80)"
    assert d.sf_type_to_sql({"type": "string", "length": 0}) == "VARCHAR(4000)"
    assert d.sf_type_to_sql({"type": "textarea"}) == "TEXT"
    assert d.sf_type_to_sql({"type": "boolean"}) == "BOOLEAN"
    assert d.sf_type_to_sql({"type": "int"}) == "INTEGER"
    assert d.sf_type_to_sql({"type": "currency", "precision": 18, "scale": 2}) == "NUMERIC(18,2)"
    assert d.sf_type_to_sql({"type": "double", "precision": 0, "scale": 0}) == "DOUBLE PRECISION"
    assert d.sf_type_to_sql({"type": "date"}) == "DATE"
    assert d.sf_type_to_sql({"type": "datetime"}) == "TIMESTAMP"
    assert d.sf_type_to_sql({"type": "time"}) == "TIME"
    assert d.sf_type_to_sql({"type": "base64"}) == "BYTEA"
    assert d.sf_type_to_sql({"type": "reference"}) == "VARCHAR(18)"


def test_pick_type_selects_the_right_backend_slot():
    assert MssqlDialect().pick_type("DATETIME2", "TEXT", "TIMESTAMP") == "DATETIME2"
    assert SqliteDialect().pick_type("DATETIME2", "TEXT", "TIMESTAMP") == "TEXT"
    assert PostgresDialect().pick_type("DATETIME2", "TEXT", "TIMESTAMP") == "TIMESTAMP"


def test_for_engine_resolves_postgresql_to_postgres_dialect():
    class _FakeDialectEngine:
        class dialect:
            name = "postgresql"

    assert isinstance(sql_dialect.for_engine(_FakeDialectEngine()), PostgresDialect)


def test_lower_keys_lowercases_every_key():
    assert sql_dialect.lower_keys({"LogId": 5, "ObjectName": "Account"}) == {"logid": 5, "objectname": "Account"}


def test_lower_keys_is_idempotent_on_an_already_lowercase_dict():
    # Simulates a real Postgres result mapping, where an unquoted column
    # comes back lowercased regardless of the originally-declared case --
    # a caller that already lowered a row and passes it to a function
    # that lowers again (see orchestrator.py's _row_to_current()) must
    # get the same result back, not an error or a double-transform.
    assert sql_dialect.lower_keys({"logid": 5}) == {"logid": 5}


def test_for_engine_rejects_unsupported_dialect_name():
    class _FakeDialectEngine:
        class dialect:
            name = "oracle"

    try:
        sql_dialect.for_engine(_FakeDialectEngine())
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Unsupported SQL backend" in str(e)
