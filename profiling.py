"""Data profiling: population counts, min/max, distinct counts, and value
distributions -- for deciding what's worth migrating and what isn't.

Two entry points sharing one storage format:
  profile_salesforce_object() -- profiles a Salesforce object directly via
      aggregate SOQL queries (describe()-driven, field-type aware).
  profile_sql_table()         -- profiles any SQL Server table (a replicated
      mirror table, or a legacy source table loaded some other way) via a
      single dynamic aggregate query over sys.columns/INFORMATION_SCHEMA.

Both write to the same two tables (dbo.FieldProfile, dbo.FieldProfileValues)
keyed by (ObjectOrTable, SourceType, FieldName), so export_profile_to_excel()
works the same regardless of where the data came from. Re-profiling an
object/table replaces only that object's prior rows.
"""
import re
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from type_map import is_compound

# Field types SOQL will reject in aggregate/GROUP BY/ORDER BY/WHERE-null-check
# contexts -- this is a hard Salesforce platform restriction on long-text and
# binary fields, not something a smarter query can work around. These fields
# come back with data_type/total_rows only; every other stat is left NULL.
# Getting a real population count for them would mean pulling actual row
# data and counting client-side (a full extract, not an aggregate query) --
# out of scope for this tool's lightweight aggregate-only design.
_SOQL_UNAGGREGATABLE_TYPES = {"textarea", "base64", "encryptedstring"}
# Field types worth a MIN/MAX in the aggregate query.
_SOQL_MINMAX_TYPES = {
    "int", "double", "currency", "percent", "date", "datetime", "time",
    "string", "picklist", "phone", "email", "url", "id", "reference", "boolean",
}
# Field types worth a GROUP BY value-distribution query.
_SOQL_DISTRIBUTION_TYPES = {"picklist", "multipicklist", "boolean"}

_SQL_TEXT_TYPES = {"char", "varchar", "nchar", "nvarchar", "text", "ntext"}
_SQL_BINARY_TYPES = {"binary", "varbinary", "image"}

_INVALID_SHEET_CHARS = re.compile(r"[:\\/?*\[\]]")


def _ensure_profile_tables(engine, schema="dbo"):
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.FieldProfile', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[FieldProfile] ("
            "ObjectOrTable NVARCHAR(255) NOT NULL, "
            "SourceType NVARCHAR(20) NOT NULL, "
            "FieldName NVARCHAR(255) NOT NULL, "
            "DataType NVARCHAR(50) NULL, "
            "TotalRows INT NULL, "
            "PopulatedCount INT NULL, "
            "PopulatedPct DECIMAL(5,2) NULL, "
            "NullCount INT NULL, "
            "BlankCount INT NULL, "
            "DistinctCount INT NULL, "
            "MinValue NVARCHAR(4000) NULL, "
            "MaxValue NVARCHAR(4000) NULL, "
            "MinLength INT NULL, "
            "MaxLength INT NULL, "
            "AnalyzedDate DATETIME2 NOT NULL, "
            "CONSTRAINT PK_FieldProfile PRIMARY KEY (ObjectOrTable, SourceType, FieldName));"
        ))
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.FieldProfileValues', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[FieldProfileValues] ("
            "ObjectOrTable NVARCHAR(255) NOT NULL, "
            "SourceType NVARCHAR(20) NOT NULL, "
            "FieldName NVARCHAR(255) NOT NULL, "
            "Value NVARCHAR(4000) NULL, "
            "Occurrences INT NOT NULL, "
            "AnalyzedDate DATETIME2 NOT NULL);"
        ))
        cx.execute(text(
            f"IF NOT EXISTS (SELECT 1 FROM sys.indexes "
            f"WHERE name = 'IX_FieldProfileValues_Lookup' "
            f"AND object_id = OBJECT_ID('{schema}.FieldProfileValues')) "
            f"CREATE INDEX IX_FieldProfileValues_Lookup ON [{schema}].[FieldProfileValues] "
            "(ObjectOrTable, SourceType, FieldName);"
        ))


def _to_str(v):
    if v is None:
        return None
    return str(v)[:4000]


def _write_profile(engine, object_or_table, source_type, profiles, distributions, schema="dbo"):
    _ensure_profile_tables(engine, schema=schema)
    analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as cx:
        cx.execute(
            text(f"DELETE FROM [{schema}].[FieldProfile] WHERE ObjectOrTable = :name AND SourceType = :st"),
            {"name": object_or_table, "st": source_type},
        )
        cx.execute(
            text(f"DELETE FROM [{schema}].[FieldProfileValues] WHERE ObjectOrTable = :name AND SourceType = :st"),
            {"name": object_or_table, "st": source_type},
        )

        rows = []
        for field_name, p in profiles.items():
            total = p.get("total_rows")
            populated = p.get("populated_count")
            null_count = p.get("null_count")
            if null_count is None and total is not None and populated is not None:
                null_count = total - populated
            pct = round(100.0 * populated / total, 2) if total and populated is not None else None
            rows.append({
                "object_or_table": object_or_table,
                "source_type": source_type,
                "field_name": field_name,
                "data_type": p.get("data_type"),
                "total_rows": total,
                "populated_count": populated,
                "populated_pct": pct,
                "null_count": null_count,
                "blank_count": p.get("blank_count"),
                "distinct_count": p.get("distinct_count"),
                "min_value": _to_str(p.get("min_value")),
                "max_value": _to_str(p.get("max_value")),
                "min_length": p.get("min_length"),
                "max_length": p.get("max_length"),
                "analyzed_at": analyzed_at,
            })
        if rows:
            cx.execute(
                text(
                    f"INSERT INTO [{schema}].[FieldProfile] "
                    "(ObjectOrTable, SourceType, FieldName, DataType, TotalRows, PopulatedCount, PopulatedPct, "
                    "NullCount, BlankCount, DistinctCount, MinValue, MaxValue, MinLength, MaxLength, AnalyzedDate) "
                    "VALUES (:object_or_table, :source_type, :field_name, :data_type, :total_rows, :populated_count, "
                    ":populated_pct, :null_count, :blank_count, :distinct_count, :min_value, :max_value, "
                    ":min_length, :max_length, :analyzed_at)"
                ),
                rows,
            )

        value_rows = []
        for field_name, values in distributions.items():
            for value, occurrences in values:
                value_rows.append({
                    "object_or_table": object_or_table,
                    "source_type": source_type,
                    "field_name": field_name,
                    "value": _to_str(value),
                    "occurrences": occurrences,
                    "analyzed_at": analyzed_at,
                })
        if value_rows:
            cx.execute(
                text(
                    f"INSERT INTO [{schema}].[FieldProfileValues] "
                    "(ObjectOrTable, SourceType, FieldName, Value, Occurrences, AnalyzedDate) "
                    "VALUES (:object_or_table, :source_type, :field_name, :value, :occurrences, :analyzed_at)"
                ),
                value_rows,
            )


# --- Salesforce-direct profiling ---------------------------------------

def _combine_where(where_clause, extra):
    return f"{where_clause} AND {extra}" if where_clause else f" WHERE {extra}"


def _batch_soql(object_name, where_clause, batch):
    select_parts = []
    for f in batch:
        name = f["name"]
        select_parts.append(f"COUNT({name}) {name}_cnt")
        select_parts.append(f"COUNT_DISTINCT({name}) {name}_dist")
        if f["type"] in _SOQL_MINMAX_TYPES:
            select_parts.append(f"MIN({name}) {name}_min")
            select_parts.append(f"MAX({name}) {name}_max")
    return f"SELECT {', '.join(select_parts)} FROM {object_name}{where_clause}"


def _profile_soql_single_field(sf, object_name, where_clause, f, out):
    """Last-resort per-field profiling for a field that broke even in a
    batch of one -- SOQL's aggregate restrictions vary by field/org, so try
    progressively simpler forms rather than giving up on population count."""
    name = f["name"]
    minmax = f["type"] in _SOQL_MINMAX_TYPES

    attempts = []
    if minmax:
        attempts.append((f"SELECT COUNT({name}) cnt, COUNT_DISTINCT({name}) dist, "
                          f"MIN({name}) mn, MAX({name}) mx FROM {object_name}{where_clause}",
                          ("cnt", "dist", "mn", "mx")))
    attempts.append((f"SELECT COUNT({name}) cnt, COUNT_DISTINCT({name}) dist "
                      f"FROM {object_name}{where_clause}", ("cnt", "dist", None, None)))
    attempts.append((f"SELECT COUNT({name}) cnt FROM {object_name}{where_clause}",
                      ("cnt", None, None, None)))

    for soql, (cnt_key, dist_key, min_key, max_key) in attempts:
        try:
            row = sf.query(soql)["records"][0]
            out[name]["populated_count"] = row.get(cnt_key)
            out[name]["distinct_count"] = row.get(dist_key) if dist_key else None
            out[name]["min_value"] = row.get(min_key) if min_key else None
            out[name]["max_value"] = row.get(max_key) if max_key else None
            return
        except Exception:
            continue

    # Booleans are never null in Salesforce -- and "!= null" against a
    # boolean field is a known SOQL quirk that returns 0 even though the
    # field is fully populated. Skip straight to the true answer.
    if f["type"] == "boolean":
        out[name]["populated_count"] = out[name].get("total_rows")
        return

    # Even a bare COUNT(field) aggregate can be rejected for some fields.
    # Fall back to counting via a WHERE filter instead of wrapping the field
    # in COUNT().
    try:
        soql = f"SELECT COUNT(Id) cnt FROM {object_name}{_combine_where(where_clause, f'{name} != null')}"
        row = sf.query(soql)["records"][0]
        out[name]["populated_count"] = row.get("cnt")
    except Exception:
        out[name]["populated_count"] = None


def _profile_soql_batch(sf, object_name, where_clause, batch, out):
    if not batch:
        return
    try:
        row = sf.query(_batch_soql(object_name, where_clause, batch))["records"][0]
        for f in batch:
            name = f["name"]
            out[name]["populated_count"] = row.get(f"{name}_cnt")
            out[name]["distinct_count"] = row.get(f"{name}_dist")
            out[name]["min_value"] = row.get(f"{name}_min")
            out[name]["max_value"] = row.get(f"{name}_max")
        return
    except Exception:
        pass

    if len(batch) == 1:
        _profile_soql_single_field(sf, object_name, where_clause, batch[0], out)
        return

    # One bad field can poison an entire batched query -- rather than losing
    # every other field's stats too, binary-search down to isolate it.
    mid = len(batch) // 2
    _profile_soql_batch(sf, object_name, where_clause, batch[:mid], out)
    _profile_soql_batch(sf, object_name, where_clause, batch[mid:], out)


def _profile_soql_distribution(sf, object_name, where_clause, field_name, top_n):
    soql = (
        f"SELECT {field_name}, COUNT(Id) cnt FROM {object_name}{where_clause} "
        f"GROUP BY {field_name} ORDER BY COUNT(Id) DESC LIMIT {top_n}"
    )
    try:
        records = sf.query(soql)["records"]
    except Exception:
        return []
    return [(r[field_name], r["cnt"]) for r in records]


def is_already_profiled(engine, object_or_table, source_type, schema="dbo"):
    """(bool, last_analyzed_at_or_None) -- has this (object_or_table,
    source_type) ever been profiled in this schema before (roadmap #47)?
    Profiling is a first-pass activity; a later pass should default to
    reviewing what's already known rather than silently re-running the
    same SOQL/aggregate-query cost again. Cheap: FieldProfile.AnalyzedDate
    already exists for exactly this purpose, no new state needed."""
    with engine.connect() as cx:
        if cx.execute(text("SELECT OBJECT_ID(:t, 'U')"), {"t": f"{schema}.FieldProfile"}).scalar() is None:
            return (False, None)
        last = cx.execute(
            text(
                f"SELECT MAX(AnalyzedDate) FROM [{schema}].[FieldProfile] "
                "WHERE ObjectOrTable = :name AND SourceType = :st"
            ),
            {"name": object_or_table, "st": source_type},
        ).scalar()
    return (last is not None, last)


def profile_salesforce_object(sf, engine, object_name, where=None, schema="dbo",
                               top_n_values=50, batch_size=12):
    """Profile a Salesforce object directly via aggregate SOQL queries."""
    desc = getattr(sf, object_name).describe()
    fields = [f for f in desc["fields"] if not is_compound(f)]
    where_clause = f" WHERE {where}" if where else ""

    total_rows = sf.query(f"SELECT COUNT(Id) total FROM {object_name}{where_clause}")["records"][0]["total"]

    profiles = {f["name"]: {"data_type": f["type"], "total_rows": total_rows} for f in fields}

    profileable = [f for f in fields if f["type"] not in _SOQL_UNAGGREGATABLE_TYPES]
    for i in range(0, len(profileable), batch_size):
        _profile_soql_batch(sf, object_name, where_clause, profileable[i:i + batch_size], profiles)

    distributions = {}
    for f in fields:
        if f["type"] in _SOQL_DISTRIBUTION_TYPES:
            values = _profile_soql_distribution(sf, object_name, where_clause, f["name"], top_n_values)
            if values:
                distributions[f["name"]] = values

    _write_profile(engine, object_name, "salesforce", profiles, distributions, schema=schema)
    return profiles, distributions


# --- SQL Server table profiling -----------------------------------------

def profile_sql_table(engine, table_name, schema="dbo", top_n_values=50, distinct_threshold=50):
    """Profile any SQL Server table via one dynamic aggregate query."""
    with engine.connect() as cx:
        columns = cx.execute(
            text(
                "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table "
                "ORDER BY ORDINAL_POSITION"
            ),
            {"schema": schema, "table": table_name},
        ).mappings().all()

    if not columns:
        raise ValueError(f"No such table: {schema}.{table_name}")

    select_parts = ["COUNT(*) AS TotalRows"]
    for col in columns:
        name = col["COLUMN_NAME"]
        dtype = col["DATA_TYPE"]
        is_max_len = col["CHARACTER_MAXIMUM_LENGTH"] == -1

        select_parts.append(f"COUNT([{name}]) AS [{name}__populated]")
        if dtype in _SQL_TEXT_TYPES:
            select_parts.append(f"SUM(CASE WHEN [{name}] = '' THEN 1 ELSE 0 END) AS [{name}__blank]")
        if dtype not in _SQL_BINARY_TYPES:
            if dtype != "bit":  # SQL Server: MIN/MAX reject the bit type outright
                select_parts.append(f"MIN([{name}]) AS [{name}__min]")
                select_parts.append(f"MAX([{name}]) AS [{name}__max]")
            select_parts.append(f"MIN(LEN(CAST([{name}] AS NVARCHAR(MAX)))) AS [{name}__minlen]")
            select_parts.append(f"MAX(LEN(CAST([{name}] AS NVARCHAR(MAX)))) AS [{name}__maxlen]")
        if not is_max_len:
            select_parts.append(f"COUNT(DISTINCT [{name}]) AS [{name}__distinct]")

    sql = f"SELECT {', '.join(select_parts)} FROM [{schema}].[{table_name}]"
    with engine.connect() as cx:
        row = cx.execute(text(sql)).mappings().one()

    total_rows = row["TotalRows"]
    profiles = {}
    for col in columns:
        name = col["COLUMN_NAME"]
        profiles[name] = {
            "data_type": col["DATA_TYPE"],
            "total_rows": total_rows,
            "populated_count": row.get(f"{name}__populated"),
            "blank_count": row.get(f"{name}__blank"),
            "min_value": row.get(f"{name}__min"),
            "max_value": row.get(f"{name}__max"),
            "min_length": row.get(f"{name}__minlen"),
            "max_length": row.get(f"{name}__maxlen"),
            "distinct_count": row.get(f"{name}__distinct"),
        }

    distributions = {}
    with engine.connect() as cx:
        for col in columns:
            name = col["COLUMN_NAME"]
            distinct_count = profiles[name]["distinct_count"]
            if distinct_count is not None and distinct_count <= distinct_threshold:
                dist_rows = cx.execute(text(
                    f"SELECT TOP {int(top_n_values)} [{name}] AS Value, COUNT(*) AS Occurrences "
                    f"FROM [{schema}].[{table_name}] "
                    f"GROUP BY [{name}] ORDER BY COUNT(*) DESC"
                )).mappings().all()
                distributions[name] = [(r["Value"], r["Occurrences"]) for r in dist_rows]

    _write_profile(engine, table_name, "sql_table", profiles, distributions, schema=schema)
    return profiles, distributions


# --- Excel export ---------------------------------------------------------

def _safe_sheet_name(name):
    return _INVALID_SHEET_CHARS.sub("_", name)[:31]


def export_profile_to_excel(engine, output_path, schema="dbo", object_or_table=None, source_type=None):
    where_bits, params = [], {}
    if object_or_table:
        where_bits.append("ObjectOrTable = :name")
        params["name"] = object_or_table
    if source_type:
        where_bits.append("SourceType = :st")
        params["st"] = source_type
    where_clause = f" WHERE {' AND '.join(where_bits)}" if where_bits else ""

    profile_df = pd.read_sql(
        text(f"SELECT * FROM [{schema}].[FieldProfile]{where_clause} ORDER BY ObjectOrTable, FieldName"),
        engine, params=params,
    )
    values_df = pd.read_sql(
        text(
            f"SELECT * FROM [{schema}].[FieldProfileValues]{where_clause} "
            "ORDER BY ObjectOrTable, FieldName, Occurrences DESC"
        ),
        engine, params=params,
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if profile_df.empty:
            pd.DataFrame({"Message": ["No profile data found for the given filter."]}).to_excel(
                writer, sheet_name="Field Profile", index=False
            )
        else:
            for name, group in profile_df.groupby("ObjectOrTable"):
                group.drop(columns=["ObjectOrTable"]).to_excel(
                    writer, sheet_name=_safe_sheet_name(name), index=False
                )

        for name, group in values_df.groupby("ObjectOrTable"):
            group.drop(columns=["ObjectOrTable"]).to_excel(
                writer, sheet_name=_safe_sheet_name(f"{name}_Values"), index=False
            )

    return output_path
