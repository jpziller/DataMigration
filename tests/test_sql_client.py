"""Coverage for sql_client.py's SQLite engine construction -- identifier
validation and the connect-time pragma/ATTACH setup."""
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
