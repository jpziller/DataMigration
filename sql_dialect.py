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

import pandas as pd
from sqlalchemy import text

import type_map as mssql_type_map


def _escape_bracket_ident(name):
    """Escape a bracket-quoted (SQL Server) identifier's own closing
    bracket by doubling it -- SQL Server's own convention, e.g. `]` inside
    `[a]b]` must be written `[a]]b]`. Without this, an identifier with an
    embedded `]` (e.g. a CSV column header this framework doesn't fully
    control, see import-csv-directory/source_ingestion.py) breaks out of
    the quoting and injects arbitrary SQL into the generated statement."""
    return str(name).replace("]", "]]")


def _escape_doublequote_ident(name):
    """Escape a double-quoted (SQLite/ANSI) identifier's own quote
    character by doubling it -- same reasoning as _escape_bracket_ident,
    for the `"` character instead of `]`."""
    return str(name).replace('"', '""')


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
    def list_columns(self, engine, schema, table):
        """Ordered [(column_name, data_type), ...] for an existing table --
        the INFORMATION_SCHEMA.COLUMNS-shaped info mapping_doc.py/others need,
        without assuming SQL Server's own INFORMATION_SCHEMA is available."""

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

    @abstractmethod
    def normalize_datetime_columns(self, df):
        """Return df with any datetime64-dtype column converted to a
        string representation safe for this backend's own to_sql() write
        path -- see SqliteDialect's own docstring for why this exists."""


class MssqlDialect(SqlDialect):
    def qualify(self, schema, table):
        return f"[{_escape_bracket_ident(schema)}].[{_escape_bracket_ident(table)}]"

    def quote_ident(self, name):
        return f"[{_escape_bracket_ident(name)}]"

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

    def list_columns(self, engine, schema, table):
        with engine.connect() as cx:
            rows = cx.execute(
                text(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table ORDER BY ORDINAL_POSITION"
                ),
                {"schema": schema, "table": table},
            ).all()
        return [(r[0], r[1]) for r in rows]

    def create_table_as_select_sql(self, schema, new_table, columns_sql, rest_sql):
        return f"SELECT {columns_sql} INTO {self.qualify(schema, new_table)} {rest_sql}"

    def select_top_n_sql(self, columns_sql, rest_sql, n):
        return f"SELECT TOP ({n}) {columns_sql} {rest_sql}"

    def autoincrement_pk_column_ddl(self, name):
        return f"{name} INT IDENTITY(1,1) PRIMARY KEY"

    def sf_type_to_sql(self, field):
        return mssql_type_map.sf_type_to_sql(field)

    def normalize_datetime_columns(self, df):
        # pyodbc's own native datetime handling already round-trips a real
        # Python/pandas datetime object into DATETIME2 correctly -- no
        # string-formatting step needed here.
        return df


class SqliteDialect(SqlDialect):
    def qualify(self, schema, table):
        return f'"{_escape_doublequote_ident(schema)}"."{_escape_doublequote_ident(table)}"'

    def quote_ident(self, name):
        return f'"{_escape_doublequote_ident(name)}"'

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

    def list_columns(self, engine, schema, table):
        with engine.connect() as cx:
            rows = cx.execute(text(f'PRAGMA "{schema}".table_info("{table}")')).fetchall()
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        return [(r[1], r[2]) for r in rows]

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

    def normalize_datetime_columns(self, df):
        # Confirmed live, a real bug: SQLAlchemy's own sqlite DateTime type
        # (not sqlite3's own adapter -- pandas .to_sql() goes through
        # SQLAlchemy's type system, bypassing sql_client.py's
        # sqlite3.register_adapter() entirely) serializes a datetime64
        # column as "YYYY-MM-DD HH:MM:SS.ffffff" -- a space separator, not
        # 'T'. That's a genuine XSD dateTime parse failure against
        # Salesforce's Bulk API ("is not a valid value for the type
        # xsd:dateTime"), not merely non-canonical -- it broke every row
        # of a real bulkops insert the first time a mocked datetime field
        # (Contact.EmailBouncedDate) went through this path unconverted.
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S").where(df[col].notna(), None)
        return df


_DIALECTS = {"mssql": MssqlDialect(), "sqlite": SqliteDialect()}


def for_engine(engine):
    name = engine.dialect.name
    try:
        return _DIALECTS[name]
    except KeyError:
        raise ValueError(f"Unsupported SQL backend: {name!r} (supported: {sorted(_DIALECTS)})")
