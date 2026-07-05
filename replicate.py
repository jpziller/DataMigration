"""Object replication: org -> SQL Server mirror table.

replicate() drops+recreates a typed SQL Server table matching the object's
describe, extracts every record via Bulk API 2.0 (low-memory CSV download),
and loads the CSVs into the table.

Pass raw=True to make every column NVARCHAR(MAX) instead of typed columns.
That sidesteps datetime/decimal/bit coercion at load time and lets you CAST
in T-SQL during transform -- the SQL-centric path.
"""
import glob
import os

import pandas as pd
from sqlalchemy import text

from type_map import sf_type_to_sql, is_compound, typed_value_coercers


def _query_columns(desc):
    return [f["name"] for f in desc["fields"] if not is_compound(f)]


def _boolean_columns(desc):
    return {f["name"] for f in desc["fields"] if f["type"] == "boolean"}


def create_table(engine, object_name, desc, schema="dbo", raw=False):
    cols = []
    for f in desc["fields"]:
        if is_compound(f):
            continue
        col_type = "NVARCHAR(MAX)" if raw else sf_type_to_sql(f)
        cols.append(f'[{f["name"]}] {col_type} NULL')
    cols_sql = ",\n    ".join(cols)
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.{object_name}', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[{object_name}];"
        ))
        cx.execute(text(
            f"CREATE TABLE [{schema}].[{object_name}] (\n    {cols_sql}\n);"
        ))


def replicate(sf, engine, object_name, stage_dir, schema="dbo",
              where=None, raw=False, chunksize=50000):
    desc = getattr(sf, object_name).describe()
    cols = _query_columns(desc)
    bool_cols = _boolean_columns(desc)
    coercers = {} if raw else typed_value_coercers(desc)

    create_table(engine, object_name, desc, schema=schema, raw=raw)

    soql = f"SELECT {', '.join(cols)} FROM {object_name}"
    if where:
        soql += f" WHERE {where}"

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
                        chunk[c] = chunk[c].map(
                            {"true": 1, "false": 0}
                        ).where(chunk[c].isin(["true", "false"]))
            for c, fn in coercers.items():
                if c in chunk.columns:
                    chunk[c] = chunk[c].map(fn)
            chunk.to_sql(object_name, engine, schema=schema,
                         if_exists="append", index=False, chunksize=1000)
            total += len(chunk)
    return total
