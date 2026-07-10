"""SQL connectivity -- SQL Server (SQLAlchemy + pyodbc) or SQLite, per
Settings.sql_backend. See sql_dialect.py for the backend-aware helpers
that use whichever engine this returns."""
import datetime
import os
import sqlite3
import urllib.parse

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from config import Settings

# Python 3.12 deprecated sqlite3's default datetime/date adapters (a bare
# INSERT of a real datetime.datetime/date object emits a DeprecationWarning
# today, and would break outright on a future Python that removes them) --
# register explicit ones so bulkops.py/source_ingestion.py's log tables
# (StartedAt/CompletedAt etc., passed as real Python datetimes) keep working
# without relying on a default that's already on its way out.
sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat(sep=" "))
sqlite3.register_adapter(datetime.date, lambda d: d.isoformat())


def build_odbc_string(s: Settings) -> str:
    parts = [
        f"DRIVER={{{s.sql_driver}}}",
        f"SERVER={s.sql_server}",
        f"DATABASE={s.sql_database}",
        f"Encrypt={s.sql_encrypt}",
        f"TrustServerCertificate={s.sql_trust_cert}",
    ]
    if s.sql_trusted.lower() == "yes":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={s.sql_uid}")
        parts.append(f"PWD={s.sql_pwd}")
    return ";".join(parts)


def _make_mssql_engine(s: Settings) -> Engine:
    # NOTE: the SQL password (if any -- Windows/trusted auth needs none) ends
    # up inside the odbc_connect blob, not the URL's native user:pass@host
    # form -- so SQLAlchemy's own hide_password=True redaction (its default
    # logging/repr behavior) can't find and mask it. Nothing here sets
    # echo=True or prints/logs the engine or its .url today, and it must
    # stay that way -- do not add echo=True or debug-print this engine's URL
    # without first redacting PWD=... out of it, or the SQL Server password
    # will end up in cleartext in logs/console output.
    odbc = urllib.parse.quote_plus(build_odbc_string(s))
    # fast_executemany dramatically speeds up pandas.to_sql / executemany writes.
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={odbc}",
        fast_executemany=True,
    )


def _make_sqlite_engine(s: Settings) -> Engine:
    # One <schema>.db file per declared schema (SQL_SQLITE_SCHEMAS,
    # comma-separated) under SQL_SQLITE_DIR, each ATTACHed under its own
    # schema name on every new physical connection -- so an existing
    # `schema=schema` kwarg on pandas .to_sql()/.read_sql() calls elsewhere
    # in this codebase already means the right thing (SQLAlchemy's sqlite
    # dialect treats `schema=` as an attached-database alias), no call-site
    # changes needed. The base connection itself is a small bootstrap file,
    # not any one schema -- avoids "is dbo the main db or an attached one"
    # ambiguity; every schema, dbo included, is attached symmetrically.
    os.makedirs(s.sql_sqlite_dir, exist_ok=True)
    schemas = [x.strip() for x in s.sql_sqlite_schemas.split(",") if x.strip()]
    bootstrap_path = os.path.join(s.sql_sqlite_dir, "_bootstrap.db")

    engine = create_engine(f"sqlite:///{bootstrap_path}")

    @event.listens_for(engine, "connect")
    def _attach_schemas_and_tune(dbapi_conn, _):
        cx = dbapi_conn.cursor()
        for schema in schemas:
            schema_path = os.path.join(s.sql_sqlite_dir, f"{schema}.db")
            cx.execute(f"ATTACH DATABASE '{schema_path}' AS \"{schema}\"")
        # Real levers for write throughput at volume -- WAL lets reads
        # proceed during a write instead of blocking; NORMAL sync trades a
        # small durability window (a hard crash could lose the last commit)
        # for real speed, an acceptable tradeoff for a migration staging DB.
        cx.execute("PRAGMA journal_mode=WAL")
        cx.execute("PRAGMA synchronous=NORMAL")
        cx.close()

    return engine


def make_engine(s: Settings) -> Engine:
    if s.sql_backend == "sqlite":
        return _make_sqlite_engine(s)
    if s.sql_backend == "mssql":
        return _make_mssql_engine(s)
    raise ValueError(f"Unsupported SQL_BACKEND: {s.sql_backend!r} (expected 'mssql' or 'sqlite')")
