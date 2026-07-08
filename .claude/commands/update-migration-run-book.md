---
description: Pull new dbo.BulkOpsLog rows into a Migration Run Book tab's Load phase -- fills in pending placeholders, inserts new rows for anything unmatched, never overwrites already-resolved or human-entered rows.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py update-migration-run-book *)
---
Sync `$ARGUMENTS` (workbook path, plus `--tab <name>` required) from
`dbo.BulkOpsLog`.

1. Run: `.venv/Scripts/python.exe cli.py update-migration-run-book $ARGUMENTS`
2. This is idempotent — it tracks a per-tab watermark (Last Synced Log Id,
   in the breadcrumb block) and only ever pulls in `BulkOpsLog` rows newer
   than that. Running it again immediately after should report 0 synced.
3. For each new log entry, it looks for a still-pending Load-phase
   placeholder row for that object (blank Status and Total Records) and
   fills it in; if none exists (already resolved from an earlier run, or
   never pre-populated), it inserts a brand-new row instead — it never
   overwrites a row that already has real data, whether that came from a
   prior sync or a human typed it in.
4. Only aggregate counts/timing come from `BulkOpsLog` — per-row error
   text isn't populated here (that would need the separate `_Result`
   writeback table, not read by this command).
5. Report the counts (synced/inserted/updated), or the "nothing to sync"
   message if `dbo.BulkOpsLog` doesn't exist yet for that schema.

This is also available as an opt-in automatic step on `bulkops` itself via
`--run-book`/`--run-book-tab` (same underlying sync), for when you want
it to happen right after a load finishes instead of running this
separately.

Read-only against Salesforce (only reads `dbo.BulkOpsLog`, writes the
local `.xlsx`) — safe to run without confirmation.
