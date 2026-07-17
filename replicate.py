"""Object replication: org -> mirror table (SQL Server or SQLite).

replicate() drops+recreates a typed mirror table matching the object's
describe, extracts every record via Bulk API 2.0 (low-memory CSV download),
and loads the CSVs into the table. See sql_dialect.py for the backend-aware
DDL/type-mapping this delegates to.

Pass raw=True to make every column this backend's "store anything as text"
type (NVARCHAR(MAX) on SQL Server, TEXT on SQLite) instead of typed columns.
That sidesteps datetime/decimal/bit coercion at load time and lets you CAST
during transform -- the SQL-centric path.
"""
import glob
import os

import pandas as pd
from sqlalchemy import text

import sql_dialect
from type_map import is_compound, typed_value_coercers


def _query_columns(desc):
    return [f["name"] for f in desc["fields"] if not is_compound(f)]


def _boolean_columns(desc):
    return {f["name"] for f in desc["fields"] if f["type"] == "boolean"}


def create_table(engine, object_name, desc, schema="dbo", raw=False):
    d = sql_dialect.for_engine(engine)
    cols = []
    for f in desc["fields"]:
        if is_compound(f):
            continue
        col_type = d.raw_text_type() if raw else d.sf_type_to_sql(f)
        cols.append(f'{d.quote_ident(f["name"])} {col_type} NULL')
    cols_sql = ",\n    ".join(cols)
    qualified = d.qualify(schema, object_name)
    already_exists = d.table_exists(engine, schema, object_name)
    with engine.begin() as cx:
        if already_exists:
            cx.execute(text(f"DROP TABLE {qualified};"))
        cx.execute(text(
            f"CREATE TABLE {qualified} (\n    {cols_sql}\n);"
        ))


def replicate(sf, engine, object_name, stage_dir, schema="dbo",
              where=None, limit=None, raw=False, chunksize=50000):
    desc = getattr(sf, object_name).describe()
    cols = _query_columns(desc)
    bool_cols = _boolean_columns(desc)
    coercers = {} if raw else typed_value_coercers(desc)

    create_table(engine, object_name, desc, schema=schema, raw=raw)

    soql = f"SELECT {', '.join(cols)} FROM {object_name}"
    if where:
        soql += f" WHERE {where}"
    if limit is not None:
        soql += f" LIMIT {int(limit)}"

    out_dir = os.path.join(stage_dir, object_name)
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "*.csv")):
        os.remove(old)

    # Bulk API 2.0 query download -> CSV part files, low memory.
    getattr(sf.bulk2, object_name).download(
        soql, path=out_dir, max_records=200000
    )

    total = 0
    for part in sorted(glob.glob(os.path.join(out_dir, "*.csv"))):
        for chunk in pd.read_csv(
            part, dtype=str, chunksize=chunksize,
            keep_default_na=False, na_values=[""],
        ):
            if not raw and bool_cols:
                for c in bool_cols:
                    if c in chunk.columns:
                        # Real Python True/False, not 1/0 -- found via
                        # live Postgres testing (roadmap #69): SQL
                        # Server's BIT and SQLite's INTEGER both accept a
                        # plain integer for a boolean-ish column, but
                        # Postgres's native BOOLEAN column rejects an
                        # integer outright ("column is of type boolean
                        # but expression is of type integer"). A real
                        # Python bool binds correctly to all three
                        # (pyodbc/sqlite3/psycopg2 each adapt it to their
                        # own column type), the same way risk_analyzer.py's
                        # own IsActive/DirectHit BIT columns already do.
                        chunk[c] = chunk[c].map(
                            {"true": True, "false": False}
                        ).where(chunk[c].isin(["true", "false"]))
            for c, fn in coercers.items():
                if c in chunk.columns:
                    chunk[c] = chunk[c].map(fn)
            chunk.to_sql(object_name, engine, schema=schema,
                         if_exists="append", index=False, chunksize=1000)
            total += len(chunk)
    return total
