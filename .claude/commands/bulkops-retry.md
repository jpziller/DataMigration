---
description: Copy only the failed rows from a load/result table into a fresh <table>_Retry table, for resubmission -- does not call Salesforce itself.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py bulkops-retry *)
---
Build a retry table for `$ARGUMENTS` (a load table that's already been
through `bulkops`, or its `<table>_Result` table).

1. Run: `.venv/Scripts/python.exe cli.py bulkops-retry $ARGUMENTS`
2. This only copies rows where `Error` is populated into a new
   `<table>_Retry` table -- it does **not** call Salesforce and does **not**
   resubmit anything itself. If it reports zero failed rows, say so plainly
   and stop; there's nothing to retry.
3. If rows were copied, tell the user the new table name and that the next
   step is a normal, explicitly-confirmed `bulkops` run against it (same
   org/auth confirmation as any other `bulkops` call — this command does
   not skip that).
4. Before suggesting a retry, it's worth a quick look at the copied rows'
   `Error` text (`/validate-load` on the new table works fine for this) --
   if every failure is the same root cause (e.g. a bad field mapping),
   fixing the transform and rebuilding the load table is probably the
   right move instead of blindly resubmitting the same bad data.

Read-only against the org; writes only a new table in the mirror DB (SQL
Server, not Salesforce) — safe to run without confirmation.
