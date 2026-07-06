"""Import a Parquet file into a typed SQL Server table.

Complements replicate.py's org-to-SQL direction with a file-to-SQL one --
the "flat file" transport docs/MIGRATION_PLAYBOOK.md already discusses for
getting source data into the mirror DB, for the columnar-file case
specifically (as opposed to that doc's existing CSV/JSON guidance).

Unlike replicate.py's Salesforce path -- Bulk API 2.0 always returns text
CSV, so every value needs coercing back to a native type (see
type_map.py's typed_value_coercers) -- Parquet is already a typed columnar
format. pyarrow hands back real int/float/datetime values directly, so
there's no coercion step here, just a schema-inference-to-SQL-Server-DDL
step (_arrow_type_to_sql), mirroring type_map.py's sf_type_to_sql for the
Salesforce side.

Reads via pyarrow.parquet.ParquetFile.iter_batches() rather than
pd.read_parquet() in one call, so a large file doesn't have to fit in
memory at once -- the same chunked-append pattern replicate.py already
uses for Salesforce extracts.
"""
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text


def _arrow_type_to_sql(arrow_type):
    if pa.types.is_boolean(arrow_type):
        return "BIT"
    if pa.types.is_integer(arrow_type):
        return "BIGINT" if arrow_type.bit_width > 32 else "INT"
    if pa.types.is_decimal(arrow_type):
        return f"DECIMAL({arrow_type.precision},{arrow_type.scale})"
    if pa.types.is_floating(arrow_type):
        return "FLOAT"
    if pa.types.is_timestamp(arrow_type):
        return "DATETIME2"
    if pa.types.is_date(arrow_type):
        return "DATE"
    if pa.types.is_time(arrow_type):
        return "TIME"
    if pa.types.is_binary(arrow_type) or pa.types.is_large_binary(arrow_type):
        return "VARBINARY(MAX)"
    return "NVARCHAR(MAX)"


def create_table(engine, table_name, arrow_schema, schema="dbo"):
    cols = [f"[{field.name}] {_arrow_type_to_sql(field.type)} NULL" for field in arrow_schema]
    cols_sql = ",\n    ".join(cols)
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[{table_name}];"
        ))
        cx.execute(text(
            f"CREATE TABLE [{schema}].[{table_name}] (\n    {cols_sql}\n);"
        ))


def import_parquet(engine, parquet_path, table_name, schema="dbo", batch_size=50000, append=False):
    """Import a Parquet file into a SQL Server table, inferring column
    types from the Parquet file's own schema. Drops+recreates the table
    by default -- pass append=True to add rows to an existing table with a
    compatible schema instead (e.g. loading a second file into the same
    table)."""
    pf = pq.ParquetFile(parquet_path)

    if not append:
        create_table(engine, table_name, pf.schema_arrow, schema=schema)

    total = 0
    for batch in pf.iter_batches(batch_size=batch_size):
        df = batch.to_pandas()
        df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False, chunksize=1000)
        total += len(df)
    return total
