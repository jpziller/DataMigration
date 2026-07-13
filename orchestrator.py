"""Deterministic tier assessment for the supervised load orchestrator
(roadmap #53, docs/ORCHESTRATOR_DESIGN.md). Phase 1 only -- see that
doc's section 5 for what's deliberately not built yet (the actual
coarse-approval mechanism, bulkops-under-plan, the PreToolUse hook).

assess_tier() is the one piece of orchestrator logic this design insists
must be deterministic Python, never model judgment (design doc section 1)
-- Claude's job, once Phase 2 exists, is to call this, read the tier it
returns, and act on it, never to eyeball a result and decide "that looks
fine." Keeping it here, pure and independently testable, is what makes
that possible.

Two things this function deliberately does NOT check, and why:
  - A `bulk_op()` pre-flight check failure (missing/non-writable field)
    and a missing Email Deliverability attestation are both hard `raise`s
    inside `bulk_op()` itself, before it ever returns a summary -- there
    is no completed run to assess in that case. The caller (Phase 2's
    orchestration loop) treats an exception from `bulk_op()` as tier 4
    directly; assess_tier() is never invoked for it.
  - "The object about to run doesn't match the plan's declared
    next-in-sequence object" (design doc section 2, tier 4) needs a real
    plan object to compare against, which doesn't exist until Phase 2
    builds `dbo.OrchestratorRunPlan`. Not checkable here yet.
"""
import getpass
import json
import os
from datetime import datetime, timezone

from sqlalchemy import text

import sql_dialect

_THRESHOLDS_PATH = os.path.join(os.path.dirname(__file__), "reference", "orchestrator_thresholds.json")
# Disclosed, accepted limitation (found in review): a known error signature
# that recurs less often than every 20 runs of this object will fall out of
# this window and get reported as "novel" again -- a real gap, but a wider
# window trades off against a real query cost on an object with a long
# BulkOpsLog history, and 20 is judged enough for the trial-and-error
# cadence a migration project actually runs at. Revisit if a real project's
# usage pattern proves this wrong.
_HISTORY_ROWS_CONSIDERED = 20

# Names, not bare numbers -- "Tier 3" means nothing out of context any more
# than "rule 7" did (CLAUDE.md's own Hard Rules were renamed for the same
# reason). Taken directly from docs/ORCHESTRATOR_DESIGN.md section 2's own
# tier headers, not invented separately.
TIER_NAMES = {
    1: "Continue Silently",
    2: "Continue with Warning",
    3: "Pause and Ask",
    4: "Full Stop",
}


def _load_thresholds():
    with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _is_delete_operation(current):
    return "delete" in (current.get("operation") or "").lower()


def _known_error_signatures(history):
    known = set()
    for row in history:
        known.update((row.get("failure_error_counts") or {}).keys())
    return known


def _max_prior_external_id_not_found(history):
    values = [row.get("external_id_not_found", 0) or 0 for row in history]
    return max(values) if values else 0


def _previous_run_had_lock_errors(history):
    if not history:
        return False
    return (history[-1].get("lock_errors") or 0) > 0


_COMPARABLE_SIZE_BAND = (0.5, 2.0)


def _average_seconds_per_record(history, current_submitted):
    """Average of (duration_seconds / submitted) across history rows of a
    *comparable size* to the current run -- None if no history row has
    enough data, or none is close enough in size to compare fairly.

    Deliberately size-banded, not just "every history row with duration
    data": confirmed live (docs/ORCHESTRATOR_DESIGN.md's own field notes)
    that Bulk API 2.0's per-job overhead (job creation, polling until
    completion) is largely fixed regardless of row count, so seconds-per-
    row is NOT batch-size-invariant -- a small clean batch can look far
    "slower per row" than a large one purely from that fixed cost, not
    because anything is wrong. Comparing only against similarly-sized
    runs (within a 2x band either way) keeps the comparison fair; with no
    comparable-sized history, the elapsed-time check simply doesn't fire
    rather than risk a false Tier 4 (Full Stop) against an unlike-sized
    baseline."""
    lo, hi = _COMPARABLE_SIZE_BAND
    rates = [
        row["duration_seconds"] / row["submitted"]
        for row in history
        if row.get("duration_seconds") and row.get("submitted")
        and lo <= (current_submitted / row["submitted"]) <= hi
    ]
    return sum(rates) / len(rates) if rates else None


def assess_tier(current, history, has_automation_risk_data, environment="uat"):
    """Assess the tier (1-4) for one completed bulk_op() run.

    current: a dict with at least submitted/succeeded/failed/ambiguous/
        external_id_not_found/lock_errors/failure_error_counts/operation
        (bulk_op()'s own summary dict already has all of these, after the
        failure_error_counts addition). duration_seconds is optional --
        the elapsed-time-overrun check is skipped gracefully without it.
    history: this object's prior runs, same shape as current, ordered
        OLDEST to NEWEST (history[-1] is the most recent prior run). Pull
        via the same BulkOpsLog query pattern
        batch_advisor._history_adjustment() already uses.
    has_automation_risk_data: whether dbo.ObjectAutomationRisk has rows
        for this object (from analyze-org-risk).
    environment: "uat" or "prod" -- selects the threshold profile from
        reference/orchestrator_thresholds.json.

    Returns {"tier": 1-4, "tier_name": TIER_NAMES[tier], "reasons": [...],
    "coarse_approval_eligible": bool}.
    "reasons" lists every trigger that fired, not just the first/highest
    -- print all of them, not just the tier number (design doc's own
    "seed knowledge, org automation, load history" rationale-first
    convention, e.g. recommend-batch-size's output style).
    coarse_approval_eligible is False whenever history is empty
    (design doc section 8.5's cold-start resolution: no baseline, no
    Stage 2+ eligibility, regardless of how clean this run's own tier
    comes out) -- tier itself still reflects this run's own real result.
    """
    thresholds = _load_thresholds()[environment]
    submitted = current.get("submitted", 0) or 0
    failed = current.get("failed", 0) or 0
    ambiguous = current.get("ambiguous", 0) or 0
    external_id_not_found = current.get("external_id_not_found", 0) or 0
    lock_errors = current.get("lock_errors", 0) or 0
    failure_error_counts = current.get("failure_error_counts") or {}
    failure_pct = (failed / submitted) if submitted else 0.0

    # Tier 4, unconditional and checked first -- never reachable by any
    # other branch, never loosens regardless of trust-ladder graduation
    # (design doc section 4).
    if _is_delete_operation(current):
        return {
            "tier": 4,
            "tier_name": TIER_NAMES[4],
            "reasons": ["Delete/purge operation -- always Tier 4 (Full Stop), unconditionally (never graduates)."],
            "coarse_approval_eligible": bool(history),
        }

    # Each check below is tracked as its own explicit tier-3 or tier-4
    # reason -- never inferred later by parsing reason text, so wording a
    # message differently can never silently change the computed tier.
    tier3_reasons, tier4_reasons = [], []

    if failure_pct > thresholds["tier3_max_failure_pct"]:
        tier4_reasons.append(
            f"Failure rate {failure_pct:.1%} exceeds the {environment} tier-3 ceiling "
            f"({thresholds['tier3_max_failure_pct']:.0%}) -- likely systemic, not an isolated tail."
        )
    elif failure_pct > thresholds["tier2_max_failure_pct"]:
        tier3_reasons.append(
            f"Failure rate {failure_pct:.1%} is above the tier-2 ceiling "
            f"({thresholds['tier2_max_failure_pct']:.0%}) but within the tier-3 ceiling "
            f"({thresholds['tier3_max_failure_pct']:.0%})."
        )

    known_signatures = _known_error_signatures(history)
    novel_errors = set(failure_error_counts) - known_signatures
    if failure_error_counts and novel_errors:
        tier3_reasons.append(f"Novel failure error signature(s) never seen before for this object: {sorted(novel_errors)}.")

    if ambiguous > 0:
        tier3_reasons.append(
            f"{ambiguous} ambiguous row(s) -- the fingerprint-based result mapping (Hard Rule #4) "
            "has broken down for at least some rows; some reported successes may not be trustworthy either."
        )

    prior_max_not_found = _max_prior_external_id_not_found(history)
    if external_id_not_found > prior_max_not_found:
        tier3_reasons.append(
            f"external_id_not_found ({external_id_not_found}) exceeds this object's prior baseline "
            f"({prior_max_not_found}) -- source data or key mapping may have shifted."
        )

    repeat_second_consecutive = lock_errors > 0 and _previous_run_had_lock_errors(history)
    if repeat_second_consecutive:
        tier3_reasons.append(
            "Lock errors on a second consecutive run against this object, even after batch_advisor "
            "already stepped the batch size down once -- the standard self-correction didn't work."
        )

    if not has_automation_risk_data:
        tier3_reasons.append("No dbo.ObjectAutomationRisk data for this object -- run analyze-org-risk first.")

    repeat_threshold = max(
        thresholds["repeated_error_min_rows"],
        thresholds["repeated_error_min_pct"] * submitted,
    )
    max_repeat = max(failure_error_counts.values()) if failure_error_counts else 0
    if max_repeat >= repeat_threshold:
        tier4_reasons.append(
            f"A single error repeated {max_repeat} time(s) (>= {repeat_threshold:.1f}-row threshold) -- "
            "reads as a validation rule/picklist mismatch blocking a whole class of records, not "
            "unrelated one-off bad rows."
        )

    avg_rate = _average_seconds_per_record(history, submitted) if submitted else None
    duration = current.get("duration_seconds")
    if avg_rate is not None and duration is not None and submitted:
        actual_rate = duration / submitted
        if actual_rate > thresholds["elapsed_time_multiplier"] * avg_rate:
            tier4_reasons.append(
                f"Elapsed time ({duration:.0f}s for {submitted} rows) exceeds "
                f"{thresholds['elapsed_time_multiplier']}x the rate of similarly-sized prior runs -- "
                "possibly stuck, rate-limited, or looping."
            )

    # Tier 2, same additive-not-exclusive accumulation as tier 3/4 above --
    # a run can be both "known low-rate failure" and "first-occurrence
    # lock errors" at once, and both reasons should surface, not just
    # whichever condition happened to be written first in an elif chain
    # (found in review: a 1% known-signature failure rate plus a first-
    # occurrence lock error used to silently drop one of the two reasons).
    tier2_reasons = []
    if failure_pct > 0 and failure_pct <= thresholds["tier2_max_failure_pct"] and not novel_errors:
        tier2_reasons.append(
            f"Failure rate {failure_pct:.1%} within the tier-2 ceiling "
            f"({thresholds['tier2_max_failure_pct']:.0%}), all failure signature(s) previously seen."
        )
    if lock_errors > 0 and not repeat_second_consecutive:
        # First occurrence (a second consecutive occurrence is already
        # tier 3 via repeat_second_consecutive above) -- expected
        # trial-and-error, not a stop condition, per design doc section 2's
        # tier 2.
        tier2_reasons.append("Lock errors on this object's first run at this batch size -- expected trial-and-error.")

    if tier4_reasons:
        tier, reasons = 4, tier4_reasons + tier3_reasons
    elif tier3_reasons:
        tier, reasons = 3, tier3_reasons
    elif tier2_reasons:
        tier, reasons = 2, tier2_reasons
    else:
        tier, reasons = 1, ["Clean run: no failures, no ambiguous rows, no external-id misses."]

    return {
        "tier": tier,
        "tier_name": TIER_NAMES[tier],
        "reasons": reasons,
        "coarse_approval_eligible": bool(history),
    }


def _row_to_current(row):
    """A BulkOpsLog row (as a SQLAlchemy mapping/dict) -> the shape
    assess_tier() expects. FailureErrorCounts is stored as a JSON string
    (bulk_op() serializes it before logging) -- a NULL/missing value
    (any row logged before this column existed) becomes {}, same as a
    genuinely clean run with no failures at all; assess_tier() can't tell
    the two apart from this dict alone, which is fine -- a NULL-history
    row simply can't contribute a "known signature" either way.

    Keys are lowercased once up front rather than accessed by exact case
    -- found via live Postgres testing: an unquoted column comes back
    lowercased in a Postgres result set (e.g. "recordssubmitted", not
    "RecordsSubmitted") even though SQL Server/SQLite both preserve the
    originally-declared case, so a plain row.get("RecordsSubmitted")
    silently returned None (not even a crash) for every field on
    Postgres. Lowercasing once here is simpler than routing every one of
    these through sql_dialect.row_get() individually."""
    row = {k.lower(): v for k, v in dict(row).items()}
    raw = row.get("failureerrorcounts")
    failure_error_counts = json.loads(raw) if raw else {}
    return {
        "operation": row.get("operation"),
        "submitted": row.get("recordssubmitted") or 0,
        "succeeded": row.get("recordssucceeded") or 0,
        "failed": row.get("recordsfailed") or 0,
        "ambiguous": row.get("recordsambiguous") or 0,
        "external_id_not_found": row.get("externalidnotfound") or 0,
        "lock_errors": row.get("lockerrorcount") or 0,
        "failure_error_counts": failure_error_counts,
        "duration_seconds": row.get("durationseconds"),
    }


def _read_bulkops_history(engine, object_name, schema="dbo", before_log_id=None):
    """This object's prior BulkOpsLog rows -- strictly *before*
    before_log_id (LogId is autoincrement, so lower means earlier),
    oldest to newest. Same table/columns
    batch_advisor._history_adjustment() already reads, just a longer
    window (assess_tier() needs the full known-error-signature set, not
    just the single most recent row). Returns [] if BulkOpsLog doesn't
    exist yet. Deliberately "before", not just "not equal to" -- a
    retroactive assessment of an older row must never see a run that
    happened after it as if it were history."""
    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "BulkOpsLog"):
        return []

    where = "WHERE ObjectName = :obj"
    params = {"obj": object_name}
    if before_log_id is not None:
        where += " AND LogId < :before"
        params["before"] = before_log_id

    query = d.select_top_n_sql(
        "LogId, Operation, RecordsSubmitted, RecordsSucceeded, RecordsFailed, "
        "RecordsAmbiguous, ExternalIdNotFound, LockErrorCount, FailureErrorCounts, "
        "DurationSeconds",
        f"FROM {d.qualify(schema, 'BulkOpsLog')} {where} ORDER BY LogId DESC",
        _HISTORY_ROWS_CONSIDERED,
    )
    with engine.connect() as cx:
        rows = cx.execute(text(query), params).mappings().all()
    # DESC for the TOP/LIMIT window, then reversed to oldest-first --
    # assess_tier() expects history[-1] to be the most recent prior run.
    return [_row_to_current(dict(r)) for r in reversed(rows)]


def _has_automation_risk_data(engine, object_name, schema="dbo"):
    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "ObjectAutomationRisk"):
        return False
    with engine.connect() as cx:
        count = cx.execute(
            text(f"SELECT COUNT(*) FROM {d.qualify(schema, 'ObjectAutomationRisk')} WHERE ObjectName = :obj"),
            {"obj": object_name},
        ).scalar()
    return bool(count)


def assess_from_log(engine, object_name, log_id=None, schema="dbo", environment="uat"):
    """Resolve a real BulkOpsLog row (the most recent for object_name if
    log_id is omitted), build assess_tier()'s inputs from it and this
    object's own prior history, and return (log_id, assess_tier()'s
    result). Raises ValueError if no matching BulkOpsLog row exists."""
    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "BulkOpsLog"):
        raise ValueError(f"{schema}.BulkOpsLog doesn't exist yet -- enable-bulkops-logging first, then run a load.")

    if log_id is not None:
        query = f"SELECT * FROM {d.qualify(schema, 'BulkOpsLog')} WHERE LogId = :log_id AND ObjectName = :obj"
        params = {"log_id": log_id, "obj": object_name}
    else:
        query = d.select_top_n_sql(
            "*", f"FROM {d.qualify(schema, 'BulkOpsLog')} WHERE ObjectName = :obj ORDER BY LogId DESC", 1
        )
        params = {"obj": object_name}

    with engine.connect() as cx:
        row = cx.execute(text(query), params).mappings().first()
    if row is None:
        raise ValueError(f"No BulkOpsLog row found for {object_name}" + (f" with LogId {log_id}" if log_id else ""))

    resolved_log_id = sql_dialect.row_get(row, "LogId")
    current = _row_to_current(dict(row))
    history = _read_bulkops_history(engine, object_name, schema=schema, before_log_id=resolved_log_id)
    has_risk_data = _has_automation_risk_data(engine, object_name, schema=schema)

    result = assess_tier(current, history, has_risk_data, environment=environment)
    return resolved_log_id, result


_RUN_EVENT_COLUMNS = [
    ("LogId", "INT", "INTEGER", "INTEGER", False),
    ("ObjectName", "NVARCHAR(255)", "TEXT", "VARCHAR(255)", False),
    ("Tier", "INT", "INTEGER", "INTEGER", False),
    ("Reasons", "NVARCHAR(MAX)", "TEXT", "TEXT", False),
    ("Environment", "NVARCHAR(10)", "TEXT", "VARCHAR(10)", False),
    ("AssessedAt", "DATETIME2", "TEXT", "TIMESTAMP", False),
    ("RunBy", "NVARCHAR(128)", "TEXT", "VARCHAR(128)", True),
]
_RUN_EVENT_UPGRADE_COLUMNS = [
    ("TierName", "NVARCHAR(30)", "TEXT", "VARCHAR(30)"),
]


def enable_orchestrator_logging(engine, schema="dbo"):
    """Create <schema>.OrchestratorRunEvent if it doesn't already exist --
    same opt-in-per-schema, presence-of-table-is-the-switch convention as
    enable_bulkops_logging(). Once created, orchestrator-assess logs every
    assessment automatically; never gates anything, purely the shadow-mode
    observation record design doc section 5 calls for -- the raw material
    for eventually checking whether the tier logic agreed with what
    actually happened.

    Also idempotently adds any columns in _RUN_EVENT_UPGRADE_COLUMNS if
    this is an existing table from before they were introduced -- same
    upgrade-in-place convention as enable_bulkops_logging(), history
    preserved rather than requiring disable+re-enable."""
    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, "OrchestratorRunEvent")

    if not d.table_exists(engine, schema, "OrchestratorRunEvent"):
        # Column names here are deliberately bare (not d.quote_ident()) --
        # matches bulkops.py's own BulkOpsLog fix for the identical issue
        # (found via live Postgres testing): quoting at CREATE TABLE
        # preserves exact case in Postgres's catalog, but every read/write
        # of this table elsewhere (log_run_event()'s own INSERT below,
        # plus assess_tier()'s own history reads above) uses bare column
        # references, which Postgres folds to lowercase -- bare here
        # matches that dominant convention instead of requiring every
        # scattered reference to be quoted.
        col_defs = [d.autoincrement_pk_column_ddl("EventId")]
        for name, mssql_t, sqlite_t, postgres_t, nullable in _RUN_EVENT_COLUMNS:
            null_sql = "NULL" if nullable else "NOT NULL"
            col_defs.append(f"{name} {d.pick_type(mssql_t, sqlite_t, postgres_t)} {null_sql}")
        for name, mssql_t, sqlite_t, postgres_t in _RUN_EVENT_UPGRADE_COLUMNS:
            col_defs.append(f"{name} {d.pick_type(mssql_t, sqlite_t, postgres_t)} NULL")
        with engine.begin() as cx:
            cx.execute(text(f"CREATE TABLE {qualified} (" + ", ".join(col_defs) + ");"))
        return

    missing = [
        (name, mssql_t, sqlite_t, postgres_t)
        for name, mssql_t, sqlite_t, postgres_t in _RUN_EVENT_UPGRADE_COLUMNS
        if not d.column_exists(engine, schema, "OrchestratorRunEvent", name)
    ]
    if missing:
        with engine.begin() as cx:
            for name, mssql_t, sqlite_t, postgres_t in missing:
                cx.execute(text(
                    f"ALTER TABLE {qualified} ADD {name} "
                    f"{d.pick_type(mssql_t, sqlite_t, postgres_t)} NULL;"
                ))


def disable_orchestrator_logging(engine, schema="dbo"):
    """Drop <schema>.OrchestratorRunEvent -- permanently discards that
    schema's shadow-mode observation history. Idempotent."""
    d = sql_dialect.for_engine(engine)
    if d.table_exists(engine, schema, "OrchestratorRunEvent"):
        with engine.begin() as cx:
            cx.execute(text(f"DROP TABLE {d.qualify(schema, 'OrchestratorRunEvent')};"))


def _orchestrator_log_table_exists(engine, schema):
    return sql_dialect.for_engine(engine).table_exists(engine, schema, "OrchestratorRunEvent")


def log_run_event(engine, log_id, object_name, result, schema="dbo", environment="uat"):
    """Write one row to <schema>.OrchestratorRunEvent if that table
    exists (opt-in, see enable_orchestrator_logging()) -- a no-op
    otherwise, same non-fatal-if-not-enabled precedent as bulk_op()'s own
    BulkOpsLog write."""
    if not _orchestrator_log_table_exists(engine, schema):
        return False
    qualified = sql_dialect.for_engine(engine).qualify(schema, "OrchestratorRunEvent")
    with engine.begin() as cx:
        cx.execute(
            text(
                f"INSERT INTO {qualified} (LogId, ObjectName, Tier, TierName, Reasons, Environment, AssessedAt, RunBy) "
                "VALUES (:log_id, :object_name, :tier, :tier_name, :reasons, :environment, :assessed_at, :run_by)"
            ),
            {
                "log_id": log_id,
                "object_name": object_name,
                "tier": result["tier"],
                "tier_name": result.get("tier_name", TIER_NAMES.get(result["tier"])),
                "reasons": " | ".join(result["reasons"]),
                "environment": environment,
                "assessed_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "run_by": getpass.getuser(),
            },
        )
    return True
