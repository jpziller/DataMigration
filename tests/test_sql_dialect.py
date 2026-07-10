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
from sql_dialect import MssqlDialect, SqliteDialect


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


def test_qualify_and_quote_ident_match_each_backend_convention():
    assert MssqlDialect().qualify("dbo", "Account") == "[dbo].[Account]"
    assert MssqlDialect().quote_ident("Sort") == "[Sort]"
    assert SqliteDialect().qualify("dbo", "Account") == '"dbo"."Account"'
    assert SqliteDialect().quote_ident("Sort") == '"Sort"'


def test_for_engine_rejects_unsupported_dialect_name():
    class _FakeDialectEngine:
        class dialect:
            name = "postgresql"

    try:
        sql_dialect.for_engine(_FakeDialectEngine())
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Unsupported SQL backend" in str(e)
