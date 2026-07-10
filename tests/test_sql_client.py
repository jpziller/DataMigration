"""Coverage for sql_client.py's SQLite engine construction -- identifier
validation and the connect-time pragma/ATTACH setup."""
import datetime

import pandas as pd
import pytest
from sqlalchemy import text

import sql_client
from config import Settings


def test_bad_schema_name_with_quote_char_raises_clearly(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas='dbo,ev"il',
    )
    with pytest.raises(ValueError, match="quote character"):
        sql_client.make_engine(s)


def test_bad_sqlite_dir_with_quote_char_raises_clearly(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "ev'il"),
        sql_sqlite_schemas="dbo",
    )
    with pytest.raises(ValueError, match="quote character"):
        sql_client.make_engine(s)


def test_sqlite_engine_connects_and_applies_pragmas(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    engine = sql_client.make_engine(s)
    with engine.connect() as cx:
        assert cx.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert cx.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        # The "dbo" schema is genuinely attached, not just configured --
        # a real table can be created in it.
        cx.execute(text('CREATE TABLE "dbo"."Probe" (x INTEGER)'))
        cx.commit()
    with engine.connect() as cx:
        assert cx.execute(text('SELECT COUNT(*) FROM "dbo"."Probe"')).scalar() == 0


def test_unsupported_backend_raises_clearly(tmp_path):
    s = Settings(sql_backend="mongodb")
    with pytest.raises(ValueError, match="Unsupported SQL_BACKEND"):
        sql_client.make_engine(s)


def test_datetime_adapter_uses_t_separator_for_raw_parameterized_writes(tmp_path):
    """Regression test for a real bug found via a live migration run: a
    space-separated datetime string (Python's isoformat(sep=" ") default)
    is a genuine XSD dateTime parse failure against Salesforce's Bulk API
    ("is not a valid value for the type xsd:dateTime"), not just
    non-canonical. Covers the raw-parameterized-query path this adapter
    actually affects (bulkops.py/source_ingestion.py's own log-row
    inserts, via text()+bound params) -- pandas .to_sql() goes through
    SQLAlchemy's own DateTime type instead and needs a separate fix, see
    test_snowfakery_data.py's coverage of that path."""
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    engine = sql_client.make_engine(s)
    dt = datetime.datetime(2025, 8, 3, 17, 16, 48)
    with engine.begin() as cx:
        cx.execute(text('CREATE TABLE "dbo"."Probe" (StartedAt TEXT)'))
        cx.execute(text('INSERT INTO "dbo"."Probe" (StartedAt) VALUES (:dt)'), {"dt": dt})
    with engine.connect() as cx:
        stored = cx.execute(text('SELECT StartedAt FROM "dbo"."Probe"')).scalar()
    assert stored == "2025-08-03T17:16:48"
    assert " " not in stored
