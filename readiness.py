"""Migration readiness score (roadmap #65).

One aggregate go/no-go view instead of manually checking five different
tables/commands to answer "are we actually ready for this pass." Per
object, re-checks (cheap, read-only, deterministic) or re-presents every
gate this framework already enforces individually -- no new checks
invented, purely a re-presentation/re-run of what already exists:

  - Parent-Batch Sort Rule (hard rule 6) -- only applies to an object
    with a parent already on file in dbo.ObjectDependency (from
    analyze-load-order); an object with no in-scope parent is never
    flagged for a missing Sort column.
  - Migration Key Integrity Rule (hard rule 7) -- re-runs
    load_table_prep.check_load_table_duplicate_keys() live.
  - Live Migration Key Validation Rule (hard rule 12) -- re-runs
    metadata.validate_external_id_field() live against the real org.
  - analyze-org-risk scan coverage (#5) -- has dbo.ObjectAutomationRisk
    got rows for this object at all (the same "scanned vs. never
    scanned" signal orchestrator.py/risk_analyzer.py's ScanCompleted
    marker already makes checkable)?
  - check-mapping-balance (#3) -- re-runs it live against the mapping
    doc + the object's real transform script, auto-resolved via
    script_numbering.script_filename_for() (same convention
    migration_run_book.py/mapping_doc.py already use).
  - Email Deliverability attestation (hard rule 9) -- a human
    attestation, never auto-checked; this can only confirm the flag was
    recorded on the most recent BulkOpsLog insert/update/upsert run, not
    verify the live Setup value. Skipped (not just unchecked) when the
    most recent run was a delete, since deletes never need it.
  - Row-count reconciliation (#64) -- folded in directly by calling
    reconciliation.py, not reimplemented.

Two gates need a per-object parameter this module can never safely
guess -- the migration-key field name (migration_keys) and the mapping
doc path (mapping_path) -- both optional; leaving an object out just
reports that gate as "not checked," never assumed clean. A gate that's
not applicable or not checked does NOT block the overall "ready"
verdict by itself (only an explicit failure does) -- it's still
reported, so a human can judge whether that gap matters for this pass.
"""
import os

from sqlalchemy import text

import load_table_prep
import mapping_doc
import metadata
import script_numbering
import sql_dialect
from reconciliation import reconcile_load_counts

_TRANSFORMS_DIR = os.path.join("sql", "transformations")


def _sort_column_gate(engine, d, schema, object_name, load_table):
    if not d.table_exists(engine, schema, "ObjectDependency"):
        return {"ok": None, "detail": "dbo.ObjectDependency doesn't exist yet -- run analyze-load-order first."}
    with engine.connect() as cx:
        # Exclude a self-reference (ChildObject == ParentObject, e.g.
        # Account.ParentId/MasterRecordId) -- found via a real dogfood
        # run: a self-referencing object has no actual CROSS-object parent
        # to batch against (that's a two-pass-load field, never mocked --
        # see load_order.py's own self_references tracking), so it was
        # wrongly flagged "Missing Sort column" here even with no in-scope
        # parent at all.
        has_parent = cx.execute(
            text(
                f"SELECT COUNT(*) FROM {d.qualify(schema, 'ObjectDependency')} "
                "WHERE ChildObject = :obj AND ParentObject != :obj"
            ),
            {"obj": object_name},
        ).scalar() > 0
    if not has_parent:
        return {"ok": None, "detail": "No parent in scope -- Sort column not required."}
    if not d.table_exists(engine, schema, load_table):
        return {"ok": None, "detail": f"Load table {load_table} doesn't exist yet."}
    has_sort = d.column_exists(engine, schema, load_table, "Sort")
    return {"ok": has_sort, "detail": "Sort column present." if has_sort
            else "Missing Sort column -- run add-bulk-load-sort-column."}


def _duplicate_key_gate(engine, d, schema, load_table, migration_key_field):
    if migration_key_field is None:
        return {"ok": None, "detail": "Not checked -- no --migration-key given for this object."}
    if not d.table_exists(engine, schema, load_table):
        return {"ok": None, "detail": f"Load table {load_table} doesn't exist yet."}
    try:
        duplicates, missing = load_table_prep.check_load_table_duplicate_keys(
            engine, load_table, migration_key_field, schema=schema
        )
    except ValueError as e:
        # check_load_table_duplicate_keys() now raises a clear error for a
        # migration-key column that doesn't actually exist on the Load
        # table (found in review: without that check, SQLite silently
        # reported a fake "duplicate" instead of failing loudly) -- an
        # explicit failure here, not a crash of the whole multi-object,
        # multi-gate readiness assessment over one bad --migration-key.
        return {"ok": False, "detail": str(e)}
    ok = not duplicates and not missing
    detail = "Clean." if ok else f"{len(duplicates)} duplicate value(s), {missing} missing key value(s)."
    return {"ok": ok, "detail": detail}


def _external_id_gate(sf, object_name, migration_key_field):
    if migration_key_field is None:
        return {"ok": None, "detail": "Not checked -- no --migration-key given for this object."}
    result = metadata.validate_external_id_field(sf, object_name, migration_key_field)
    detail = "Valid externalId+unique field." if result["ok"] else "; ".join(result["problems"])
    return {"ok": result["ok"], "detail": detail}


def _org_risk_gate(engine, d, schema, object_name):
    if not d.table_exists(engine, schema, "ObjectAutomationRisk"):
        return {"ok": False, "detail": "dbo.ObjectAutomationRisk doesn't exist yet -- run analyze-org-risk."}
    with engine.connect() as cx:
        count = cx.execute(
            text(f"SELECT COUNT(*) FROM {d.qualify(schema, 'ObjectAutomationRisk')} WHERE ObjectName = :obj"),
            {"obj": object_name},
        ).scalar()
    return {"ok": bool(count), "detail": "Scanned." if count else "Never scanned -- run analyze-org-risk."}


def _mapping_balance_gate(sf, mapping_path, object_name, load_table, known_objects=None, script_dir=None):
    if not mapping_path:
        return {"ok": None, "detail": "Not checked -- no --mapping-path given."}
    search_dir = script_dir if script_dir is not None else _TRANSFORMS_DIR
    script_filename = script_numbering.script_filename_for(object_name, search_dir, known_objects=known_objects)
    if not script_filename:
        return {"ok": None, "detail": "No transform script found for this object yet."}
    script_path = os.path.join(search_dir, script_filename)
    try:
        balance = mapping_doc.check_mapping_balance(sf, mapping_path, object_name, script_path, load_table_name=load_table)
    except (ValueError, FileNotFoundError) as e:
        # openpyxl.load_workbook() raises FileNotFoundError for a bad
        # --mapping-path, not ValueError -- found in review: this used to
        # crash the whole multi-object assess_migration_readiness() call
        # over one bad path, the exact same bug class as pass_summary.py's
        # already-fixed crash, and the fix pattern (catch the file-missing
        # case, report "not checked" instead of a raw traceback) already
        # existed right next door in reconciliation.py's own
        # _source_table_from_mapping().
        return {"ok": None, "detail": str(e)}

    ok = not any(balance.values())
    if ok:
        return {"ok": True, "detail": "Mapping doc and transform agree."}
    problems = []
    if balance["documented_not_implemented"]:
        problems.append(f"documented but not implemented: {balance['documented_not_implemented']}")
    if balance["implemented_not_documented"]:
        problems.append(f"implemented but not documented: {balance['implemented_not_documented']}")
    if balance["not_a_real_field"]:
        problems.append(f"not a real field: {balance['not_a_real_field']}")
    if balance["duplicate_target_fields"]:
        problems.append(f"duplicate target fields: {list(balance['duplicate_target_fields'])}")
    if balance["duplicate_implemented_columns"]:
        problems.append(f"duplicate implemented columns: {balance['duplicate_implemented_columns']}")
    return {"ok": False, "detail": "; ".join(problems)}


def _email_deliverability_gate(engine, d, schema, object_name):
    if not d.table_exists(engine, schema, "BulkOpsLog"):
        return {"ok": None, "detail": "Not checked -- dbo.BulkOpsLog doesn't exist yet (no bulkops run logged)."}
    query = d.select_top_n_sql(
        "Operation, EmailDeliverability",
        f"FROM {d.qualify(schema, 'BulkOpsLog')} WHERE ObjectName = :obj ORDER BY LogId DESC",
        1,
    )
    with engine.connect() as cx:
        row = cx.execute(text(query), {"obj": object_name}).mappings().first()
    if row is None:
        return {"ok": None, "detail": "Not checked -- no BulkOpsLog row for this object yet."}
    # Normalized to lowercase keys once here rather than accessed by exact
    # case -- see orchestrator.py's own _row_to_current() for the
    # identical fix and why it's needed (Postgres returns an unquoted
    # column lowercased in its own query results, unlike SQL Server/
    # SQLite).
    row = sql_dialect.lower_keys(row)
    if (row["operation"] or "").lower() == "delete":
        return {"ok": None, "detail": "Most recent run was a delete -- Email Deliverability attestation not required."}
    value = row["emaildeliverability"]
    ok = bool(value)
    detail = f"Attested as '{value}' on the most recent run." if ok \
        else "No Email Deliverability attestation recorded on the most recent run."
    return {"ok": ok, "detail": detail}


def _reconciliation_gate(engine, object_name, schema, mapping_path, load_table):
    result = reconcile_load_counts(
        engine, [object_name], schema=schema, mapping_path=mapping_path,
        load_tables={object_name: load_table},
    )[0]
    if result["load_count"] is None:
        # Same "not yet, not a failure" treatment as every other gate's
        # missing-Load-table case (found in review: this gate originally
        # treated reconcile_load_counts()'s own "doesn't exist yet" flag
        # as an explicit failure, inconsistent with every other gate here
        # reporting that exact state as ok=None instead).
        return {"ok": None, "detail": f"Load table {load_table} doesn't exist yet."}
    # "Never loaded via bulkops yet" is the normal, expected state for an
    # object about to have its FIRST pass -- exactly when a readiness
    # check is meant to run -- so it never blocks readiness on its own
    # (found in review: every object's first-ever load was incorrectly
    # reported NOT READY before this fix). Still shown in the detail text
    # for context; every OTHER reconciliation flag (dropped rows, a stale
    # prior run) still blocks readiness as before.
    blocking_flags = [f for f in result["flags"] if "Never loaded via bulkops" not in f]
    ok = not blocking_flags
    detail = "Clean." if not result["flags"] else "; ".join(result["flags"])
    return {"ok": ok, "detail": detail}


def assess_migration_readiness(sf, engine, object_names, schema="dbo",
                                migration_keys=None, mapping_path=None, load_tables=None,
                                script_dir=None):
    """Aggregate go/no-go readiness per object in object_names.

    migration_keys: optional {object_name: field_name} -- enables the
    Migration Key Integrity / Live Migration Key Validation gates for
    that object; left out, both report "not checked," never assumed
    clean.
    mapping_path: optional -- enables the check-mapping-balance gate for
    every object (also feeds the row-count reconciliation gate's
    source-count half).
    load_tables: optional {object_name: table_name} override -- defaults
    to <object_name>_Load.
    script_dir: optional -- resolve the mapping-balance gate's transform
    script from here instead of the default sql/transformations/ (see
    CLAUDE.md's "Library vs. attempts workspace" section). None
    reproduces today's exact behavior.

    Returns [{"object", "load_table", "gates": {gate_name: {"ok",
    "detail"}, ...}, "ready": bool, "blocking": [gate_name, ...]}, ...].
    A gate's "ok" is True/False/None (not applicable or not checked) --
    only an explicit False blocks the overall "ready" verdict; None
    gates are still reported, never silently assumed clean."""
    migration_keys = migration_keys or {}
    load_tables = load_tables or {}
    d = sql_dialect.for_engine(engine)
    known_objects = set(object_names)

    results = []
    for object_name in object_names:
        load_table = load_tables.get(object_name, f"{object_name}_Load")
        migration_key = migration_keys.get(object_name)

        gates = {
            "parent_batch_sort": _sort_column_gate(engine, d, schema, object_name, load_table),
            "migration_key_integrity": _duplicate_key_gate(engine, d, schema, load_table, migration_key),
            "live_migration_key_validation": _external_id_gate(sf, object_name, migration_key),
            "org_risk_scanned": _org_risk_gate(engine, d, schema, object_name),
            "mapping_balance": _mapping_balance_gate(sf, mapping_path, object_name, load_table, known_objects=known_objects, script_dir=script_dir),
            "email_deliverability_attested": _email_deliverability_gate(engine, d, schema, object_name),
            "row_count_reconciliation": _reconciliation_gate(engine, object_name, schema, mapping_path, load_table),
        }
        blocking = [name for name, g in gates.items() if g["ok"] is False]
        results.append({
            "object": object_name, "load_table": load_table,
            "gates": gates, "ready": not blocking, "blocking": blocking,
        })
    return results
