"""Load-table pre-flight checks -- hard rules 6/7.

Originally two SQL Server stored procedures (sql/functions/utilities/
AddBulkLoadSortColumn.sql, CheckLoadTableDuplicateKeys.sql). Retired in
favor of plain Python + inline SQL via sql_dialect.py, so both work on any
supported backend without a SQL-Server-only CREATE PROCEDURE/EXEC step --
these are now real cli.py commands, not a sqlcmd step a human runs by hand.
"""
from sqlalchemy import text

import sql_dialect


def add_bulk_load_sort_column(engine, table, parent_key_column, schema="dbo"):
    """Hard rule 6: adds/refreshes an integer Sort column on a load table,
    numbered by ROW_NUMBER() OVER (ORDER BY parent_key_column), so every row
    sharing the same parent lands in a contiguous Sort range -- bulk_op()
    orders by Sort when present (see bulkops.py) so parent/child rows stay
    together in the same submitted batch instead of being scattered across
    batches that process concurrently and lock-contend on the shared parent.

    Returns a list of {ParentKey, MinSort, MaxSort, RowCount, SortSpan} for
    every parent key whose rows ended up in a non-contiguous Sort range --
    empty means a clean sort."""
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, table)
    sort_col = d.quote_ident("Sort")
    parent_col = d.quote_ident(parent_key_column)

    with engine.begin() as cx:
        if not d.column_exists(engine, schema, table, "Sort"):
            cx.execute(text(f"ALTER TABLE {qualified} ADD {sort_col} INTEGER NULL;"))

        if isinstance(d, sql_dialect.MssqlDialect):
            # T-SQL lets an UPDATE target a CTE that's a direct reference to
            # the underlying table -- an idiomatic way to number rows and
            # write them back in one statement.
            cx.execute(text(f"""
                WITH NumberedRows AS (
                    SELECT {sort_col}, ROW_NUMBER() OVER (ORDER BY {parent_col}) AS RowNum
                    FROM {qualified}
                )
                UPDATE NumberedRows SET {sort_col} = RowNum;
            """))
        else:
            # SQLite has no updatable-CTE equivalent -- correlate by the
            # table's own implicit rowid instead.
            cx.execute(text(f"""
                UPDATE {qualified} SET {sort_col} = (
                    SELECT sub.RowNum FROM (
                        SELECT rowid AS _rid, ROW_NUMBER() OVER (ORDER BY {parent_col}) AS RowNum
                        FROM {qualified}
                    ) sub WHERE sub._rid = {qualified}.rowid
                );
            """))

        # RowCount is bracketed/quoted below -- SQL Server treats a bare
        # RowCount alias as colliding with SET ROWCOUNT/@@ROWCOUNT
        # (confirmed live: "Incorrect syntax near the keyword 'RowCount'"
        # without quoting), the same reserved-word collision
        # source_ingestion.py's own SourceIngestionLog.[RowCount] column
        # already has to work around.
        row_count_col = d.quote_ident("RowCount")
        rows = cx.execute(text(f"""
            SELECT {parent_col} AS ParentKey,
                   MIN({sort_col}) AS MinSort, MAX({sort_col}) AS MaxSort, COUNT(*) AS {row_count_col},
                   MAX({sort_col}) - MIN({sort_col}) AS SortSpan
            FROM {qualified}
            GROUP BY {parent_col}
            HAVING MAX({sort_col}) - MIN({sort_col}) <> COUNT(*) - 1
        """)).mappings().all()

    return [dict(r) for r in rows]


def check_load_table_duplicate_keys(engine, table, key_column, schema="dbo"):
    """Hard rule 7: checks a load table's migration-key column for
    duplicate or missing values before bulkops -- either breaks
    fingerprint-based result mapping on insert (see bulkops.py's own
    docstring: Bulk API 2.0 echoes back sent columns with no row-order
    guarantee, so two identical migration keys produce an identical
    fingerprint and can't be told apart when writing Id/Error back).

    Returns (duplicates, missing_key_count): duplicates is a list of
    {DuplicateKey, Occurrences}; duplicates == [] and missing_key_count == 0
    together mean clean to load."""
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, table)
    key_col = d.quote_ident(key_column)

    with engine.connect() as cx:
        duplicates = cx.execute(text(f"""
            SELECT {key_col} AS DuplicateKey, COUNT(*) AS Occurrences
            FROM {qualified}
            WHERE {key_col} IS NOT NULL
            GROUP BY {key_col}
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
        """)).mappings().all()

        missing_key_count = cx.execute(text(f"""
            SELECT COUNT(*) FROM {qualified} WHERE {key_col} IS NULL
        """)).scalar()

    return [dict(r) for r in duplicates], missing_key_count
