"""Source directory ingestion (roadmap #46).

A client hands over a directory of CSV files (or this is a later pass --
e.g. a UAT reload -- of a directory shaped like one seen before). This
module reads a whole directory in one bulk operation and turns it into a
Source SQL Server database, generalizing a proven real-world convention
from hand-built client migration scripts: stage every column as
NVARCHAR(MAX) via BULK INSERT, type/transform later via T-SQL under
sql/transformations/ -- deliberately NOT type-sniffing the CSV (dates,
leading-zero ids, and numeric-looking strings are exactly the values type
inference gets wrong; explicit T-SQL transforms are this framework's own
established way to type staged data, see replicate.py/type_map.py's own
coercion step for the Salesforce side).

Two cases, handled differently:
  - New file (no existing script for its derived table name): generate a
    numbered .sql script under sql/source_ingestion/ (git-committed,
    human-readable, sqlcmd-runnable -- the actual artifact of record for
    this project), then run it.
  - Existing file, later pass: the script is REUSED, never silently
    regenerated -- only its current CSV's header is checked against what
    the script expects. BULK INSERT maps columns *positionally*, not by
    name, so a reordered column is exactly as dangerous as a renamed one;
    check_drift() compares the full ordered column list, not just set
    membership. Any difference is a hard stop for that file -- the
    architect must understand what changed and explicitly --rebuild it
    before it loads again.

Execution never shells out to sqlcmd or blindly evals a script's raw text:
DROP/CREATE/BULK INSERT are always reconstructed from known values (table
name, column list, csv path) and run via the same SQLAlchemy engine every
other write path in this framework uses (see parquet_import.py's
create_table() for the identical drop+create shape). The .sql file is a
human-readable, independently re-runnable (`sqlcmd -i`) artifact, not
something Python re-parses and evals wholesale.

Known operational requirement, not fixable from Python: BULK INSERT needs
the SQL Server service account itself to have filesystem read access to
the CSV's path -- true by default for a local/on-prem SQL Server sharing a
machine (or a reachable UNC path) with the files, but a real constraint to
be aware of on an unusual setup.
"""
import csv
import os
import re
from datetime import datetime, timezone

from sqlalchemy import text

import migration_run_book

_SQL_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), "sql", "source_ingestion")

_TABLE_NAME_RE = re.compile(r"[^A-Za-z0-9_]")
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:\[?[\w]+\]?\.)?\[?(\w+)\]?\s*\(([^;]+?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_LINE_RE = re.compile(r"\[(\w+)\]\s+NVARCHAR\(MAX\)\s+NULL")
_BULK_INSERT_FROM_RE = re.compile(r"BULK\s+INSERT\s+.*?\bFROM\s+'([^']+)'", re.IGNORECASE | re.DOTALL)
_SCRIPT_NUMBER_RE = re.compile(r"^(\d+)_")


def table_name_for_csv(csv_path):
    """Sanitized base filename (extension stripped, non-alnum -> '_') as
    the destination table name -- no forced prefix, the client's own
    filename is already meaningful and this is what they'll recognize on a
    later pass."""
    base = os.path.splitext(os.path.basename(csv_path))[0]
    return _TABLE_NAME_RE.sub("_", base)


def _read_csv_header(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh))


def _check_no_duplicate_columns(columns, csv_path):
    """Hard rule 14: a CSV header with a repeated column name would make
    generate_import_script()'s CREATE TABLE fail outright ("column name ...
    specified more than once") -- catch it here with a clear message
    instead of a raw SQL Server error partway through a run."""
    duplicates = sorted({c for c in columns if columns.count(c) > 1})
    if duplicates:
        raise ValueError(
            f"{csv_path}'s header has duplicate column name(s): {duplicates} -- "
            "fix the source file before it can be staged (a CREATE TABLE can't "
            "have the same column twice)."
        )


def _next_script_number(sql_dir):
    if not os.path.isdir(sql_dir):
        return 10
    existing = [
        int(m.group(1)) for f in os.listdir(sql_dir)
        if (m := _SCRIPT_NUMBER_RE.match(f))
    ]
    return (max(existing) + 10) if existing else 10


def _script_path_for_table(sql_dir, table_name):
    """The existing script for table_name, if any -- matched by table name
    appearing in the filename, same discovery convention
    migration_run_book.py's _script_filename_for() already uses for
    sql/transformations/."""
    if not os.path.isdir(sql_dir):
        return None
    matches = sorted(
        f for f in os.listdir(sql_dir)
        if f.lower().endswith(".sql") and f"_{table_name.lower()}_" in f"_{f.lower()}"
    )
    return os.path.join(sql_dir, matches[0]) if matches else None


def generate_import_script(csv_path, table_name, ticket, schema="dbo", sql_dir=_SQL_DIR_DEFAULT):
    """Write a new numbered BULK INSERT script for csv_path. Never
    overwrites an existing script for this table -- rebuild_import_script()
    is the only explicit path that replaces one."""
    os.makedirs(sql_dir, exist_ok=True)
    columns = _read_csv_header(csv_path)
    _check_no_duplicate_columns(columns, csv_path)
    abs_csv_path = os.path.abspath(csv_path)

    number = _next_script_number(sql_dir)
    filename = f"{number}_{table_name}_import.sql"
    out_path = os.path.join(sql_dir, filename)

    cols_sql = ",\n    ".join(f"[{c}] NVARCHAR(MAX) NULL" for c in columns)
    script = f"""/*  Source ingestion: stage {os.path.basename(csv_path)} into [{schema}].[{table_name}].
    Ticket: {ticket}

    Every column is staged as NVARCHAR(MAX) -- no type sniffing. Type and
    transform this data via sql/transformations/*.sql once mapped, the
    same "stage raw, type explicitly" convention this framework already
    uses for every other source. KEEPNULLS: an empty CSV field becomes SQL
    NULL, not empty string.

    Reused as-is on every later pass -- never regenerate by hand. If this
    CSV's structure ever no longer matches the column list below, treat
    that as a real signal to stop and understand why before reloading;
    `import-csv-directory` checks this automatically and blocks the load
    on drift, only proceeding once --rebuild is passed explicitly.

    Requires the SQL Server service account to have filesystem read access
    to the path below -- true by default for a local/on-prem instance
    sharing a machine or reachable UNC path with the source files.

    ROWTERMINATOR is '0x0a', not the '\\n' shorthand -- confirmed live
    (SQL Server 2022 16.0.1180.1): '\\n' combined with FORMAT='csv' raises
    "Cannot obtain the required interface (IID_IColumnsInfo) from OLE DB
    provider BULK" (msg 7301) on this build, while the hex-string form
    loads cleanly. Don't "simplify" this back to '\\n'.
*/
IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL
    DROP TABLE [{schema}].[{table_name}];

CREATE TABLE [{schema}].[{table_name}] (
    {cols_sql}
);

BULK INSERT [{schema}].[{table_name}]
FROM '{abs_csv_path}'
WITH (
    FORMAT = 'csv',
    FIRSTROW = 2,
    FIELDQUOTE = '"',
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    KEEPNULLS
);
"""
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(script)
    return out_path


def rebuild_import_script(csv_path, table_name, ticket, schema="dbo", sql_dir=_SQL_DIR_DEFAULT):
    """Explicitly replace an existing script for table_name with a fresh
    one matching the CSV's current structure -- only ever called when the
    architect has reviewed a drift report and decided to accept it."""
    existing = _script_path_for_table(sql_dir, table_name)
    if existing:
        os.remove(existing)
    return generate_import_script(csv_path, table_name, ticket, schema=schema, sql_dir=sql_dir)


def extract_create_table_columns(sql_text):
    """Return the ordered column-name list from a generated script's
    CREATE TABLE, or None if none is found -- same regex-parsing style as
    mapping_doc.extract_insert_columns."""
    m = _CREATE_TABLE_RE.search(sql_text)
    if not m:
        return None
    return _COLUMN_LINE_RE.findall(m.group(2))


def extract_bulk_insert_source_path(sql_text):
    m = _BULK_INSERT_FROM_RE.search(sql_text)
    return m.group(1) if m else None


def check_drift(csv_path, script_path):
    """Compare csv_path's current header against script_path's declared
    column list. Compares the full ORDERED list, not just set membership
    -- BULK INSERT maps columns positionally, so a same-name reorder is
    exactly as dangerous as a rename and must be caught the same way.

    Returns {"ok", "added", "removed", "reordered", "current_columns",
    "script_columns"}."""
    current_columns = _read_csv_header(csv_path)
    with open(script_path, encoding="utf-8") as fh:
        script_columns = extract_create_table_columns(fh.read()) or []

    current_set, script_set = set(current_columns), set(script_columns)
    added = [c for c in current_columns if c not in script_set]
    removed = [c for c in script_columns if c not in current_set]
    reordered = (
        not added and not removed
        and current_columns != script_columns
    )
    ok = not added and not removed and not reordered
    return {
        "ok": ok,
        "added": added,
        "removed": removed,
        "reordered": reordered,
        "current_columns": current_columns,
        "script_columns": script_columns,
    }


def _run_script(engine, schema, table_name, columns, csv_path):
    """Reconstruct and execute the DROP/CREATE/BULK INSERT sequence
    directly -- same shape as parquet_import.py's create_table(), never a
    blind exec of a script file's raw text. Returns the row count."""
    cols_sql = ",\n    ".join(f"[{c}] NVARCHAR(MAX) NULL" for c in columns)
    abs_csv_path = os.path.abspath(csv_path)
    with engine.begin() as cx:
        cx.execute(text(f"IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL DROP TABLE [{schema}].[{table_name}];"))
        cx.execute(text(f"CREATE TABLE [{schema}].[{table_name}] (\n    {cols_sql}\n);"))
        # BULK INSERT's FROM clause does not accept a bound parameter in
        # SQL Server -- the path must be a literal. Safe here because
        # abs_csv_path is a local filesystem path this same process just
        # resolved via os.path.abspath, not external/user-facing input
        # reaching this string via a SQL injection surface.
        # ROWTERMINATOR = '0x0a', not '\n' -- confirmed live, see
        # generate_import_script()'s docstring for why.
        cx.execute(text(
            f"BULK INSERT [{schema}].[{table_name}] FROM '{abs_csv_path}' WITH "
            "(FORMAT = 'csv', FIRSTROW = 2, FIELDQUOTE = '\"', FIELDTERMINATOR = ',', "
            "ROWTERMINATOR = '0x0a', KEEPNULLS);"
        ))
        count = cx.execute(text(f"SELECT COUNT(*) FROM [{schema}].[{table_name}]")).scalar()
    return count


def _ensure_log_table(engine, schema):
    with engine.connect() as cx:
        return cx.execute(text("SELECT OBJECT_ID(:t, 'U')"), {"t": f"{schema}.SourceIngestionLog"}).scalar() is not None


def _log_run(engine, schema, table_name, csv_path, script_path, status, row_count,
              started_at, completed_at, drift_details=None):
    if not _ensure_log_table(engine, schema):
        return
    with engine.begin() as cx:
        cx.execute(text(
            f"INSERT INTO [{schema}].[SourceIngestionLog] "
            "(TableName, CsvPath, ScriptPath, Status, [RowCount], StartedAt, CompletedAt, DurationSeconds, RunBy, DriftDetails) "
            "VALUES (:t, :c, :s, :st, :rc, :sa, :ca, :d, :rb, :dd)"
        ), {
            "t": table_name, "c": os.path.abspath(csv_path), "s": script_path,
            "st": status, "rc": row_count, "sa": started_at, "ca": completed_at,
            "d": (completed_at - started_at).total_seconds(),
            "rb": os.environ.get("USERNAME") or os.environ.get("USER"),
            "dd": drift_details,
        })


def import_directory(engine, csv_dir, sql_dir=_SQL_DIR_DEFAULT, schema="dbo", ticket=None, rebuild=None,
                      run_book_path=None, run_book_tab=None):
    """Scan csv_dir for *.csv and, for each file, generate-if-missing (or
    rebuild, if its table name is in `rebuild`) then load its script;
    check_drift() gates every reuse of an existing script. One bad file's
    drift never blocks the rest of the batch. Returns a list of per-file
    result dicts: {"csv", "table", "status", "rows", "duration_seconds"}
    where status is one of "created"/"reused"/"rebuilt"/"drift_blocked".

    run_book_path/run_book_tab (opt-in, both required together): after the
    whole batch finishes, sync SourceIngestionLog into that tab's
    Pre-Migration phase -- same opt-in shape as bulk_op()'s own
    run_book_path/run_book_tab in bulkops.py. A sync failure never takes
    away the load results already in the return value; see
    "run_book_sync_error" appended to the return list's last element."""
    rebuild = set(rebuild or [])
    csv_files = sorted(f for f in os.listdir(csv_dir) if f.lower().endswith(".csv"))
    results = []

    for filename in csv_files:
        csv_path = os.path.join(csv_dir, filename)
        table_name = table_name_for_csv(csv_path)
        existing_script = _script_path_for_table(sql_dir, table_name)
        started_at = datetime.now(timezone.utc).replace(tzinfo=None)

        if existing_script and table_name in rebuild:
            if not ticket:
                raise ValueError(f"--ticket is required to rebuild the script for '{table_name}'.")
            script_path = rebuild_import_script(csv_path, table_name, ticket, schema=schema, sql_dir=sql_dir)
            status = "rebuilt"
        elif existing_script:
            drift = check_drift(csv_path, existing_script)
            if not drift["ok"]:
                completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                drift_summary = "; ".join(filter(None, [
                    f"added: {', '.join(drift['added'])}" if drift["added"] else None,
                    f"removed: {', '.join(drift['removed'])}" if drift["removed"] else None,
                    "column order changed" if drift["reordered"] else None,
                ]))
                _log_run(
                    engine, schema, table_name, csv_path, existing_script,
                    "drift_blocked", None, started_at, completed_at, drift_details=drift_summary,
                )
                results.append({
                    "csv": filename, "table": table_name, "status": "drift_blocked",
                    "rows": None, "duration_seconds": None, "drift": drift,
                    "script": existing_script,
                })
                continue
            script_path = existing_script
            status = "reused"
        else:
            if not ticket:
                raise ValueError(f"--ticket is required to generate a new script for '{table_name}'.")
            script_path = generate_import_script(csv_path, table_name, ticket, schema=schema, sql_dir=sql_dir)
            status = "created"

        with open(script_path, encoding="utf-8") as fh:
            columns = extract_create_table_columns(fh.read())
        row_count = _run_script(engine, schema, table_name, columns, csv_path)
        completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        _log_run(engine, schema, table_name, csv_path, script_path, status, row_count, started_at, completed_at)
        results.append({
            "csv": filename, "table": table_name, "status": status,
            "rows": row_count, "duration_seconds": (completed_at - started_at).total_seconds(),
            "script": script_path,
        })

    if run_book_path and run_book_tab and results:
        try:
            migration_run_book.sync_source_ingestion_to_run_book(engine, run_book_path, run_book_tab, schema=schema)
        except Exception as e:
            results.append({"run_book_sync_error": str(e)})

    return results


def enable_source_ingestion_logging(engine, schema="dbo"):
    """Create <schema>.SourceIngestionLog if it doesn't already exist --
    same opt-in, presence-is-the-switch convention as
    bulkops.enable_bulkops_logging. Off by default; once this table
    exists, import_directory() logs every run against this schema
    automatically."""
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.SourceIngestionLog', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[SourceIngestionLog] ("
            "LogId INT IDENTITY(1,1) PRIMARY KEY, "
            "TableName NVARCHAR(255) NOT NULL, "
            "CsvPath NVARCHAR(1000) NOT NULL, "
            "ScriptPath NVARCHAR(1000) NOT NULL, "
            "Status NVARCHAR(20) NOT NULL, "
            "[RowCount] INT NULL, "  # RowCount collides with a T-SQL reserved keyword (SET ROWCOUNT/@@ROWCOUNT) -- must be bracketed
            "StartedAt DATETIME2 NOT NULL, "
            "CompletedAt DATETIME2 NOT NULL, "
            "DurationSeconds FLOAT NOT NULL, "
            "RunBy NVARCHAR(128) NULL, "
            "DriftDetails NVARCHAR(1000) NULL);"
        ))


def disable_source_ingestion_logging(engine, schema="dbo"):
    """Drop <schema>.SourceIngestionLog -- permanently discards that
    schema's log history. Idempotent (no-op if never enabled)."""
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.SourceIngestionLog', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[SourceIngestionLog];"
        ))
