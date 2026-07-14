"""SFDMU (forcedotcom/SFDX-Data-Move-Utility) as an alternate `bulkops` load
engine -- opt-in via `--engine sfdmu`, never the default. The Python engine
(bulk_op() in bulkops.py) stays exactly as-is for flexibility; this module
is a second way to push a Load table to Salesforce, reusing SFDMU's mature,
Salesforce-maintained Bulk API 2.0 wrapper and relationship-graph resolver
instead of this project's own hand-rolled one.

REQUIRES: Node.js (bundled with the `sf` CLI itself) and the plugin
installed once via `sf plugins install sfdmu` -- not a Python dependency,
so nothing here works unless that's been done. See README.md's setup steps.

RESULT MAPPING: reuses bulk_op()'s own machinery so Hard Rule 4 holds
identically regardless of engine -- `_preflight_check()` (schema/permission
gate before any API call), `_check_email_deliverability()` (Hard Rule 9),
`_writeback_inplace()`/`_writeback_result_table()` (Id/Error land in the
SAME SQL Load table), and `_write_bulkops_log_row()`/BulkOpsLog + Migration
Run Book sync (found missing in an earlier version of this module by a
ruthless review pass -- an sfdmu-engine load was invisible to
orchestrator-assess/assess-migration-readiness/reconcile-load-counts/
batch_advisor.py, all five of which read BulkOpsLog as their one source of
truth for "did this object get loaded," regardless of engine; now written
identically to bulk_op()'s own call). Results are matched back to source
rows by the external id column itself (confirmed live: SFDMU's own target
CSV echoes back the original business columns, including the external id,
whenever nothing goes wrong) -- not SFDMU's own synthetic "Old Id"
placeholder scheme, which exists for its other use cases (e.g. a CSV
source with no natural key) but isn't needed here since every Load table
in this framework already carries a real migration key.

V1 SCOPE -- upsert/update only, not insert/delete:
Every Load table here already carries a real migration key (Hard Rules
4/7), and upsert/update match results unambiguously via that key. Plain
insert (no external id) relies on SFDMU's own "Id column as placeholder"
CSV convention, which is murkier to match back reliably -- deferred, not
silently guessed at. Delete is out of scope for the same reason bulk_op()
itself treats it specially (Bulk API 2.0 delete only accepts a real Id, no
external-id form exists at the API level).

PARENT LOOKUP RESOLUTION -- the one real gotcha, found live this session
via `--simulation` mode testing against a real org (never a live write)
plus reading the installed plugin's own compiled source, not assumed from
docs:

  SFDMU's relationship engine DOES correctly resolve an already-loaded
  parent's real target Id into a child's lookup field (e.g.
  Contact_Load.AccountId, populated by Account's own earlier bulkops load)
  -- but only with a specific declaration, confirmed by tracing the actual
  exclusion warning in the plugin's own log output:
    "{Account} Only Id remains in the query, so the object will be
     excluded from the migration" -- which then cascades to
    "{Contact.AccountId} Lookup removed because referenced object Account
     is excluded."
  A parent object declared with ONLY `Id` in its query is treated as a
  degenerate/unused declaration and dropped, silently stripping any lookup
  pointing at it. The fix: give the parent's query one more field (`Name`,
  present on every object) alongside `Id`, declare `"externalId": "Id"`
  (ScriptObject.hasAutonumberExternalId -- SFDMU's own recognized
  "this value is already a resolved Id, match directly" case), and mark it
  `"operation": "Readonly"` (correctly signals "don't write to this
  object, it's already fully loaded"). With all three, a real target Id
  flows through with zero errors/warnings -- verified directly against
  Contact_Load/Account_Load from this project's own dogfood data.

  Each declared parent also needs its OWN source CSV (the distinct,
  already-resolved parent Ids actually referenced) -- without one, SFDMU
  has no source-side data to correlate the "externalId: Id" match against,
  and the field resolves blank instead of erroring (found live, a distinct
  failure mode from the "Only Id" exclusion above). When two different
  sent lookup columns reference the SAME parent object, their distinct Id
  sets are unioned into that one parent's CSV -- a ruthless review found
  the earlier version of this module wrote one lookup column's CSV, then
  unconditionally overwrote it with a second column's CSV for the same
  parent, silently dropping any Id only referenced by the first column.

  Self-referencing lookups (a field whose single referenceTo target is the
  object being loaded itself, e.g. Account.ParentId) are excluded from
  parent-object resolution entirely, not left to fall through -- a
  ruthless review found that without this exclusion, the object would get
  declared TWICE in one export.json (once as the real Upsert/Update entry,
  once as a spurious Readonly "parent" entry for itself), a shape SFDMU
  isn't built to accept. A self-referencing field is genuinely out of
  scope for v1 the same way this framework's own load_order.py treats it
  (a two-pass load, never mocked -- see snowfakery_data.py) -- it's
  dropped from `sent` entirely here, same treatment as a polymorphic
  lookup, and reported back in the summary rather than silently vanishing.

  V1 ONLY HANDLES SINGLE-TARGET (non-polymorphic) LOOKUPS. A polymorphic
  field (multiple `referenceTo` targets, e.g. Task.WhatId) needs the same
  CASE-based resolution this framework's own hand-written transforms
  already use (see sql/transformations/080_task_load_postgres.sql) --
  guessing which target a polymorphic lookup resolves to isn't this
  module's job (the "No Invented Field Names" discipline, hard rule 5).
  Such fields are left out of `sent` entirely for the sfdmu engine v1;
  the caller can still load them via the Python engine as a second pass.

EXTERNAL ID FORMATTING: a migration-key column that's genuinely numeric in
SQL (or upcast to float64 by pandas because even one NULL is present --
a narrower-precondition risk this framework's own Hard Rule 7 gate is
meant to prevent, but a real reachable code path with no defensive check)
serializes via pandas' default to_csv() as "1.0", not "1". Sent to
Salesforce as a Text-typed external id, that's not merely a local matching
problem -- it would write the WRONG key value onto the record, silently
failing to match the existing row it was supposed to update.
`_stringify_migration_key()` below normalizes a whole-number float column
back to a plain integer string before it's ever written to CSV, and the
same function is reused to build local result-matching keys so both sides
agree by construction rather than by coincidence of dtype.

NOT YET CONFIRMED: whether SFDMU offers any lock-contention/batch-ordering
behavior comparable to this framework's own Hard Rule 6 ([Sort] column).
Nothing found in the installed plugin's source suggests one -- a disclosed
gap, not assumed either way.
"""
import getpass
import glob
import json
import os
import re
import shutil
from datetime import datetime, timezone

import pandas as pd

import migration_run_book
import sql_dialect
from sf_client import run_sf_cli
from bulkops import (
    _derive_sent_columns,
    _preflight_check,
    _check_email_deliverability,
    _format_datetime_columns_for_csv,
    _normalize_error_signature,
    _writeback_inplace,
    _writeback_result_table,
    _bulkops_log_table_exists,
    _write_bulkops_log_row,
)

_SFDMU_OPERATIONS = {"upsert": "Upsert", "update": "Update"}

# See sf_client.run_sf_cli()'s own docstring for why this shares that one
# subprocess seam with _run_sf() instead of re-implementing shell=True/
# subprocess.run() a second time -- broader than _run_sf()'s alnum-only
# pattern (a real filesystem path needs `/`, `\`, `:`, spaces), but still
# excludes every shell metacharacter.
_SAFE_SFDMU_ARG_RE = re.compile(r"^[A-Za-z0-9_.:\\/ -]+$")


def _run_sfdmu(source_username, target_username, path, simulation=False):
    args = [
        "sfdmu", "run",
        "--sourceusername", source_username,
        "--targetusername", target_username,
        "--path", path,
        "--noprompt", "--json",
    ]
    if simulation:
        args.append("--simulation")
    proc = run_sf_cli(args, _SAFE_SFDMU_ARG_RE, check=False)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"`sf sfdmu run` produced non-JSON output (exit code {proc.returncode}). "
            f"stdout: {proc.stdout!r}\nstderr: {proc.stderr!r}"
        ) from e


def _classify_lookup_fields(object_name, sent_columns, fields_by_name):
    """From an already-fetched describe()'s fields_by_name (fetched exactly
    once by the caller, not re-fetched here), split sent_columns's
    reference fields into: parent_objects ({column: parent}, single-target,
    not self-referencing), polymorphic_skipped (2+ targets), and
    self_ref_skipped (single target == object_name itself). Read-only, no
    Salesforce call of its own."""
    parent_objects, polymorphic_skipped, self_ref_skipped = {}, [], []
    for col in sent_columns:
        field = fields_by_name.get(col)
        if not field or field.get("type") != "reference":
            continue
        ref_to = field.get("referenceTo") or []
        if len(ref_to) > 1:
            polymorphic_skipped.append(col)
        elif len(ref_to) == 1 and ref_to[0] == object_name:
            self_ref_skipped.append(col)
        elif len(ref_to) == 1:
            parent_objects[col] = ref_to[0]
    return parent_objects, polymorphic_skipped, self_ref_skipped


def _build_export_json(object_name, operation, external_id, sent_columns, parent_objects):
    objects = []
    for parent in sorted(set(parent_objects.values())):
        # See this module's docstring: Id alone makes SFDMU treat the
        # object as degenerate and exclude it, silently stripping any
        # lookup pointing at it -- confirmed live, not assumed.
        objects.append({
            "query": f"SELECT Id, Name FROM {parent}",
            "operation": "Readonly",
            "externalId": "Id",
        })
    objects.append({
        "query": f"SELECT {', '.join(sent_columns)} FROM {object_name}",
        "operation": _SFDMU_OPERATIONS[operation],
        "externalId": external_id,
    })
    return {"objects": objects}


def _stringify_migration_key(series):
    """Render a migration-key column as clean strings before it's ever
    written to a CSV SFDMU/Salesforce will match against. See this
    module's own "EXTERNAL ID FORMATTING" docstring section -- a float64
    column (e.g. upcast from int64 by a NULL) otherwise serializes via
    pandas' to_csv() as "1.0", not "1"."""
    if pd.api.types.is_float_dtype(series):
        return series.apply(
            lambda v: (str(int(v)) if pd.notna(v) and float(v).is_integer()
                      else (str(v) if pd.notna(v) else None))
        )
    return series.astype(str).where(series.notna(), None)


def run_sfdmu_upsert(sf, engine, object_name, operation, source_table, external_id,
                     org_alias, key_column="LoadId", id_column="Id",
                     error_column="Error", ref_prefix="REF_", schema="dbo",
                     stage_dir="_stage", email_deliverability=None,
                     confirm_external_email_risk=False, run_book_path=None,
                     run_book_tab=None):
    """SFDMU-engine equivalent of bulk_op() -- upsert/update only (see this
    module's docstring for why), external_id required. Returns a summary
    dict shaped like bulk_op()'s own (submitted/succeeded/failed/
    written_to/email_deliverability/logged/...), so CLI output and every
    downstream tool that reads a bulkops summary or BulkOpsLog stays
    consistent regardless of which engine actually ran."""
    if operation not in _SFDMU_OPERATIONS:
        raise ValueError(
            f"The sfdmu engine only supports upsert/update in this version -- "
            f"got {operation!r}. insert/delete via sfdmu are out of scope for v1 "
            f"(see this module's docstring for why)."
        )
    if not external_id:
        raise ValueError(
            "The sfdmu engine requires --external-id -- every Load table in this "
            "framework already carries a real migration key (hard rules 4/7); "
            "matching results back any other way is not supported here."
        )

    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    deliverability_note = _check_email_deliverability(
        operation, email_deliverability, confirm_external_email_risk
    )

    d = sql_dialect.for_engine(engine)
    has_sort_column = d.column_exists(engine, schema, source_table, "Sort")
    order_by = f" ORDER BY {d.quote_ident('Sort')}" if has_sort_column else ""
    df = pd.read_sql(f"SELECT * FROM {d.qualify(schema, source_table)}{order_by}", engine)

    sent = _derive_sent_columns(df, operation, id_column=id_column, key_column=key_column,
                                error_column=error_column, ref_prefix=ref_prefix)

    # describe() fetched exactly once and threaded through everything below
    # -- a ruthless review found this used to be fetched three separate
    # times per call (inside _preflight_check(), again inline here, again
    # inside a since-removed _lookup_parent_objects()), each a real network
    # round-trip against the live org.
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}

    preflight = _preflight_check(sf, object_name, operation, sent, id_column=id_column, desc=desc)
    # Confirmed live: unlike the Python engine (Bulk API 2.0 tolerates a
    # redundant real Id alongside upsert's own external-id matching),
    # sending our own id_column to SFDMU makes it treat that column as ITS
    # OWN internal row-tracking key (matching its documented "CSV should
    # include the Id field" convention for a different use case) -- which
    # suppresses the full business-column echo-back in the target CSV,
    # dropping external_id along with everything else needed to match
    # results back to source rows. Dropped from what's actually sent (not
    # from `sent` above, so the pre-flight check -- which already passed --
    # still reflects what the Load table really carries).
    sent = [c for c in sent if c != id_column]
    fatal_details = []
    if preflight["not_a_real_field"]:
        fatal_details.append(f"not a real field on {object_name}: {preflight['not_a_real_field']}")
    if preflight["not_writable"]:
        fatal_details.append(f"not updateable on {object_name}: {preflight['not_writable']}")
    if fatal_details:
        raise ValueError(
            f"Pre-flight check failed for {source_table} -> {object_name} ({operation}): "
            + "; ".join(fatal_details)
        )

    # Polymorphic and self-referencing lookups aren't resolvable here (see
    # docstring) -- drop them from what's sent via sfdmu rather than
    # letting SFDMU silently mis-handle or reject them; report which ones
    # so the caller knows to load them via the Python engine as a second
    # pass instead.
    parent_objects, polymorphic_skipped, self_ref_skipped = _classify_lookup_fields(
        object_name, sent, fields_by_name
    )
    sent = [c for c in sent if c not in polymorphic_skipped and c not in self_ref_skipped]

    run_dir = os.path.join(stage_dir, "sfdmu", object_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    os.makedirs(run_dir, exist_ok=True)

    # Same datetime64-to-XSD-string fix bulk_op() already needed for the
    # Python engine's own CSV export (see _format_datetime_columns_for_csv's
    # docstring) -- confirmed live in this integration's own first real
    # test run: Contact.EmailBouncedDate failed on every one of 8 rows with
    # "Cannot deserialize instance of datetime from VALUE_STRING value
    # 2027-02-11 06:01:40" (pandas' default space-separated str(), not the
    # 'T'-separated form the API requires) before this fix was applied here.
    payload = _format_datetime_columns_for_csv(df[sent].copy())
    if external_id in payload.columns:
        payload[external_id] = _stringify_migration_key(payload[external_id])
    payload.to_csv(os.path.join(run_dir, f"{object_name}.csv"), index=False)

    # Each declared Readonly parent needs its own source CSV too -- without
    # one, SFDMU has no source-side data to correlate the "externalId: Id"
    # match against, and the lookup resolves to blank for every row rather
    # than erroring (confirmed live: a distinct failure mode from the
    # "Only Id in query" exclusion the module docstring describes). Two
    # different lookup columns referencing the SAME parent have their
    # distinct Id sets unioned into that one parent's CSV, not written
    # per-column (see docstring).
    ids_by_parent = {}
    for lookup_col, parent in parent_objects.items():
        ids_by_parent.setdefault(parent, set()).update(payload[lookup_col].dropna().unique())
    for parent, parent_ids in ids_by_parent.items():
        # A blank Name column avoids a spurious "MISSING COLUMN IN THE CSV
        # FILE" report entry (the declared query is "SELECT Id, Name FROM
        # <Parent>" -- see _build_export_json) -- confirmed live this
        # session; matching still happens on Id, Name's value is never
        # actually used for it.
        pd.DataFrame({"Id": sorted(parent_ids), "Name": ""}).to_csv(
            os.path.join(run_dir, f"{parent}.csv"), index=False
        )

    export_json = _build_export_json(object_name, operation, external_id, sent, parent_objects)
    with open(os.path.join(run_dir, "export.json"), "w", encoding="utf-8") as fh:
        json.dump(export_json, fh, indent=2)

    result = _run_sfdmu("csvfile", org_alias, run_dir)
    if result.get("status") != 0:
        raise RuntimeError(
            f"`sf sfdmu run` failed for {object_name} ({operation}): "
            f"{result.get('statusString')} -- see {run_dir}/reports/ for details."
        )

    # Confirmed live (both this session's validation spike and this
    # module's own first real test run): SFDMU always names the result
    # file "<Object>_update_target.csv", even when the declared operation
    # was "Upsert" -- not "<Object>_upsert_target.csv". Discovered by glob
    # rather than a hardcoded "_{operation}_" string -- a ruthless review
    # found the earlier hardcoded guess would break silently if a future
    # SFDMU version or an untested operation used a different naming
    # scheme; this degrades to the same explicit failure only when the
    # actual result file genuinely can't be found.
    target_dir = os.path.join(run_dir, "target")
    target_matches = glob.glob(os.path.join(target_dir, f"{object_name}_*_target.csv"))
    if len(target_matches) != 1:
        raise RuntimeError(
            f"Expected exactly one result file matching {object_name}_*_target.csv "
            f"under {target_dir}, found {len(target_matches)}: {target_matches} -- "
            f"sfdmu run may not have processed {object_name} as expected this run."
        )
    target_csv = target_matches[0]
    target_df = pd.read_csv(target_csv, dtype=str, keep_default_na=False, na_values=[""])
    if external_id not in target_df.columns:
        raise RuntimeError(
            f"{external_id!r} not present in {target_csv} -- can't match results back "
            f"to {source_table} without it. Confirmed live this session: SFDMU only "
            f"echoes back an object's original business columns when nothing goes "
            f"wrong at the field level -- if this happens, some other field in "
            f"`sent` is likely triggering the same partial-echo behavior found "
            f"during this integration's own validation spike."
        )

    # SFDMU's own "no value" sentinel in CSV output is the literal string
    # "#N/A" (confirmed live), not a genuinely blank field -- normalize to
    # None so pd.notna()/writeback treat it as no-error/no-id correctly.
    id_by_ext = {k: (v if v != "#N/A" else None)
                for k, v in zip(target_df[external_id], target_df["Id"])}
    err_by_ext = {k: (v if v != "#N/A" else None)
                 for k, v in zip(target_df[external_id], target_df["Errors"])}

    # Match on the SAME stringified external-id values actually written to
    # the outbound CSV (see _stringify_migration_key() and the "EXTERNAL ID
    # FORMATTING" docstring section), not a fresh, independent
    # re-derivation -- guarantees both sides agree by construction rather
    # than by coincidence of dtype.
    match_key = _stringify_migration_key(df[external_id])
    df["_result_id"] = match_key.map(id_by_ext)
    df["_result_error"] = match_key.map(err_by_ext)

    # Confirmed live: for an update-by-external-id, SFDMU populates "Id"
    # once the record is matched, REGARDLESS of whether the actual DML then
    # succeeded or failed (unlike the Python engine's Bulk API 2.0 path,
    # which splits into two genuinely separate success/failure result
    # sets) -- so success/failure has to be decided by Errors, not by
    # whether an Id came back. A row whose external id value never
    # appears in target_df at all (both columns NaN) counts as neither --
    # surfaced separately as "unmatched" rather than silently folded into
    # "failed", since that's a distinct, more surprising outcome.
    matched = df["_result_id"].notna() | df["_result_error"].notna()
    n_ok = int((matched & df["_result_error"].isna()).sum())
    n_err = int(df["_result_error"].notna().sum())
    n_unmatched = int((~matched).sum())
    failure_error_counts = {}
    for msg, count in df["_result_error"].dropna().value_counts().items():
        key = _normalize_error_signature(msg)
        failure_error_counts[key] = failure_error_counts.get(key, 0) + int(count)

    if key_column in df.columns:
        _writeback_inplace(engine, schema, source_table, df, key_column, id_column, error_column)
        written_to = f"{schema}.{source_table}"
    else:
        written_to = _writeback_result_table(engine, schema, source_table, df, sent,
                                             id_column, error_column)

    completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    summary = {
        "engine": "sfdmu",
        "operation": operation,
        "object": object_name,
        "submitted": len(df),
        "succeeded": n_ok,
        "failed": n_err,
        "unmatched": n_unmatched,
        "written_to": written_to,
        "email_deliverability": deliverability_note,
        "parent_objects_declared": sorted(set(parent_objects.values())),
        "polymorphic_fields_skipped": polymorphic_skipped,
        "self_referencing_fields_skipped": self_ref_skipped,
        "failure_error_counts": failure_error_counts,
    }

    # Activity logging -- same opt-in, per-schema BulkOpsLog convention
    # bulk_op() itself uses (see bulkops.py's own ACTIVITY LOGGING
    # docstring section). A ruthless review found this missing entirely in
    # an earlier version of this module: without it, an sfdmu-engine load
    # was invisible to orchestrator-assess (which crashed outright),
    # assess-migration-readiness, reconcile-load-counts, and
    # batch_advisor.py -- all five read BulkOpsLog as their one source of
    # truth for "did this object get loaded," regardless of engine.
    summary["logged"] = False
    if _bulkops_log_table_exists(engine, schema):
        try:
            _write_bulkops_log_row(engine, schema, {
                "operation": operation,
                "object_name": object_name,
                "source_table": source_table,
                "target_schema": schema,
                "submitted": len(df),
                "succeeded": n_ok,
                "failed": n_err,
                "ambiguous": 0,
                "external_id_not_found": 0,
                "job_count": 1,
                "email_deliverability": deliverability_note,
                "written_to": written_to,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_seconds": (completed_at - started_at).total_seconds(),
                "run_by": getpass.getuser(),
                "batch_size": None,
                "batch_size_source": "sfdmu",
                "lock_error_count": 0,
                "failure_error_counts": json.dumps(failure_error_counts),
            })
            summary["logged"] = True
        except Exception as e:
            # The real load and its writeback already succeeded above --
            # a logging failure shouldn't take that result away, just
            # surface itself rather than fail silently (same precedent as
            # bulk_op()'s own logging_error handling).
            summary["logging_error"] = str(e)

    # Migration Run Book sync -- same opt-in convention as bulk_op()'s own
    # --run-book/--run-book-tab. A ruthless review found the CLI previously
    # accepted and validated these flags for --engine sfdmu without ever
    # honoring them, silently no-op'ing with no warning that the Run Book
    # was never touched.
    if run_book_path and run_book_tab and summary["logged"]:
        try:
            summary["run_book_synced"] = migration_run_book.sync_run_book_from_log(
                engine, run_book_path, run_book_tab, schema=schema
            )
        except Exception as e:
            summary["run_book_sync_error"] = str(e)

    return summary
