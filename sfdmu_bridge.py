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
and `_writeback_inplace()`/`_writeback_result_table()` (Id/Error land in the
SAME SQL Load table, so reconcile-load-counts/triage-failures/
migration_run_book sync don't need to know or care which engine wrote the
data). Results are matched back to source rows by the external id column
itself (confirmed live: SFDMU's own target CSV echoes back the original
business columns, including the external id, whenever nothing goes wrong)
-- not SFDMU's own synthetic "Old Id" placeholder scheme, which exists for
its other use cases (e.g. a CSV source with no natural key) but isn't
needed here since every Load table in this framework already carries a
real migration key.

V1 SCOPE -- upsert/update only, not insert/delete:
Every Load table here already carries a real migration key (Hard Rules
4/7), and upsert/update match results unambiguously via that key. Plain
insert (no external id) relies on SFDMU's own "Id column as placeholder"
CSV convention, which is murkier to match back reliably -- deferred, not
silently guessed at. Delete is out of scope for the same reason bulk_op()
itself treats it specially (Bulk API 2.0 delete only accepts a real Id, no
external-id form exists at the API level).

PARENT LOOKUP RESOLUTION -- the one real gotcha, found live this session
(roadmap: see the SFDMU integration entry) via `--simulation` mode testing
against a real org (never a live write) plus reading the installed
plugin's own compiled source, not assumed from docs:

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

  V1 ONLY HANDLES SINGLE-TARGET (non-polymorphic) LOOKUPS. A polymorphic
  field (multiple `referenceTo` targets, e.g. Task.WhatId) needs the same
  CASE-based resolution this framework's own hand-written transforms
  already use (see sql/transformations/080_task_load_postgres.sql) --
  guessing which target a polymorphic lookup resolves to isn't this
  module's job (the "No Invented Field Names" discipline, hard rule 5).
  Such fields are left out of `sent` entirely for the sfdmu engine v1;
  the caller can still load them via the Python engine as a second pass.

NOT YET CONFIRMED: whether SFDMU offers any lock-contention/batch-ordering
behavior comparable to this framework's own Hard Rule 6 ([Sort] column).
Nothing found in the installed plugin's source suggests one -- a disclosed
gap, not assumed either way.
"""
import glob
import json
import os
import re
import subprocess

import pandas as pd

import sql_dialect
from bulkops import (
    _derive_sent_columns,
    _preflight_check,
    _check_email_deliverability,
    _format_datetime_columns_for_csv,
    _writeback_inplace,
    _writeback_result_table,
)

_SFDMU_OPERATIONS = {"upsert": "Upsert", "update": "Update"}

# Windows requires shell=True for sf.cmd resolution (same reasoning as
# sf_client.py's _run_sf()), which means cmd.exe's own metacharacter
# interpretation (&|^%<>) applies even inside a quoted argument. Org
# aliases and the paths this module builds itself never legitimately need
# those characters, so every arg is checked against this allowlist before
# ever reaching subprocess -- broader than _run_sf()'s alnum-only pattern
# (a real filesystem path needs `/`, `\`, `:`, spaces), but still excludes
# every shell metacharacter.
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
    for arg in args:
        if not _SAFE_SFDMU_ARG_RE.fullmatch(arg):
            raise ValueError(
                f"Refusing to pass {arg!r} to `sf sfdmu run` -- contains characters "
                "outside the safe path/alias set, which risks shell metacharacter "
                "interpretation on Windows (shell=True is required there for sf.cmd "
                "resolution). Check SF_ORG_ALIAS / stage_dir."
            )
    proc = subprocess.run(
        ["sf", *args], capture_output=True, text=True, check=False,
        shell=(os.name == "nt"),
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"`sf sfdmu run` produced non-JSON output (exit code {proc.returncode}). "
            f"stdout: {proc.stdout!r}\nstderr: {proc.stderr!r}"
        ) from e


def _lookup_parent_objects(sf, object_name, sent_columns):
    """{column_name: parent_object_name} for every sent column that's a
    single-target reference field on object_name, per live describe() --
    read-only against Salesforce, no data write. A polymorphic field
    (2+ referenceTo targets) is deliberately skipped, not guessed at."""
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}
    parents = {}
    for col in sent_columns:
        field = fields_by_name.get(col)
        if not field or field.get("type") != "reference":
            continue
        ref_to = field.get("referenceTo") or []
        if len(ref_to) == 1:
            parents[col] = ref_to[0]
    return parents


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


def run_sfdmu_upsert(sf, engine, object_name, operation, source_table, external_id,
                     org_alias, key_column="LoadId", id_column="Id",
                     error_column="Error", ref_prefix="REF_", schema="dbo",
                     stage_dir="_stage", email_deliverability=None,
                     confirm_external_email_risk=False):
    """SFDMU-engine equivalent of bulk_op() -- upsert/update only (see this
    module's docstring for why), external_id required. Returns a summary
    dict shaped like bulk_op()'s own (submitted/succeeded/failed/
    written_to/email_deliverability), so CLI output stays consistent
    regardless of which engine actually ran."""
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

    deliverability_note = _check_email_deliverability(
        operation, email_deliverability, confirm_external_email_risk
    )

    d = sql_dialect.for_engine(engine)
    has_sort_column = d.column_exists(engine, schema, source_table, "Sort")
    order_by = f" ORDER BY {d.quote_ident('Sort')}" if has_sort_column else ""
    df = pd.read_sql(f"SELECT * FROM {d.qualify(schema, source_table)}{order_by}", engine)

    sent = _derive_sent_columns(df, operation, id_column=id_column, key_column=key_column,
                                error_column=error_column, ref_prefix=ref_prefix)

    preflight = _preflight_check(sf, object_name, operation, sent, id_column=id_column)
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

    # Polymorphic lookups aren't resolvable here (see docstring) -- drop
    # them from what's sent via sfdmu rather than letting SFDMU silently
    # mis-handle them; report which ones so the caller knows to load them
    # via the Python engine as a second pass instead.
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}
    polymorphic_skipped = [
        c for c in sent
        if fields_by_name.get(c, {}).get("type") == "reference"
        and len(fields_by_name[c].get("referenceTo") or []) > 1
    ]
    sent = [c for c in sent if c not in polymorphic_skipped]
    parent_objects = _lookup_parent_objects(sf, object_name, sent)

    run_dir = os.path.join(stage_dir, "sfdmu", object_name)
    os.makedirs(run_dir, exist_ok=True)
    for old in glob.glob(os.path.join(run_dir, "*")):
        if os.path.isdir(old):
            for f in glob.glob(os.path.join(old, "*")):
                os.remove(f)
        else:
            os.remove(old)

    # Same datetime64-to-XSD-string fix bulk_op() already needed for the
    # Python engine's own CSV export (see _format_datetime_columns_for_csv's
    # docstring) -- confirmed live in this integration's own first real
    # test run: Contact.EmailBouncedDate failed on every one of 8 rows with
    # "Cannot deserialize instance of datetime from VALUE_STRING value
    # 2027-02-11 06:01:40" (pandas' default space-separated str(), not the
    # 'T'-separated form the API requires) before this fix was applied here.
    payload = _format_datetime_columns_for_csv(df[sent].copy())
    payload.to_csv(os.path.join(run_dir, f"{object_name}.csv"), index=False)

    # Each declared Readonly parent needs its own source CSV too -- without
    # one, SFDMU has no source-side data to correlate the "externalId: Id"
    # match against, and the lookup resolves to blank for every row rather
    # than erroring (confirmed live: this is a distinct failure mode from
    # the "Only Id in query" exclusion the module docstring describes --
    # both were found via this integration's own real test runs, not
    # assumed from docs). The distinct, already-resolved Id values actually
    # present in this child's own data are sufficient content -- SFDMU only
    # needs to see each value once to treat it as a known, valid parent Id.
    for lookup_col, parent in parent_objects.items():
        parent_ids = payload[lookup_col].dropna().unique()
        # A blank Name column avoids a spurious "MISSING COLUMN IN THE CSV
        # FILE" report entry (the declared query is "SELECT Id, Name FROM
        # <Parent>" -- see _build_export_json) -- confirmed live this
        # session; matching still happens on Id, Name's value is never
        # actually used for it.
        pd.DataFrame({"Id": parent_ids, "Name": ""}).to_csv(
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
    # was "Upsert" -- not "<Object>_upsert_target.csv". Hardcoded to
    # "update" rather than the actual operation string for that reason.
    target_csv = os.path.join(run_dir, "target", f"{object_name}_update_target.csv")
    if not os.path.exists(target_csv):
        raise RuntimeError(
            f"Expected result file not found: {target_csv} -- sfdmu run may not "
            f"have processed {object_name} at all this run."
        )
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

    df["_result_id"] = df[external_id].astype(str).map(id_by_ext)
    df["_result_error"] = df[external_id].astype(str).map(err_by_ext)

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

    if key_column in df.columns:
        _writeback_inplace(engine, schema, source_table, df, key_column, id_column, error_column)
        written_to = f"{schema}.{source_table}"
    else:
        written_to = _writeback_result_table(engine, schema, source_table, df, sent,
                                             id_column, error_column)

    return {
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
    }
