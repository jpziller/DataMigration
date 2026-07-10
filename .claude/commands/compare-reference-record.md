---
description: Diff a live, hand-created reference record against the Load table row its migration key corresponds to.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py compare-reference-record *)
---
Compare a reference record for `$ARGUMENTS` (object name, Load table name,
record Id, plus `--migration-key <Field>`).

1. Run: `.venv/Scripts/python.exe cli.py compare-reference-record $ARGUMENTS`
2. Report field-by-field: which fields match, which differ (load table
   value vs. live value), most useful line first ("all fields match" or
   the count that differ).
3. This is a review/debugging aid for fixing the SQL transform — never
   suggest writing anything back based on this comparison; that's a
   separate, human-decided step.

Read-only — a `describe()` call, one SOQL query, one SQL Server SELECT.
Safe to run without confirmation.
