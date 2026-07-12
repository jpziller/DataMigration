"""Reset-dev-cycle command (roadmap #63).

Codifies the manual reset ritual this project's own dogfooding did by
hand, repeatedly, across earlier sessions (see docs/ORCHESTRATOR_DESIGN.md's
field notes: "a full reset -- org records deleted, scripts/docs/SQLite
wiped -- before each of three consecutive full Dev-tier cycles") into one
command, instead of remembering the steps each time.

Two distinct halves, kept genuinely separate because they have very
different risk profiles:
  - reset_dev_cycle_tables() -- mirror-DB-only (Hard Rule 1): drops every
    <Object>_Mock/_Mock_Adversarial/_Load/_Load_Result/_Load_Retry/_Purge/
    _Purge_Result table for the given objects, and clears their
    dbo.FieldProfile/FieldProfileValues rows -- so the next
    profile-salesforce/profile-sql-table call doesn't silently skip
    re-profiling a rebuilt table (roadmap #47's own skip-if-already-
    profiled behavior would otherwise misread a dropped-and-rebuilt table
    as still current). Always safe.
  - purge_org_test_data() -- a real Salesforce delete, via bulkops.py's
    own purge_by_filter() (#32) -- optional, requires an explicit WHERE
    clause per object (never a delete-everything default), and is exactly
    as Live-Org-Write-Confirmation-gated (Hard Rule 2) as any other
    delete. Kept as a thin, undisguised pass-through -- this is not a
    separate delete mechanism, it's the same one.

Deliberately leaves sql/transformations/*.sql, mapping docs, and every
org-metadata-derived cache (dbo.ObjectAutomationRisk, dbo.RecordTypeMap,
dbo.SourceRegistry/AutoMapSuggestions) untouched -- those are either
real, committed artifacts a reset must never silently erase, or reflect
the target ORG's own state (which a Dev-cycle reset doesn't change), not
this project's own iteration-specific mock/test data.
"""
from sqlalchemy import text

import bulkops
import sql_dialect

_TABLE_SUFFIXES = (
    "_Mock", "_Mock_Adversarial", "_Load", "_Load_Result", "_Load_Retry",
    "_Purge", "_Purge_Result",
)


def reset_dev_cycle_tables(engine, object_names, schema="dbo"):
    """Drop every _TABLE_SUFFIXES table for each name in object_names,
    and clear their dbo.FieldProfile/FieldProfileValues rows (if that
    table exists yet). Idempotent -- a table/row set that's already gone
    is silently skipped, not an error.

    Returns {"dropped": ["schema.table", ...], "profiling_cleared":
    [object_name, ...]}."""
    d = sql_dialect.for_engine(engine)
    dropped = []

    for object_name in object_names:
        for suffix in _TABLE_SUFFIXES:
            table_name = f"{object_name}{suffix}"
            if d.table_exists(engine, schema, table_name):
                with engine.begin() as cx:
                    cx.execute(text(f"DROP TABLE {d.qualify(schema, table_name)};"))
                dropped.append(f"{schema}.{table_name}")

    profiling_cleared = []
    if d.table_exists(engine, schema, "FieldProfile"):
        has_values_table = d.table_exists(engine, schema, "FieldProfileValues")
        with engine.begin() as cx:
            for object_name in object_names:
                result = cx.execute(
                    text(f"DELETE FROM {d.qualify(schema, 'FieldProfile')} WHERE ObjectOrTable = :name"),
                    {"name": object_name},
                )
                if result.rowcount:
                    profiling_cleared.append(object_name)
                if has_values_table:
                    cx.execute(
                        text(f"DELETE FROM {d.qualify(schema, 'FieldProfileValues')} WHERE ObjectOrTable = :name"),
                        {"name": object_name},
                    )

    return {"dropped": dropped, "profiling_cleared": profiling_cleared}


def purge_org_test_data(sf, engine, object_name, where, schema="dbo", dry_run=False):
    """Thin, undisguised pass-through to bulkops.purge_by_filter() (#32)
    -- kept here only so reset-dev-cycle's CLI command has one module to
    call for both halves of the reset; this is exactly the same real,
    Hard-Rule-2-gated delete purge_by_filter() always is, not a separate
    or softer mechanism."""
    return bulkops.purge_by_filter(sf, engine, object_name, where, schema=schema, dry_run=dry_run)
