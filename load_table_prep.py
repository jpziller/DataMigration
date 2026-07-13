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
    if not d.column_exists(engine, schema, table, parent_key_column):
        # Found in review: SQLite silently treats a double-quoted
        # identifier with no matching column as a plain string literal
        # instead of raising (a real, documented SQLite compatibility
        # quirk) -- ORDER BY/GROUP BY a constant then silently produces a
        # nonsensical but non-crashing Sort column instead of a clear
        # error. SQL Server's own bracket-quoting doesn't have this
        # failure mode (it raises "Invalid column name"), but checking
        # explicitly here means both backends fail the same clear way.
        raise ValueError(
            f"'{parent_key_column}' is not a column on {schema}.{table} -- check the parent key "
            "column name (typo, or the load table doesn't have this field yet)."
        )
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
        elif isinstance(d, sql_dialect.PostgresDialect):
            # Postgres has no updatable-CTE equivalent either, but (unlike
            # SQLite) DOES support UPDATE ... FROM a correlated subquery --
            # correlate by ctid, Postgres's own physical-row identifier
            # (its rowid analogue; stable for the duration of this single
            # UPDATE statement, which is all that's needed here). Verified
            # live against a real Postgres 16 instance, including the
            # multi-row-per-parent case this function exists for.
            cx.execute(text(f"""
                UPDATE {qualified} AS t SET {sort_col} = sub.RowNum
                FROM (
                    SELECT ctid AS _rid, ROW_NUMBER() OVER (ORDER BY {parent_col}) AS RowNum
                    FROM {qualified}
                ) sub WHERE sub._rid = t.ctid;
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
    if not d.column_exists(engine, schema, table, key_column):
        # Same SQLite quoted-identifier-as-string-literal quirk as
        # add_bulk_load_sort_column() above -- without this check, a
        # typo'd/wrong key_column on SQLite silently reports a fake
        # "duplicate" (every row groups into the same constant) instead
        # of a clear error.
        raise ValueError(
            f"'{key_column}' is not a column on {schema}.{table} -- check the migration key "
            "column name (typo, or the load table doesn't have this field yet)."
        )
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
