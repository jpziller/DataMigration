"""Backend-aware SQL dialect helpers (SQL Server + SQLite + PostgreSQL).

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
    #: Short backend identifier ("mssql"/"sqlite"/"postgres") each concrete
    #: subclass must set as a class attribute -- used only by pick_type()
    #: below, for callers with their own ad hoc per-backend column types
    #: (BulkOpsLog/OrchestratorRunEvent/SourceIngestionLog/ObjectDependency/
    #: ObjectLoadOrder/ObjectAutomationRisk) that don't go through
    #: sf_type_to_sql(). Not used anywhere else in this module.
    backend_key = None

    def pick_type(self, mssql_type, sqlite_type, postgres_type):
        """Select the right column-type string for whichever real dialect
        this is, from a single (mssql, sqlite, postgres) triple -- replaces
        the private, mssql-or-sqlite-only `_col_type()`/inline
        `isinstance(d, MssqlDialect)` ternaries that used to be duplicated
        independently in bulkops.py, orchestrator.py, source_ingestion.py,
        load_order.py, and risk_analyzer.py (found in review: every one of
        those would have silently mistyped a Postgres column as whatever
        the *sqlite* type was, e.g. DATETIME2 -> TEXT instead of TIMESTAMP,
        since none of them knew a third backend existed). A fourth backend
        now needs updating in exactly one place, not five."""
        return {"mssql": mssql_type, "sqlite": sqlite_type, "postgres": postgres_type}[self.backend_key]

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


def lower_keys(row):
    """Lowercase every key of a SQLAlchemy RowMapping (or plain dict) --
    needed because Postgres folds an unquoted column name to lowercase
    not just for matching but for the catalog name itself, so a query
    result's actual keys come back lowercased (`row["LogId"]` raises
    `NoSuchColumnError` there) even though SQL Server/SQLite both
    preserve/return whatever case a column was originally declared with.
    Confirmed live: orchestrator.py's own `row["LogId"]` failed against a
    real Postgres instance until routed through this. Found in review: an
    earlier version of this fix also had a `row_get(row, key)` variant
    (exact-case fast path, case-insensitive fallback, for a single-field
    access) -- removed once its only real call site turned out to still
    need `lower_keys()` right next to it anyway (a second helper with no
    call site of its own is not a justified split, just incidental
    duplication)."""
    return {k.lower(): v for k, v in dict(row).items()}


class MssqlDialect(SqlDialect):
    backend_key = "mssql"

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
    backend_key = "sqlite"

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


class PostgresDialect(SqlDialect):
    """roadmap #69 -- the third real `sql_dialect.py` backend. Identifier
    quoting/CTAS/LIMIT match SqliteDialect's own ANSI-ish conventions
    (Postgres and SQLite happen to agree here); table/column introspection
    uses information_schema (Postgres, unlike SQLite, genuinely implements
    it) rather than SQLite's PRAGMA or SQL Server's OBJECT_ID/COL_LENGTH.
    See ROADMAP.md #69 for what's been verified live against a real
    Postgres instance vs. reasoned from docs."""

    backend_key = "postgres"

    def qualify(self, schema, table):
        return f'"{_escape_doublequote_ident(schema)}"."{_escape_doublequote_ident(table)}"'

    def quote_ident(self, name):
        return f'"{_escape_doublequote_ident(name)}"'

    def raw_text_type(self):
        return "TEXT"

    def table_exists(self, engine, schema, table):
        with engine.connect() as cx:
            return cx.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = :table"
                ),
                {"schema": schema, "table": table},
            ).fetchone() is not None

    def column_exists(self, engine, schema, table, column):
        # column_name compared via LOWER() on both sides, not an exact
        # match -- found via live Postgres testing: this codebase creates
        # most columns bare/unquoted (see bulkops.py's own CREATE TABLE
        # comment for why), which Postgres folds to lowercase in the
        # catalog, while every caller here still passes the
        # originally-declared Pascal-case name (e.g. "BatchSize"). An
        # exact-case comparison against `information_schema.columns` --
        # unlike table_exists() above, where table names are always
        # created via self.qualify() and therefore quoted/case-preserved
        # -- silently always returned False, so
        # enable_bulkops_logging()'s own upgrade-column-exists check
        # thought a column was still missing on every single run, even
        # right after creating it.
        with engine.connect() as cx:
            return cx.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = :table "
                    "AND LOWER(column_name) = LOWER(:column)"
                ),
                {"schema": schema, "table": table, "column": column},
            ).fetchone() is not None

    def list_columns(self, engine, schema, table):
        with engine.connect() as cx:
            rows = cx.execute(
                text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = :table "
                    "ORDER BY ordinal_position"
                ),
                {"schema": schema, "table": table},
            ).all()
        return [(r[0], r[1]) for r in rows]

    def create_table_as_select_sql(self, schema, new_table, columns_sql, rest_sql):
        # Same CTAS shape/limitation as SqliteDialect -- no guaranteed
        # column-type carryover the way SQL Server's SELECT INTO gives;
        # fine for the one real caller (build_retry_table), which only
        # re-reads this table via pandas and re-serializes to CSV.
        return f"CREATE TABLE {self.qualify(schema, new_table)} AS SELECT {columns_sql} {rest_sql}"

    def select_top_n_sql(self, columns_sql, rest_sql, n):
        return f"SELECT {columns_sql} {rest_sql} LIMIT {n}"

    def autoincrement_pk_column_ddl(self, name):
        # SQL-standard identity column syntax (Postgres 10+) -- Postgres's
        # own docs recommend this over the legacy SERIAL pseudo-type.
        return f"{name} INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"

    def sf_type_to_sql(self, field):
        # Mirrors type_map.py's mssql granularity (real VARCHAR(n)/
        # NUMERIC(p,s), not just SQLite's loose TEXT-for-everything
        # affinity) but with Postgres-native type names -- no NVARCHAR
        # (Postgres VARCHAR is already UTF-8, no separate N-prefixed type
        # needed).
        t = field["type"]
        length = field.get("length") or 0
        precision = field.get("precision") or 0
        scale = field.get("scale") or 0

        if t in ("id", "reference"):
            return "VARCHAR(18)"
        if t in ("string", "picklist", "combobox", "phone", "url",
                 "email", "encryptedstring"):
            n = length if 0 < length <= 4000 else 4000
            return f"VARCHAR({n})"
        if t in ("textarea", "multipicklist"):
            return "TEXT"
        if t == "boolean":
            return "BOOLEAN"
        if t == "int":
            return "INTEGER"
        if t in ("double", "currency", "percent"):
            if precision > 0:
                return f"NUMERIC({precision},{scale})"
            return "DOUBLE PRECISION"
        if t == "date":
            return "DATE"
        if t == "datetime":
            return "TIMESTAMP"
        if t == "time":
            return "TIME"
        if t == "base64":
            return "BYTEA"
        return "TEXT"

    def normalize_datetime_columns(self, df):
        # psycopg2 registers its own native adapters for Python
        # datetime.datetime/date objects (long-established, documented
        # psycopg2 behavior) -- same category of reasoning as pyodbc's for
        # MssqlDialect above, so no string-formatting workaround should be
        # needed. Unlike the mssql/sqlite dialects, this hasn't actually
        # been exercised against a live Postgres instance yet -- treat as
        # the first thing to check if a real Postgres-backed replicate/
        # bulkops run hits a datetime write error.
        return df


_DIALECTS = {"mssql": MssqlDialect(), "sqlite": SqliteDialect(), "postgresql": PostgresDialect()}


def for_engine(engine):
    name = engine.dialect.name
    try:
        return _DIALECTS[name]
    except KeyError:
        raise ValueError(f"Unsupported SQL backend: {name!r} (supported: {sorted(_DIALECTS)})")
