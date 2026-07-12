---
description: Cross-check source table row count, Load table row count, and bulkops' most recent submitted/succeeded/failed counts for each object, flagging anywhere they don't reconcile.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py reconcile-load-counts *)
---
Reconcile row counts for `$ARGUMENTS` (one or more object names, plus
optional `--mapping-path` and `--load-table Object=TableName`).

1. Run: `.venv/Scripts/python.exe cli.py reconcile-load-counts $ARGUMENTS`
2. For each object, report source/Load/bulkops counts and whether it's
   clean or flagged.
3. If `--mapping-path` wasn't given, the source-table row count is
   skipped for every object (still reports Load/bulkops numbers) —
   mention that passing it would add the source-count cross-check, via
   each object's mapping-doc sheet's own "Source Object:" header cell.
4. Flags to relay plainly if present: the Load table doesn't exist yet,
   it has fewer rows than the source (a transform may have dropped
   rows), it's never been loaded via `bulkops`, or its current row count
   no longer matches what the most recent `bulkops` run submitted (a
   stale prior run — rerun `bulkops` to pick up the current Load table).

Read-only, no Salesforce connection needed — just the mirror DB and
(with `--mapping-path`) the local mapping workbook. Safe to run without
confirmation.
