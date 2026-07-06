---
description: Profile a Salesforce object or SQL Server table (population, min/max, distinct counts, value distributions) for migration scoping decisions.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py profile-salesforce *), Bash(.venv/Scripts/python.exe cli.py profile-sql-table *), Bash(.venv/Scripts/python.exe cli.py export-profile-excel *), Bash(sqlcmd *)
---
Profile `$ARGUMENTS` (an object or table name) to help decide what's worth
migrating.

1. If it's not already clear from context, ask (or infer) whether to profile
   directly from Salesforce (`profile-salesforce`) or from an already-
   replicated SQL Server table (`profile-sql-table`) — results can genuinely
   differ between the two (see README's Known limitations: long-text fields
   have no population stats via the Salesforce path at all).
2. Run the appropriate command against `$ARGUMENTS` — it prints a compact
   preview table (field name, type, populated %, distinct count) already;
   paste that output rather than re-deriving a summary from scratch.
3. Call out anything notable in it: fields that are mostly null/blank,
   low-cardinality fields worth reviewing, and any fields the profiler
   couldn't get stats for (full detail — min/max, blank counts, value
   distributions — lives in `dbo.FieldProfile`/`dbo.FieldProfileValues`, not
   the console preview).
4. If asked for a spreadsheet, run `export-profile-excel` and report the path.

Read-only against the org; writes only to dbo.FieldProfile/
dbo.FieldProfileValues in the mirror DB — safe to run without confirmation.
