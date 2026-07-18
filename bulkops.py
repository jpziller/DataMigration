"""Bulk load operations: SQL load table -> Salesforce (SQL Server, SQLite,
or PostgreSQL, per SQL_BACKEND).

Reads a SQL "load table", pushes insert / update / upsert / delete to
Salesforce via Bulk API 2.0, then writes the resulting Salesforce Id and Error
back into that table -- the full round trip a migration load needs. Every
backend-specific SQL construct (existence checks, identifier quoting, the
BulkOpsLog DDL, retry-table creation) goes through sql_dialect.py.

RESULT MAPPING (the part everyone gets wrong):
  Bulk API 2.0 returns separate "successful" and "failed" record sets, each
  echoing the columns you submitted plus sf__Id / sf__Error. There is no
  guaranteed global row order across those two files, so we do NOT map by
  position. Instead we fingerprint each submitted row by the tuple of its sent
  business columns and join the results back on that fingerprint.

  -> update / upsert / delete already send Id (or an external id), so the
     fingerprint is unique and mapping is exact.
  -> insert has no Id yet. Include a UNIQUE migration-key column among the sent
     columns (mapped to a real SF text/external-id field, e.g. Legacy_Id__c) so
     the fingerprint is guaranteed unique. If two submitted rows are identical
     across every sent column, they are genuinely ambiguous and the second is
     reported in `ambiguous`.

Writeback target:
  If `key_column` exists in the load table, Id/Error are UPDATEd in place keyed
  on it. Otherwise a `<table>_Result` table is written instead (no in-place
  update possible without a stable local key).

PRE-FLIGHT CHECK (roadmap #1's "rebuild instead of port" -- a legacy
column/permission compare tool, rebuilt here as a live describe() check
rather than ported verbatim):
  Before ever calling the Bulk API, every sent column is checked against the
  target object's live describe(): does the field exist at all, and can this
  operation actually write it (createable for insert, updateable for
  update/upsert)? Either failure aborts before spending a real API call --
  Salesforce would reject the whole job or every row for the same reason,
  just after burning a batch and taking longer to find out. This is a schema/
  permission check only, not a data-content one (see
  load_table_prep.check_load_table_duplicate_keys / cli.py's
  check-load-table-duplicate-keys for that). A required-but-not-sent field
  on insert is reported as a warning, not a hard stop -- automation could
  still default it, so it isn't guaranteed to fail the way a missing/
  non-writable field is.

RETRY HELPER (build_retry_table):
  Copies only the failed rows (Error column populated) from a load table or
  its `_Result` table into a fresh `<table>_Retry` table, so a partial
  failure can be resubmitted via a normal `bulk_op()` call against just the
  rows that need it, instead of re-running (and re-charging batches for)
  the whole original load.

DELETE BY EXTERNAL ID:
  Bulk API 2.0's delete operation only ever accepts the real Salesforce Id
  column -- confirmed against Salesforce's own Bulk API 2.0 docs ("bulk
  deletion requests can include only the Id field"), unlike update/upsert,
  which do accept an external id via `externalIdFieldName`. So `delete`
  with `external_id` set doesn't send the external id to the API directly
  -- it resolves those values to real Ids via a SOQL query first
  (`_resolve_external_ids_to_sf_id`), then runs a normal Id-based delete
  against the resolved rows. A value with no matching org record is never
  submitted to the API at all (there's no Id to delete); it's reported
  back as a local "no matching record found" error on that row, the same
  writeback shape as any other failure, not silently dropped.

EMAIL DELIVERABILITY ATTESTATION (insert/upsert only):
  insert/upsert can create brand-new records that trigger outbound email to
  real external contacts (welcome emails, notifications, workflow-driven
  sends) -- see docs/MIGRATION_PLAYBOOK.md's "Email deliverability" note.
  Salesforce has no supported API to *read* the org's Email Deliverability
  setting (confirmed by retrieving EmailAdministrationSettings live against
  a real org and cross-checking Salesforce's own field reference -- neither
  has any such field; the only tool found that can even *set* it
  programmatically drives a headless browser against the Setup UI, which
  is exactly the kind of fragile screen-scraping this framework avoids).
  So this can't be a real automated check -- it's a required, explicit
  human attestation instead: `email_deliverability` must be passed for
  insert/upsert (`"no-access"`, `"system-email-only"`, or `"all-email"`,
  matching Setup's own three states), based on someone actually having
  looked at Setup > Email Administration > Deliverability first. Missing
  it raises and aborts before touching the API. `"all-email"` additionally
  requires `confirm_external_email_risk=True`, or it raises too --
  deliverability set to allow all email is the one state that can
  genuinely send real mail to real people, so it needs a deliberate
  override, not a default. The confirmed value is echoed back in the
  result dict either way, so it's visible in the load's own report.

ACTIVITY LOGGING (opt-in, per schema -- roadmap #14):
  Off by default, and never turned on implicitly. An architect enables it
  per schema with `enable_bulkops_logging()` (CLI: `enable-bulkops-logging
  --schema <schema>`), which creates `<schema>.BulkOpsLog`. From then on,
  every `bulk_op()` call against that schema checks whether the table
  exists and, if so, writes one row per call (action, object, source
  table, record counts, job count, Email Deliverability attestation,
  start/end/duration, OS user) -- the same "presence of a table gates
  behavior" pattern this module already uses for the [Sort] column and
  key_column writeback. Never logs `query_tool.py` reads, only bulkops
  writes. A logging failure never fails the underlying load -- the real
  Salesforce operation and its writeback have already completed by the
  time logging runs; a failure is reported back as `logging_error`
  instead. `disable_bulkops_logging()` drops the table (and its history)
  for a schema.
"""
import getpass
import io
import json
import os
import re
import time
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

import batch_advisor
import migration_run_book
import sql_dialect


# (name, mssql_type, sqlite_type, nullable) for BulkOpsLog's original columns;
# (name, mssql_type, sqlite_type) for the 3 added later (ROADMAP #15) --
# always nullable, added idempotently to an existing table via ALTER TABLE.
_BULKOPS_LOG_BASE_COLUMNS = [
    ("Operation", "NVARCHAR(20)", "TEXT", "VARCHAR(20)", False),
    ("ObjectName", "NVARCHAR(255)", "TEXT", "VARCHAR(255)", False),
    ("SourceTable", "NVARCHAR(255)", "TEXT", "VARCHAR(255)", False),
    ("TargetSchema", "NVARCHAR(128)", "TEXT", "VARCHAR(128)", False),
    ("RecordsSubmitted", "INT", "INTEGER", "INTEGER", False),
    ("RecordsSucceeded", "INT", "INTEGER", "INTEGER", False),
    ("RecordsFailed", "INT", "INTEGER", "INTEGER", False),
    ("RecordsAmbiguous", "INT", "INTEGER", "INTEGER", False),
    ("ExternalIdNotFound", "INT", "INTEGER", "INTEGER", False),
    ("JobCount", "INT", "INTEGER", "INTEGER", False),
    ("EmailDeliverability", "NVARCHAR(255)", "TEXT", "VARCHAR(255)", True),
    ("WrittenTo", "NVARCHAR(255)", "TEXT", "VARCHAR(255)", False),
    ("StartedAt", "DATETIME2", "TEXT", "TIMESTAMP", False),
    ("CompletedAt", "DATETIME2", "TEXT", "TIMESTAMP", False),
    ("DurationSeconds", "FLOAT", "REAL", "DOUBLE PRECISION", False),
    ("RunBy", "NVARCHAR(128)", "TEXT", "VARCHAR(128)", True),
]
_BULKOPS_LOG_UPGRADE_COLUMNS = [
    ("BatchSize", "INT", "INTEGER", "INTEGER"),
    ("BatchSizeSource", "NVARCHAR(20)", "TEXT", "VARCHAR(20)"),
    ("LockErrorCount", "INT", "INTEGER", "INTEGER"),
    ("FailureErrorCounts", "NVARCHAR(MAX)", "TEXT", "TEXT"),
]


def _read_result_csv(csv_text):
    if not csv_text or not csv_text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(csv_text), dtype=str,
                       keep_default_na=False, na_values=[""])


# Backoff schedule for _fetch_job_results() -- 7 attempts, ~61s worst case,
# only ever paid on the rare job that actually hits the race described
# there. Extended from the original (0, 1, 2, 4, 8) = ~15s budget live
# during the NPSP-to-NPC migration proof-of-concept (roadmap #75 follow-up):
# that budget, tuned against a mocked/simulated delay in tests, wasn't
# generous enough for this target org's real propagation tail -- hit on
# 3 of 9 loads (AccountContactRelation, Campaign, GiftDesignation), each
# confirmed genuinely successful via a direct, much-later successfulResults
# call, well past the old 15s window. Not a tunable CLI flag: this is an
# internal robustness fix, not a feature, same "hardcode a sane default"
# altitude as _resolve_external_ids_to_sf_id()'s own chunk_size=200 a few
# lines below.
_RESULTS_RETRY_BACKOFF_SECONDS = (0, 1, 2, 4, 8, 16, 30)


def _fetch_job_results(handler, job_id, expected_total, sleep_fn=None):
    """(successes_df, failures_df) for one completed Bulk API 2.0 job --
    retries get_successful_records()/get_failed_records() with backoff
    instead of a single unretried read.

    sleep_fn defaults to None, resolved to time.sleep inside the function
    body rather than bound as a literal default value at def-time --
    found in review: `sleep_fn=time.sleep` in the signature captures the
    function object once, at import time, so a test's
    `monkeypatch.setattr("bulkops.time.sleep", ...)` never reaches this
    already-bound reference. Confirmed live: the two retry tests in
    tests/test_bulkops_sqlite_integration.py silently slept for real
    (3s/61s, matching the real backoff schedule exactly) instead of
    running instantly as their own comments claimed -- the same class of
    hidden-real-sleep problem this file's own #74 fix was built to catch,
    reintroduced by the fix's own test-injection seam.

    Found live (roadmap #74, an NPSP org-seeding session): simple_salesforce's
    own wait_for_job() polls the JOB STATUS endpoint until state ==
    JobComplete and returns immediately -- confirmed by reading
    simple_salesforce/bulk2.py directly. get_successful_records()/
    get_failed_records() are each a single, un-retried GET with no
    readiness check of their own. Salesforce's job-complete signal
    (state, numberRecordsProcessed/Failed) can become accurate before the
    underlying result FILES are actually ready to serve -- reproduced live
    5 times in one session, always on objects with heavier synchronous
    trigger/rollup cascades (General Accounting Unit, Recurring Donation,
    Opportunity, Payment, Allocation all hit it; Contact and CampaignMember,
    lighter automation, never did) -- every time, a job that had already
    genuinely succeeded (confirmed via a direct, slightly-later call to the
    same results endpoint) came back from get_successful_records()/
    get_failed_records() completely empty on the first read, indistinguishable
    from "zero rows were ever submitted" without this check.

    expected_total: numberRecordsProcessed alone from the job's own
    already-reliable status metadata -- real Bulk API 2.0 semantics:
    "processed" already INCLUDES failures (numberRecordsFailed is the
    failed subset within it, not an addition to it -- adding both together
    here once double-counted and made expected_total unreachable on any
    job with failures, silently burning the full retry budget in real
    sleeps on every such call; caught by the test suite's own runtime
    ballooning from ~10s to ~265s, not by reasoning alone). 0 always
    short-circuits immediately (nothing was ever submitted to this job,
    not a readiness question). Gives up after the backoff schedule and
    returns its last, possibly-still-incomplete read rather than hanging
    or raising -- a genuinely unrecoverable read should surface as an
    accurate but disappointing summary, not an exception that hides the
    real work the job already did.
    """
    sleep_fn = sleep_fn or time.sleep
    succ = fail = pd.DataFrame()
    for delay in _RESULTS_RETRY_BACKOFF_SECONDS:
        if delay:
            sleep_fn(delay)
        succ = _read_result_csv(handler.get_successful_records(job_id))
        fail = _read_result_csv(handler.get_failed_records(job_id))
        if expected_total == 0 or len(succ) + len(fail) >= expected_total:
            return succ, fail
    return succ, fail


_SF_ID_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9]{15}\b|\b[a-zA-Z0-9]{18}\b")


def _normalize_error_signature(msg):
    """Collapse a Salesforce error message down to a stable signature for
    orchestrator.py's "known vs. novel error" check -- a DUPLICATE_VALUE or
    similar error embeds the specific colliding record's real Id directly
    in the message text, so the exact same logical error class produces a
    different raw string on almost every occurrence, always reading as
    "novel" even when it's really the same recurring problem (found in
    review). Replaces any 15- or 18-char alphanumeric token that also
    contains at least one digit -- real Salesforce Ids always do, and the
    digit requirement is what keeps a same-length, all-letters field/object
    name (e.g. a 15-character label with no Id in it) from being collapsed
    by mistake. Heuristic, not a guarantee: a token that happens to satisfy
    both conditions without actually being a Salesforce Id would still be
    replaced -- accepted, same "documented residual edge" spirit as
    migration_run_book.py's own token-matching caveat."""
    def repl(match):
        token = match.group(0)
        return "<ID>" if any(c.isdigit() for c in token) else token
    return _SF_ID_TOKEN_RE.sub(repl, str(msg))


def _fingerprint(df, cols):
    # fillna() before astype(str) -- a blank cell in the result CSV (e.g. an
    # empty numeric field like BillingLatitude on a failed row) surfaces as a
    # real NaN float even though _read_result_csv reads everything as dtype=
    # str, and "\x1f".join() raises TypeError on a bare float mixed in with
    # strings. Converting NaN to "" first guarantees every value is a string
    # before the join, regardless of column dtype.
    return df[cols].fillna("").astype(str).agg("\x1f".join, axis=1)


def _resolve_external_ids_to_sf_id(sf, object_name, external_id_field, values, chunk_size=200):
    """Resolve external ID field values to real Salesforce Ids via SOQL --
    see this module's "DELETE BY EXTERNAL ID" docstring section for why
    this is necessary before a delete. Returns {value_as_str: sf_id}; a
    value with no matching org record is simply absent from the result."""
    resolved = {}
    unique_values = sorted({str(v) for v in values if v not in (None, "") and pd.notna(v)})
    for i in range(0, len(unique_values), chunk_size):
        chunk = unique_values[i:i + chunk_size]
        quoted = ", ".join("'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'" for v in chunk)
        soql = f"SELECT Id, {external_id_field} FROM {object_name} WHERE {external_id_field} IN ({quoted})"
        for rec in sf.query(soql).get("records", []):
            resolved[str(rec[external_id_field])] = rec["Id"]
    return resolved


def _preflight_check(sf, object_name, operation, sent_columns, id_column="Id", desc=None):
    """desc: an already-fetched describe() payload, if the caller has one
    in hand -- skips this function's own describe() call (a real network
    round-trip) when given. bulk_op() itself never passes this (unchanged
    behavior); sfdmu_bridge.py does, since it needs describe() for its own
    parent-lookup/polymorphic-field classification too and previously
    fetched it three separate times per call (found in review)."""
    if desc is None:
        desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}

    checked_columns = [c for c in sent_columns if c != id_column]
    not_real_field = [c for c in checked_columns if c not in fields_by_name]
    writable_columns = [c for c in checked_columns if c in fields_by_name]

    if operation == "insert":
        not_writable = [c for c in writable_columns if not fields_by_name[c].get("createable")]
    elif operation in ("update", "upsert"):
        not_writable = [c for c in writable_columns if not fields_by_name[c].get("updateable")]
    else:  # delete only ever sends id_column, already excluded above
        not_writable = []

    required_not_sent = []
    if operation == "insert":
        sent_set = set(sent_columns)
        for f in desc["fields"]:
            if (f.get("createable") and not f.get("nillable", True)
                    and not f.get("defaultedOnCreate") and f["name"] not in sent_set):
                required_not_sent.append(f["name"])

    return {
        "not_a_real_field": not_real_field,
        "not_writable": not_writable,
        "required_not_sent": required_not_sent,
    }


def _derive_sent_columns(df, operation, send_columns=None, id_column="Id",
                         key_column="LoadId", error_column="Error", ref_prefix="REF_"):
    """Which load-table columns actually get sent to Salesforce for a given
    operation -- shared by bulk_op() (Bulk API 2.0 engine) and
    sfdmu_bridge.py (SFDMU engine), so the REF_/Sort/key_column/id_column
    exclusion rules (hard rules 6/13) live in exactly one place. See
    bulk_op()'s own docstring for the full rationale; an explicit
    send_columns is never second-guessed by any of this."""
    _auto_excluded_exact = {error_column}
    if operation == "delete":
        return [id_column]
    if operation == "insert":
        return send_columns or [
            c for c in df.columns
            if c not in (_auto_excluded_exact | {id_column, key_column})
            and c.upper() != "SORT"
            and not c.upper().startswith(ref_prefix.upper())
        ]
    # update / upsert -- id_column IS sent (Salesforce needs it to identify
    # the record); key_column/Sort are not.
    return send_columns or [
        c for c in df.columns
        if c not in (_auto_excluded_exact | {key_column})
        and c.upper() != "SORT"
        and not c.upper().startswith(ref_prefix.upper())
    ]


_DELIVERABILITY_LEVELS = ("no-access", "system-email-only", "all-email")


def _check_email_deliverability(operation, email_deliverability, confirm_external_email_risk):
    """See this module's "EMAIL DELIVERABILITY ATTESTATION" docstring
    section -- there is no supported API to read this setting, so this is
    a required human attestation, not an automated check. Returns a note
    string for the result dict, or None if not applicable to this op."""
    if operation not in ("insert", "upsert"):
        return None

    if email_deliverability is None:
        raise ValueError(
            "insert/upsert can create new records that trigger outbound email to real "
            "external contacts. Check Setup > Email Administration > Deliverability first, "
            "then pass --email-deliverability no-access|system-email-only|all-email. "
            "(There is no API to read this setting automatically -- see this module's "
            "docstring for why.)"
        )
    if email_deliverability not in _DELIVERABILITY_LEVELS:
        raise ValueError(f"Invalid email_deliverability value: {email_deliverability!r} "
                         f"(expected one of {_DELIVERABILITY_LEVELS})")
    if email_deliverability == "all-email" and not confirm_external_email_risk:
        raise ValueError(
            "Email Deliverability is set to 'All Email' -- this load could send real "
            "outbound email to external contacts. If that's genuinely intended, re-run "
            "with --confirm-external-email-risk. Otherwise, set Deliverability to "
            "'System Email Only' or 'No Access' in Setup first."
        )

    if email_deliverability == "all-email":
        return "All Email -- confirmed, external email risk explicitly accepted"
    return f"{email_deliverability} -- internal-only confirmed, continuing"


def enable_bulkops_logging(engine, schema="dbo"):
    """Create <schema>.BulkOpsLog if it doesn't already exist -- idempotent,
    same style as risk_analyzer.py's _ensure_table. Off by default; this is
    the one-time, explicit opt-in this module's ACTIVITY LOGGING docstring
    section describes. Once this table exists, bulk_op() logs automatically
    for every call against this schema -- no per-call flag needed.

    Also idempotently adds the batch-size columns (ROADMAP #15) if this is
    an existing table from before they were introduced -- re-running enable
    on an already-enabled schema upgrades it in place rather than requiring
    disable+re-enable (which would discard log history)."""
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, "BulkOpsLog")

    if not d.table_exists(engine, schema, "BulkOpsLog"):
        # Column names here are deliberately bare (not d.quote_ident()) --
        # found via live Postgres testing: quoting at CREATE TABLE
        # preserves exact case in Postgres's catalog, but every read/
        # write of this table elsewhere (bulk_op()'s own INSERT above,
        # plus batch_advisor.py/orchestrator.py/readiness.py/
        # reconciliation.py, none of which quote their references) uses
        # bare column references, which Postgres folds to lowercase --
        # a real mismatch (psycopg2.errors.UndefinedColumn) if creation
        # is quoted but every reference isn't. SQL Server/SQLite never
        # surfaced this because both match case-insensitively regardless.
        # Bare here matches the dominant convention everywhere else
        # instead of requiring every scattered reference to be quoted.
        col_defs = [d.autoincrement_pk_column_ddl("LogId")]
        for name, mssql_t, sqlite_t, postgres_t, nullable in _BULKOPS_LOG_BASE_COLUMNS:
            null_sql = "NULL" if nullable else "NOT NULL"
            col_defs.append(f"{name} {d.pick_type(mssql_t, sqlite_t, postgres_t)} {null_sql}")
        for name, mssql_t, sqlite_t, postgres_t in _BULKOPS_LOG_UPGRADE_COLUMNS:
            col_defs.append(f"{name} {d.pick_type(mssql_t, sqlite_t, postgres_t)} NULL")
        with engine.begin() as cx:
            cx.execute(text(f"CREATE TABLE {qualified} (" + ", ".join(col_defs) + ");"))
        return

    missing = [
        (name, mssql_t, sqlite_t, postgres_t)
        for name, mssql_t, sqlite_t, postgres_t in _BULKOPS_LOG_UPGRADE_COLUMNS
        if not d.column_exists(engine, schema, "BulkOpsLog", name)
    ]
    if missing:
        with engine.begin() as cx:
            for name, mssql_t, sqlite_t, postgres_t in missing:
                cx.execute(text(
                    f"ALTER TABLE {qualified} ADD {name} "
                    f"{d.pick_type(mssql_t, sqlite_t, postgres_t)} NULL;"
                ))


def disable_bulkops_logging(engine, schema="dbo"):
    """Drop <schema>.BulkOpsLog -- permanently discards that schema's log
    history. Idempotent (no-op if logging was never enabled there)."""
    d = sql_dialect.for_engine(engine)
    if d.table_exists(engine, schema, "BulkOpsLog"):
        with engine.begin() as cx:
            cx.execute(text(f"DROP TABLE {d.qualify(schema, 'BulkOpsLog')};"))


def _bulkops_log_table_exists(engine, schema):
    return sql_dialect.for_engine(engine).table_exists(engine, schema, "BulkOpsLog")


def _write_bulkops_log_row(engine, schema, row):
    qualified = sql_dialect.for_engine(engine).qualify(schema, "BulkOpsLog")
    with engine.begin() as cx:
        cx.execute(text(
            f"INSERT INTO {qualified} "
            "(Operation, ObjectName, SourceTable, TargetSchema, RecordsSubmitted, "
            "RecordsSucceeded, RecordsFailed, RecordsAmbiguous, ExternalIdNotFound, "
            "JobCount, EmailDeliverability, WrittenTo, StartedAt, CompletedAt, "
            "DurationSeconds, RunBy, BatchSize, BatchSizeSource, LockErrorCount, "
            "FailureErrorCounts) VALUES "
            "(:operation, :object_name, :source_table, :target_schema, :submitted, "
            ":succeeded, :failed, :ambiguous, :external_id_not_found, :job_count, "
            ":email_deliverability, :written_to, :started_at, :completed_at, "
            ":duration_seconds, :run_by, :batch_size, :batch_size_source, :lock_error_count, "
            ":failure_error_counts)"
        ), row)


def _format_datetime_columns_for_csv(payload):
    """Reformat any real datetime64-dtype column to the XSD 'T'-separated
    string form Salesforce's Bulk API requires, right before writing the
    outbound CSV.

    A load table column that's a genuine datetime64 dtype (read back from
    a real SQL datetime/datetime2 column, not a pre-formatted string)
    otherwise serializes via pandas' own default str(datetime) --
    space-separated, no 'T' -- which is a real XSD dateTime parse failure
    against the Bulk API ("is not a valid value for the type
    xsd:dateTime"), not merely non-canonical. Confirmed live via a real
    dogfood run: Contact.EmailBouncedDate failed on every submitted row
    this way. sql_dialect.py's own normalize_datetime_columns() only fixes
    this on the WRITE side (into a mirror-DB table); this is the
    outbound-to-Salesforce side, a pre-existing gap this framework hadn't
    hit until a real datetime64 column reached bulk_op() for the first
    time -- not specific to any one mock-data path, since any load table
    built from a genuine SQL datetime column would hit it the same way."""
    payload = payload.copy()
    for col in payload.columns:
        if pd.api.types.is_datetime64_any_dtype(payload[col]):
            payload[col] = payload[col].dt.strftime("%Y-%m-%dT%H:%M:%S").where(payload[col].notna(), None)
    return payload


def bulk_op(sf, engine, object_name, operation, source_table,
            send_columns=None, external_id=None, fingerprint_columns=None,
            key_column="LoadId", id_column="Id", error_column="Error",
            ref_prefix="REF_", schema="dbo", stage_dir="_stage",
            email_deliverability=None, confirm_external_email_risk=False,
            batch_size="auto", run_book_path=None, run_book_tab=None):
    """See this module's docstring for the full design.

    fingerprint_columns (optional, must be a subset of the sent columns):
    restrict RESULT MAPPING's fingerprint to just these columns instead of
    every sent column. Confirmed live -- a real, previously-undiscovered
    bug, not SQL-backend-specific: Bulk API 2.0 can echo a sent value back
    in a different (but semantically identical) string representation than
    what was submitted -- e.g. a sent datetime "2024-04-23T09:56:37+00:00"
    comes back as "2024-04-23T09:56:37.000Z". _fingerprint() joins every
    echoed column into one match key, so a single reformatted column
    silently zeroes out matching for the ENTIRE row (every row reports as
    neither succeeded nor failed, even though the real Salesforce DML
    genuinely happened) -- not an "ambiguous" count, since the fingerprints
    just never intersect at all between the submitted and returned sides.
    Pass the migration key alone here (it's already required to be unique
    by hard rule 4) whenever any OTHER sent column risks this -- datetime
    fields are the confirmed case, but anything Salesforce might normalize
    on echo is a candidate. Defaults to None: today's original behavior,
    fingerprinting by every sent column, unchanged for any existing caller.

    batch_size (ROADMAP #15): "auto" (default) asks batch_advisor.recommend_batch_size() for a
    ladder-rung recommendation and prints its rationale before the load runs;
    an int is honored verbatim (source "static") -- a scripted value always
    wins and stays, same as every other established migration tool's
    hardcode-it-in-the-script norm; None/"none" submits everything as one
    unchunked job (today's original behavior, still available as an
    explicit escape hatch).

    run_book_path/run_book_tab (ROADMAP #16, opt-in): when both are given
    and this call's BulkOpsLog row is written successfully, also calls
    migration_run_book.sync_run_book_from_log() against that tab right
    after -- the "end of the bulk job" moment the sync is meant for. Not
    automatic by default; bulkops shouldn't silently touch a spreadsheet
    file unless asked to.

    ref_prefix (hard rule 13): any auto-derived-list column whose name
    starts with this prefix (case-insensitive) is a human-only, SQL-side
    audit field -- excluded from the actual API payload and from
    _preflight_check, so it's never a false "not a real field" abort. An
    explicit send_columns list is never filtered this way -- naming a
    REF_ column there is a deliberate override.

    AUTO-EXCLUDED LOCAL COLUMNS (auto-derived list only, same override rule
    as ref_prefix above -- an explicit send_columns is never filtered):
    [Sort] (hard rule 6, matched case-insensitively like ref_prefix) and
    key_column are never real Salesforce fields, just this framework's own
    load-table bookkeeping, and are excluded on every operation. id_column
    is the one exception -- update/upsert must still send it (Salesforce
    needs it to identify the record); only insert excludes it, since the
    record doesn't have one yet. A real bug found via a live volume test:
    this exclusion was missing entirely for [Sort] on every operation, and
    missing for key_column specifically on update/upsert -- either gap
    makes _preflight_check fail outright ("not a real field") the moment a
    load table actually has that column, which every Sort-column load
    table always does."""
    operation = operation.lower()
    if operation not in ("insert", "update", "upsert", "delete"):
        raise ValueError(f"Unsupported operation: {operation}")

    started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    deliverability_note = _check_email_deliverability(
        operation, email_deliverability, confirm_external_email_risk
    )

    batch_rationale = []
    if isinstance(batch_size, str) and batch_size.lower() == "auto":
        resolved_batch_size, batch_rationale = batch_advisor.recommend_batch_size(
            engine, object_name, schema=schema
        )
        batch_size_source = "auto"
    elif batch_size is None or (isinstance(batch_size, str) and batch_size.lower() == "none"):
        resolved_batch_size = None
        batch_size_source = "none"
    else:
        resolved_batch_size = int(batch_size)
        batch_size_source = "static"

    # If the load table carries a [Sort] column (see
    # load_table_prep.add_bulk_load_sort_column / cli.py's
    # add-bulk-load-sort-column), submit rows in that order so parent/child
    # rows land in the same Bulk API batch rather than being scattered
    # across batches that process concurrently and
    # lock-contend on a shared parent record.
    d = sql_dialect.for_engine(engine)
    has_sort_column = d.column_exists(engine, schema, source_table, "Sort")
    order_by = f" ORDER BY {d.quote_ident('Sort')}" if has_sort_column else ""

    df = pd.read_sql(f"SELECT * FROM {d.qualify(schema, source_table)}{order_by}", engine)

    # Delete-by-external-id: resolve to real Ids first (see this module's
    # "DELETE BY EXTERNAL ID" docstring section). skip_mask marks rows with
    # no matching org record -- they never reach the API, but still get a
    # clear, locally-generated error written back like any other failure.
    skip_mask = pd.Series(False, index=df.index)
    not_found_count = 0
    if operation == "delete" and external_id:
        if external_id not in df.columns:
            raise ValueError(f"Column {external_id} not in {source_table}")
        resolved = _resolve_external_ids_to_sf_id(sf, object_name, external_id, df[external_id])
        df[id_column] = df[external_id].astype(str).map(resolved)
        skip_mask = df[id_column].isna()
        not_found_count = int(skip_mask.sum())

    # Which columns get sent to Salesforce. A REF_-prefixed column (hard
    # rule 13) is a human-only, SQL-side audit field -- excluded here the
    # same way id_column/error_column/key_column already are, so it never
    # reaches _preflight_check (never a false "not_a_real_field" abort) and
    # never appears in the actual API payload. [Sort] (hard rule 6) is the
    # same kind of local/framework-only auxiliary column and must be
    # excluded the same way on every operation -- confirmed live: a load
    # table with a real [Sort] column previously failed _preflight_check
    # outright ("not a real field: ['Sort']") on its very first bulk_op()
    # call, since nothing excluded it. Matched case-insensitively, same as
    # ref_prefix -- add_bulk_load_sort_column() always creates it as
    # exactly "Sort", but there's no reason a differently-cased variant
    # should silently reintroduce this bug. key_column (e.g. "LoadId") is
    # likewise never a real Salesforce field and must be excluded for
    # update/upsert too, not just insert -- it was already correctly
    # excluded there but missing here, the same class of bug. Only applies
    # to the auto-derived list -- an explicit send_columns is never
    # second-guessed.
    sent = _derive_sent_columns(df, operation, send_columns=send_columns,
                               id_column=id_column, key_column=key_column,
                               error_column=error_column, ref_prefix=ref_prefix)

    missing = [c for c in sent if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not in {source_table}: {missing}")

    if fingerprint_columns is not None:
        not_sent = [c for c in fingerprint_columns if c not in sent]
        if not_sent:
            raise ValueError(
                f"fingerprint_columns must be a subset of the sent columns -- "
                f"not sent: {not_sent}"
            )

    preflight = _preflight_check(sf, object_name, operation, sent, id_column=id_column)
    fatal_details = []
    if preflight["not_a_real_field"]:
        fatal_details.append(f"not a real field on {object_name}: {preflight['not_a_real_field']}")
    if preflight["not_writable"]:
        verb = "createable" if operation == "insert" else "updateable"
        fatal_details.append(f"not {verb} on {object_name}: {preflight['not_writable']}")
    if fatal_details:
        raise ValueError(
            f"Pre-flight check failed for {source_table} -> {object_name} ({operation}): "
            + "; ".join(fatal_details)
        )

    # Rows that failed external-id resolution never reach the API -- they
    # get a locally-generated error instead (see skip_mask above).
    submit_df = df[~skip_mask] if skip_mask.any() else df

    os.makedirs(stage_dir, exist_ok=True)
    csv_path = os.path.join(stage_dir, f"{source_table}_{operation}.csv")

    job_count = 0
    if submit_df.empty:
        successes, failures = pd.DataFrame(), pd.DataFrame()
        echo_cols = []
    else:
        payload = _format_datetime_columns_for_csv(submit_df[sent].copy())
        payload.to_csv(csv_path, index=False)

        handler = getattr(sf.bulk2, object_name)
        if operation == "insert":
            results = handler.insert(csv_file=csv_path, batch_size=resolved_batch_size)
        elif operation == "update":
            results = handler.update(csv_file=csv_path, batch_size=resolved_batch_size)
        elif operation == "upsert":
            if not external_id:
                raise ValueError("upsert requires external_id")
            # simple_salesforce's SFBulk2Handler.upsert() signature is
            # (csv_file=None, records=None, external_id_field='Id', ...) --
            # its SECOND positional parameter is records, not
            # external_id_field. Passing external_id positionally (as this
            # call previously did) silently bound the external-id field
            # name string into records instead, which _convert_dict_to_csv()
            # then tried to iterate as a list of row dicts -- found live
            # against a real org ("'str' object has no attribute 'keys'"),
            # invisible to the test suite because tests/stub_salesforce.py's
            # own StubBulkHandler.upsert() had drifted to match this WRONG
            # calling convention rather than the real library's actual
            # signature. Always pass both by keyword here so a future
            # signature change fails loudly instead of silently rebinding.
            results = handler.upsert(csv_file=csv_path, external_id_field=external_id,
                                      batch_size=resolved_batch_size)
        else:  # delete
            results = handler.delete(csv_file=csv_path, batch_size=resolved_batch_size)
        job_count = len(results)

        # Collect per-job successful + failed records. _fetch_job_results()
        # retries with backoff against a real Bulk API 2.0 race -- see its
        # own docstring for the live incident that found it.
        succ_frames, fail_frames = [], []
        for job in results:
            job_id = job["job_id"]
            # numberRecordsProcessed already INCLUDES failures (real Bulk
            # API 2.0 semantics: processed = successes + failures combined,
            # numberRecordsFailed is the failed subset within it) -- adding
            # them again here double-counted and made expected_total
            # unreachable on every job with any failures at all, silently
            # burning the full retry budget (real sleeps) on every such
            # test. Caught by the full suite ballooning from ~10s to ~265s
            # before this was fixed, not by reasoning alone.
            expected = job.get("numberRecordsProcessed", 0)
            succ, fail = _fetch_job_results(handler, job_id, expected)
            succ_frames.append(succ)
            fail_frames.append(fail)
        successes = pd.concat([f for f in succ_frames if not f.empty],
                              ignore_index=True) if any(not f.empty for f in succ_frames) else pd.DataFrame()
        failures = pd.concat([f for f in fail_frames if not f.empty],
                             ignore_index=True) if any(not f.empty for f in fail_frames) else pd.DataFrame()

        # Build fingerprint -> (Id, Error) using the sent business columns that are
        # echoed back in the result files -- or just fingerprint_columns, if given
        # (see this function's own docstring for why that's sometimes necessary:
        # a single echoed-back column that Salesforce reformats, e.g. a datetime
        # field, otherwise breaks matching for the whole row).
        # A column only belongs in echo_cols if it's present in EVERY
        # non-empty result frame, not just one of them (found in review):
        # _fingerprint() is called with this same column list against
        # successes, failures, AND submit_df, so a column present in only
        # one result frame would raise KeyError the moment the OTHER
        # frame is fingerprinted -- after the real Salesforce write has
        # already happened. Vacuously true for an empty frame (nothing to
        # be missing a column from).
        fingerprint_source = fingerprint_columns if fingerprint_columns is not None else sent
        echo_cols = [c for c in fingerprint_source if (
            (successes.empty or c in successes.columns) and
            (failures.empty or c in failures.columns)
        )]

    id_by_fp, err_by_fp, ambiguous = {}, {}, 0
    if not successes.empty:
        for fp, sid in zip(_fingerprint(successes, echo_cols),
                           successes.get("sf__Id", pd.Series(dtype=str))):
            if fp in id_by_fp:
                ambiguous += 1
            id_by_fp[fp] = sid
    if not failures.empty:
        for fp, serr in zip(_fingerprint(failures, echo_cols),
                            failures.get("sf__Error", pd.Series(dtype=str))):
            err_by_fp[fp] = serr

    df["_result_id"] = pd.Series(dtype=object, index=df.index)
    df["_result_error"] = pd.Series(dtype=object, index=df.index)
    if not submit_df.empty:
        submit_fp = _fingerprint(submit_df, echo_cols)
        df.loc[submit_df.index, "_result_id"] = submit_fp.map(id_by_fp)
        df.loc[submit_df.index, "_result_error"] = submit_fp.map(err_by_fp)
    if skip_mask.any():
        not_found_msg = f"No {object_name} record found with {external_id} matching this row's value"
        df.loc[skip_mask, "_result_error"] = not_found_msg

    n_ok = df["_result_id"].notna().sum()
    n_err = df["_result_error"].notna().sum()
    # Row-lock contention (ROADMAP #15's history feedback loop reads this
    # back on future runs) -- Salesforce's own error string for it.
    lock_error_count = int(
        df["_result_error"].fillna("").str.contains("UNABLE_TO_LOCK_ROW").sum()
    )
    # Distinct failure error messages and their counts -- previously only
    # visible in the writeback table, not the summary dict. Needed by
    # orchestrator.py's assess_tier() for its "seen before vs. novel error"
    # check (a known signature vs. something never observed for this
    # object before). Keys run through _normalize_error_signature() first
    # (record-Id tokens collapsed to <ID>) so the same recurring error
    # class still reads as "known" across runs instead of looking novel
    # every time purely because it names a different row's Id -- two
    # distinct raw messages that normalize to the same signature have
    # their counts combined here, not counted separately.
    failure_error_counts = {}
    for msg, count in df["_result_error"].dropna().value_counts().items():
        key = _normalize_error_signature(msg)
        failure_error_counts[key] = failure_error_counts.get(key, 0) + int(count)

    # Write results back. For delete-by-external-id, the result table should
    # still show the external id value a row was submitted for, even though
    # only the resolved Id was ever sent to the API -- otherwise a "no
    # matching record" row would be unreviewable (blank Id, no external id
    # either).
    report_columns = sent
    if operation == "delete" and external_id and external_id not in sent:
        report_columns = sent + [external_id]

    if key_column in df.columns:
        _writeback_inplace(engine, schema, source_table, df,
                           key_column, id_column, error_column)
        target = f"{schema}.{source_table}"
    else:
        target = _writeback_result_table(engine, schema, source_table, df,
                                          report_columns, id_column, error_column)

    completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    summary = {
        "operation": operation,
        "object": object_name,
        "submitted": len(submit_df),
        "succeeded": int(n_ok),
        "failed": int(n_err),
        "ambiguous": ambiguous,
        "external_id_not_found": not_found_count,
        "written_to": target,
        "preflight_warnings": preflight["required_not_sent"],
        "email_deliverability": deliverability_note,
        "batch_size": resolved_batch_size if resolved_batch_size is not None else "none (unchunked)",
        "batch_size_source": batch_size_source,
        "batch_size_rationale": batch_rationale,
        "lock_errors": lock_error_count,
        "failure_error_counts": failure_error_counts,
    }

    # Activity logging -- opt-in per schema, see this module's ACTIVITY
    # LOGGING docstring section. Only runs if the architect has already
    # created <schema>.BulkOpsLog via enable_bulkops_logging(); otherwise
    # this is a single cheap table-existence check and nothing more happens.
    summary["logged"] = False
    if _bulkops_log_table_exists(engine, schema):
        try:
            _write_bulkops_log_row(engine, schema, {
                "operation": operation,
                "object_name": object_name,
                "source_table": source_table,
                "target_schema": schema,
                "submitted": len(submit_df),
                "succeeded": int(n_ok),
                "failed": int(n_err),
                "ambiguous": ambiguous,
                "external_id_not_found": not_found_count,
                "job_count": job_count,
                "email_deliverability": deliverability_note,
                "written_to": target,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_seconds": (completed_at - started_at).total_seconds(),
                "run_by": getpass.getuser(),
                "batch_size": resolved_batch_size,
                "batch_size_source": batch_size_source,
                "lock_error_count": lock_error_count,
                "failure_error_counts": json.dumps(failure_error_counts),
            })
            summary["logged"] = True
        except Exception as e:
            # The real load and its writeback already succeeded above --
            # a logging failure shouldn't take that result away, just
            # surface itself rather than fail silently.
            summary["logging_error"] = str(e)

    # Migration Run Book sync -- opt-in (ROADMAP #16), only attempted once
    # this call's own BulkOpsLog row actually exists to sync from. Same
    # "the real load already succeeded, don't let this take it away"
    # precedent as logging_error above.
    if run_book_path and run_book_tab and summary["logged"]:
        try:
            summary["run_book_synced"] = migration_run_book.sync_run_book_from_log(
                engine, run_book_path, run_book_tab, schema=schema
            )
        except Exception as e:
            summary["run_book_sync_error"] = str(e)

    return summary


def purge_by_filter(sf, engine, object_name, where, schema="dbo",
                    stage_dir="_stage", batch_size="auto", dry_run=False,
                    run_book_path=None, run_book_tab=None):
    """Bulk test-data cleanup by SOQL filter (ROADMAP #32): resolve every
    Id matching `where` via SOQL, materialize them into
    [schema].[<Object>_Purge], and delegate to the normal bulk_op() delete
    path -- so batch sizing, activity logging, result writeback, and the
    run-book sync all behave exactly like any other delete, no parallel
    code path. Built for the mock-data test cycle (generate -> insert ->
    validate -> purge -> repeat), not as a real-migration load feature.

    `where` is required and never defaulted -- there is deliberately no
    "delete everything" mode. Purging an entire object means writing
    `Id != null` yourself, explicitly and on purpose.

    dry_run=True returns {"matched", "sample_ids"} and touches nothing --
    no SQL table, no API call. Run that first; this is a destructive
    command.

    v1 non-goal: no hard-delete (Bulk API hard delete needs its own org
    permission and skips the Recycle Bin). A standard delete is
    recoverable from the Recycle Bin, which is the right default for a
    cleanup command.
    """
    if not where or not str(where).strip():
        raise ValueError(
            "purge_by_filter requires a non-empty WHERE clause -- there is "
            "deliberately no delete-everything default. To purge an entire "
            "object, say so explicitly with e.g. \"Id != null\"."
        )

    ids = [rec["Id"] for rec in sf.query_all_iter(
        f"SELECT Id FROM {object_name} WHERE {where}"
    )]

    if dry_run:
        return {"operation": "delete (dry run)", "object": object_name,
                "where": where, "matched": len(ids), "sample_ids": ids[:10]}

    if not ids:
        return {"operation": "delete", "object": object_name, "where": where,
                "matched": 0, "submitted": 0,
                "note": "no records matched -- nothing sent to the API"}

    purge_table = f"{object_name}_Purge"
    pd.DataFrame({"Id": ids, "Error": None}).to_sql(
        purge_table, engine, schema=schema, if_exists="replace", index=False
    )

    summary = bulk_op(sf, engine, object_name, "delete", purge_table,
                      schema=schema, stage_dir=stage_dir, batch_size=batch_size,
                      run_book_path=run_book_path, run_book_tab=run_book_tab)
    summary["where"] = where
    summary["matched"] = len(ids)
    return summary


def _writeback_inplace(engine, schema, table, df, key_column,
                       id_column, error_column):
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, table)
    missing_cols = [
        col for col in (id_column, error_column)
        if not d.column_exists(engine, schema, table, col)
    ]
    with engine.begin() as cx:
        for col in missing_cols:
            cx.execute(text(
                f"ALTER TABLE {qualified} ADD {d.quote_ident(col)} {d.raw_text_type()} NULL;"
            ))
        stmt = text(
            f"UPDATE {qualified} "
            f"SET {d.quote_ident(id_column)} = :rid, {d.quote_ident(error_column)} = :rerr "
            f"WHERE {d.quote_ident(key_column)} = :k"
        )
        rows = [
            {"rid": r["_result_id"] if pd.notna(r["_result_id"]) else None,
             "rerr": r["_result_error"] if pd.notna(r["_result_error"]) else None,
             "k": r[key_column]}
            for _, r in df.iterrows()
        ]
        cx.execute(stmt, rows)


def _writeback_result_table(engine, schema, table, df, sent,
                            id_column, error_column):
    out = df[sent].copy()
    out[id_column] = df["_result_id"]
    out[error_column] = df["_result_error"]
    result_table = f"{table}_Result"
    out.to_sql(result_table, engine, schema=schema,
               if_exists="replace", index=False)
    return f"{schema}.{result_table}"


def build_retry_table(engine, table, schema="dbo", error_column="Error", retry_suffix="_Retry"):
    """Copy only the failed rows from `table` (a load table written back in
    place, or a `<table>_Result` table) into a fresh `<table>_Retry` table --
    for resubmission via a normal bulk_op() call against just what failed,
    not the whole original load. Never resubmits anything itself; that's a
    separate, explicit bulkops call against the returned table name."""
    d = sql_dialect.for_engine(engine)
    if not d.column_exists(engine, schema, table, error_column):
        raise ValueError(
            f"{schema}.{table} has no [{error_column}] column -- has bulkops been run against it yet?"
        )

    retry_table = f"{table}{retry_suffix}"
    qualified_retry = d.qualify(schema, retry_table)
    qualified_source = d.qualify(schema, table)

    if d.table_exists(engine, schema, retry_table):
        with engine.begin() as cx:
            cx.execute(text(f"DROP TABLE {qualified_retry};"))

    create_sql = d.create_table_as_select_sql(
        schema, retry_table, "*",
        f"FROM {qualified_source} WHERE {d.quote_ident(error_column)} IS NOT NULL"
    )
    with engine.begin() as cx:
        cx.execute(text(create_sql + ";"))
        count = cx.execute(text(f"SELECT COUNT(*) FROM {qualified_retry}")).scalar()
        if count == 0:
            # SELECT INTO / CREATE TABLE AS SELECT creates the table even
            # when the WHERE clause matches nothing -- don't leave a stray
            # empty table behind just because a load had no failures to retry.
            cx.execute(text(f"DROP TABLE {qualified_retry};"))

    return f"{schema}.{retry_table}", count
