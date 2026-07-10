"""Backend-aware SQL dialect helpers (SQL Server + SQLite).

Every call site that used to build raw T-SQL by hand -- OBJECT_ID/
COL_LENGTH existence checks, [schema].[table] bracket-quoted identifiers,
SELECT ... INTO, TOP (n), IDENTITY(1,1) -- assumed SQL Server specifically.
This module gives bulkops.py/replicate.py/batch_advisor.py a single seam to
call through instead.

Keyed off the real engine in hand (engine.dialect.name), not a threaded
backend flag: SQLAlchemy already exposes this on any engine, and a second
flag could drift from what the engine actually is (stale kwarg, wrong test
fixture) in a way that silently corrupts a load instead of erroring loudly.

String-building helpers (everything except table_exists/column_exists) take
no engine -- they return SQL text for the caller to run inside whatever
connection/transaction it already has open, rather than opening a separate
one here.
"""
from abc import ABC, abstractmethod

from sqlalchemy import text

import type_map as mssql_type_map


class SqlDialect(ABC):
    @abstractmethod
    def qualify(self, schema, table):
        """Quoted schema.table identifier for raw SQL text."""

    @abstractmethod
    def quote_ident(self, name):
        """Quoted bare identifier (e.g. a column name) for raw SQL text."""

    @abstractmethod
    def raw_text_type(self):
        """This backend's 'store anything as text' column type, for
        replicate.py's raw=True path (every column NVARCHAR(MAX)-equivalent)."""

    @abstractmethod
    def table_exists(self, engine, schema, table):
        ...

    @abstractmethod
    def column_exists(self, engine, schema, table, column):
        ...

    @abstractmethod
    def create_table_as_select_sql(self, schema, new_table, columns_sql, rest_sql):
        """rest_sql is 'FROM ... [WHERE ...]', with table names already
        run through self.qualify(). columns_sql is the select-list, e.g. '*'."""

    @abstractmethod
    def select_top_n_sql(self, columns_sql, rest_sql, n):
        """rest_sql is 'FROM ... [WHERE ...] [ORDER BY ...]', no limit applied yet."""

    @abstractmethod
    def autoincrement_pk_column_ddl(self, name):
        ...

    @abstractmethod
    def sf_type_to_sql(self, field):
        """Salesforce describe() field -> this backend's column type."""


class MssqlDialect(SqlDialect):
    def qualify(self, schema, table):
        return f"[{schema}].[{table}]"

    def quote_ident(self, name):
        return f"[{name}]"

    def raw_text_type(self):
        return "NVARCHAR(MAX)"

    def table_exists(self, engine, schema, table):
        with engine.connect() as cx:
            return cx.execute(
                text("SELECT OBJECT_ID(:t, 'U')"), {"t": f"{schema}.{table}"}
            ).scalar() is not None

    def column_exists(self, engine, schema, table, column):
        with engine.connect() as cx:
            return cx.execute(
                text("SELECT COL_LENGTH(:t, :c)"), {"t": f"{schema}.{table}", "c": column}
            ).scalar() is not None

    def create_table_as_select_sql(self, schema, new_table, columns_sql, rest_sql):
        return f"SELECT {columns_sql} INTO {self.qualify(schema, new_table)} {rest_sql}"

    def select_top_n_sql(self, columns_sql, rest_sql, n):
        return f"SELECT TOP ({n}) {columns_sql} {rest_sql}"

    def autoincrement_pk_column_ddl(self, name):
        return f"{name} INT IDENTITY(1,1) PRIMARY KEY"

    def sf_type_to_sql(self, field):
        return mssql_type_map.sf_type_to_sql(field)


class SqliteDialect(SqlDialect):
    def qualify(self, schema, table):
        return f'"{schema}"."{table}"'

    def quote_ident(self, name):
        return f'"{name}"'

    def raw_text_type(self):
        return "TEXT"

    def table_exists(self, engine, schema, table):
        with engine.connect() as cx:
            return cx.execute(
                text(f'SELECT name FROM "{schema}".sqlite_master WHERE type=\'table\' AND name=:t'),
                {"t": table},
            ).fetchone() is not None

    def column_exists(self, engine, schema, table, column):
        with engine.connect() as cx:
            rows = cx.execute(text(f'PRAGMA "{schema}".table_info("{table}")')).fetchall()
            return any(r[1] == column for r in rows)

    def create_table_as_select_sql(self, schema, new_table, columns_sql, rest_sql):
        # No column affinity carries over from CTAS in SQLite (unlike SQL
        # Server's SELECT INTO, which preserves source types) -- accepted,
        # documented gap; the only real caller (build_retry_table) only
        # ever re-reads this table via pandas and re-serializes to CSV, so
        # a missing declared type doesn't bite there.
        return f"CREATE TABLE {self.qualify(schema, new_table)} AS SELECT {columns_sql} {rest_sql}"

    def select_top_n_sql(self, columns_sql, rest_sql, n):
        return f"SELECT {columns_sql} {rest_sql} LIMIT {n}"

    def autoincrement_pk_column_ddl(self, name):
        return f"{name} INTEGER PRIMARY KEY AUTOINCREMENT"

    def sf_type_to_sql(self, field):
        # SQLite has type *affinity*, not enforced length/precision -- no
        # need to replicate type_map.py's NVARCHAR(n)/DECIMAL(p,s) detail.
        t = field["type"]
        if t in ("boolean", "int"):
            return "INTEGER"
        if t in ("double", "currency", "percent"):
            return "REAL"
        if t == "base64":
            return "BLOB"
        # id/reference/string/picklist/combobox/phone/url/email/
        # encryptedstring/textarea/multipicklist/date/datetime/time and
        # anything unrecognized: TEXT covers all of these (dates/datetimes
        # stored as ISO8601 text, SQLite's own convention).
        return "TEXT"


_DIALECTS = {"mssql": MssqlDialect(), "sqlite": SqliteDialect()}


def for_engine(engine):
    name = engine.dialect.name
    try:
        return _DIALECTS[name]
    except KeyError:
        raise ValueError(f"Unsupported SQL backend: {name!r} (supported: {sorted(_DIALECTS)})")
