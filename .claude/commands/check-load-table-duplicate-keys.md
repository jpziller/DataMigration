---
description: Check a load table's migration-key column for duplicate or missing values before bulkops (hard rule 7).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-load-table-duplicate-keys *)
---
Check the migration key for `$ARGUMENTS` (load table name, key column,
plus optional `--schema`).

1. Run: `.venv/Scripts/python.exe cli.py check-load-table-duplicate-keys $ARGUMENTS`
2. Report plainly:
   - **OK**: no duplicates or missing values -- safe to load.
   - **Problems found**: list every duplicate key (with its occurrence
     count) and the missing-key row count exactly as reported. Resolve
     every duplicate before loading -- don't let it surface later as an
     unexplained `ambiguous` count after a real Salesforce API call
     (hard rule 4).

Works on either SQL backend (`load_table_prep.py` via `sql_dialect.py`, not
a stored procedure). Read-only — safe to run without confirmation. Exits
nonzero on any finding, so it can gate a script.
