"""Dynamic bulk-load batch-size recommendations (ROADMAP #15).

Bulk API 2.0 has no server-side adaptivity at all -- it mechanically
splits submitted data into chunks and processes them, never inspecting
an org's automation to size batches (confirmed against the installed
simple-salesforce source, not assumed). So any "start heavily-automated
objects smaller" common sense has to live client-side. This module is
that client-side logic, built from three layers, each adjusting a
recommendation up or down the ladder and recording *why* -- so a data
architect reviewing the recommendation sees the reasoning, not just a
number, the same "rationale over bare answer" principle auto_mapper.py
already established for field-mapping suggestions.

Three layers, applied in order:
  1. Seed knowledge (reference/batch_size_heuristics.json) -- exact
     object-name seeds for OOTB-heavy objects (Opportunity, Case, ...)
     and managed-package prefix seeds (SBQQ__, blng__, ...), git-tracked
     and human-curated like field_synonyms.json. This is cross-project
     knowledge: what every migration already knows to expect from these
     objects before ever touching this specific org.
  2. This org's own automation (dbo.ObjectAutomationRisk, written by
     analyze-org-risk, ROADMAP #5) -- active Apex triggers, record-
     triggered Flows, and validation rule counts each step the
     recommendation down a rung if they cross a threshold.
  3. This project's own load history (dbo.BulkOpsLog, ROADMAP #14) --
     if the object's last run had UNABLE_TO_LOCK_ROW errors, step down;
     if recent runs were clean, step up cautiously. This is the
     trial-and-error feedback loop, automated and remembered instead of
     re-discovered by hand each time.

All recommendations snap to a fixed ladder of rungs (see the JSON's
"ladder") rather than an arbitrary computed number -- a handful of
comparable, memorable sizes instead of one-off values like "743".

This module never writes to the seed file itself -- suggest_heuristic_
updates() only *prints* candidate edits for a human to review and commit
deliberately, the same git-is-truth principle the auto-mapper thesaurus
already follows for its own synonym file.
"""
import json
import os

from sqlalchemy import text

import sql_dialect

_HEURISTICS_PATH = os.path.join(os.path.dirname(__file__), "reference", "batch_size_heuristics.json")


def _load_heuristics():
    with open(_HEURISTICS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _ladder_index(ladder, size):
    """Nearest rung to size, for stepping up/down by whole rungs."""
    return min(range(len(ladder)), key=lambda i: abs(ladder[i] - size))


def _step(ladder, size, rungs):
    idx = _ladder_index(ladder, size)
    idx = max(0, min(len(ladder) - 1, idx + rungs))
    return ladder[idx]


def _seed_lookup(heuristics, object_name):
    seeds = heuristics.get("object_seeds", {})
    if object_name in seeds:
        seed = seeds[object_name]
        return seed["start"], f"Seed knowledge for {object_name}: {seed['why']}."
    for prefix, seed in heuristics.get("prefix_seeds", {}).items():
        if object_name.startswith(prefix):
            return seed["start"], f"Seed knowledge for {prefix}* objects: {seed['why']}."
    default = heuristics["default_batch_size"]
    return default, f"No seed knowledge for {object_name} -- starting from the default ({default})."


def _automation_adjustment(engine, heuristics, object_name, schema):
    adj = heuristics["risk_adjustments"]
    rationale = []
    rungs_down = 0

    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "ObjectAutomationRisk"):
        rationale.append(
            "This object hasn't been scanned by analyze-org-risk yet -- "
            "run it for a better-informed starting point (org automation unknown)."
        )
        return 0, rationale

    with engine.connect() as cx:
        counts = dict(cx.execute(
            text(
                f"SELECT CheckType, COUNT(*) FROM {d.qualify(schema, 'ObjectAutomationRisk')} "
                "WHERE ObjectName = :obj AND IsActive = 1 GROUP BY CheckType"
            ),
            {"obj": object_name},
        ).fetchall())

    if not counts:
        rationale.append(
            f"analyze-org-risk scanned {object_name} and confirmed no active automation -- no adjustment."
        )
        return 0, rationale

    apex_triggers = counts.get("ApexTrigger", 0)
    flows = counts.get("RecordTriggeredFlow", 0)
    validation_rules = counts.get("ValidationRule", 0)

    if apex_triggers > 0:
        rungs_down += adj["any_active_apex_trigger_rungs_down"]
        rationale.append(f"{apex_triggers} active Apex trigger(s) on {object_name}.")
    if flows >= adj["record_triggered_flows_threshold"]:
        rungs_down += adj["record_triggered_flows_rungs_down"]
        rationale.append(f"{flows} active record-triggered Flow(s), at/above the "
                         f"{adj['record_triggered_flows_threshold']}-Flow threshold.")
    if validation_rules >= adj["active_validation_rules_threshold"]:
        rungs_down += adj["active_validation_rules_rungs_down"]
        rationale.append(f"{validation_rules} active validation rule(s), at/above the "
                         f"{adj['active_validation_rules_threshold']}-rule threshold.")

    if not rationale:
        rationale.append(f"analyze-org-risk shows light automation on {object_name} -- no adjustment.")

    return rungs_down, rationale


def _history_adjustment(engine, heuristics, object_name, schema):
    hist = heuristics["history_rules"]
    rationale = []

    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "BulkOpsLog"):
        return 0, []

    # An existing BulkOpsLog from before ROADMAP #15 won't have these
    # columns yet -- confirmed live: querying them unconditionally
    # crashes with "Invalid column name" rather than degrading. Check
    # first and tell the architect how to fix it instead of erroring.
    if not d.column_exists(engine, schema, "BulkOpsLog", "BatchSize"):
        return 0, [
            f"{schema}.BulkOpsLog exists but predates batch-size tracking -- "
            f"run enable-bulkops-logging --schema {schema} again to upgrade it in place "
            "(existing log history is preserved)."
        ]

    query = d.select_top_n_sql(
        "BatchSize, LockErrorCount",
        f"FROM {d.qualify(schema, 'BulkOpsLog')} "
        "WHERE ObjectName = :obj AND BatchSize IS NOT NULL "
        "ORDER BY CompletedAt DESC",
        hist["runs_considered"],
    )
    with engine.connect() as cx:
        rows = cx.execute(text(query), {"obj": object_name}).fetchall()

    if not rows:
        return 0, []

    last_batch_size, last_lock_errors = rows[0]
    if last_lock_errors:
        rationale.append(
            f"Last run against {object_name} (batch size {last_batch_size}) hit "
            f"{last_lock_errors} row-lock error(s) -- stepping down."
        )
        return -hist["lock_errors_rungs_down"], rationale

    clean_streak = 0
    for _, lock_errors in rows:
        if lock_errors:
            break
        clean_streak += 1

    if clean_streak >= hist["clean_runs_to_increase"]:
        rationale.append(
            f"Last {clean_streak} run(s) against {object_name} had no lock errors -- stepping up cautiously."
        )
        return hist["clean_runs_rungs_up"], rationale

    rationale.append(
        f"Last run against {object_name} (batch size {last_batch_size}) was clean; "
        f"holding size until {hist['clean_runs_to_increase']} consecutive clean runs."
    )
    return 0, rationale


def recommend_batch_size(engine, object_name, schema="dbo"):
    """Return (size, rationale_lines) -- a ladder rung and the full,
    human-readable reasoning behind it (seed -> org automation -> load
    history, in that order), for both bulk_op()'s "auto" mode and the
    standalone recommend-batch-size command."""
    heuristics = _load_heuristics()
    ladder = heuristics["ladder"]

    size, seed_rationale = _seed_lookup(heuristics, object_name)
    rationale = [seed_rationale]

    automation_rungs, automation_rationale = _automation_adjustment(engine, heuristics, object_name, schema)
    rationale.extend(automation_rationale)
    if automation_rungs:
        size = _step(ladder, size, -automation_rungs)

    history_rungs, history_rationale = _history_adjustment(engine, heuristics, object_name, schema)
    rationale.extend(history_rationale)
    if history_rungs:
        size = _step(ladder, size, history_rungs)

    size = max(ladder[0], min(ladder[-1], size))
    rationale.append(f"Recommended batch size: {size}.")
    return size, rationale


def suggest_heuristic_updates(engine, schema="dbo"):
    """Look at dbo.BulkOpsLog for objects whose batch size has converged
    (several recent clean runs at the same size) and print candidate
    reference/batch_size_heuristics.json edits -- never writes the file
    itself. A human reviews and commits deliberately, same as adding a
    new alias to the field-synonym thesaurus."""
    heuristics = _load_heuristics()
    hist = heuristics["history_rules"]

    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "BulkOpsLog"):
        return []
    if not d.column_exists(engine, schema, "BulkOpsLog", "BatchSize"):
        return []

    qualified = d.qualify(schema, "BulkOpsLog")
    with engine.connect() as cx:
        objects = [r[0] for r in cx.execute(
            text(f"SELECT DISTINCT ObjectName FROM {qualified} WHERE BatchSize IS NOT NULL")
        ).fetchall()]

        suggestions = []
        for obj in objects:
            query = d.select_top_n_sql(
                "BatchSize, LockErrorCount",
                f"FROM {qualified} WHERE ObjectName = :obj AND BatchSize IS NOT NULL "
                "ORDER BY CompletedAt DESC",
                hist["runs_considered"],
            )
            rows = cx.execute(text(query), {"obj": obj}).fetchall()
            if len(rows) < hist["clean_runs_to_increase"]:
                continue
            sizes = {r[0] for r in rows}
            all_clean = all(not r[1] for r in rows)
            if len(sizes) == 1 and all_clean:
                converged_size = sizes.pop()
                existing = heuristics.get("object_seeds", {}).get(obj)
                if existing and existing["start"] == converged_size:
                    continue
                suggestions.append({
                    "object": obj,
                    "converged_size": converged_size,
                    "runs": len(rows),
                    "current_seed": existing["start"] if existing else None,
                })
        return suggestions
