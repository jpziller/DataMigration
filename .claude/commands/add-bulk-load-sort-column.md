---
description: Add/refresh a [Sort] column on a load table, numbered by parent key, so bulkops keeps same-parent rows in the same batch (hard rule 6).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py add-bulk-load-sort-column *)
---
Add/refresh the `[Sort]` column for `$ARGUMENTS` (load table name, parent
key column, plus optional `--schema`).

1. Run: `.venv/Scripts/python.exe cli.py add-bulk-load-sort-column $ARGUMENTS`
2. Report plainly:
   - **Clean**: every parent key's rows landed in a contiguous Sort range.
   - **Non-contiguous ranges found**: list each parent key and its
     Sort span exactly as reported -- this means the sort didn't take
     cleanly and needs investigation before `bulkops`, not something to
     wave off.

Works on either SQL backend (`load_table_prep.py` via `sql_dialect.py`, not
a stored procedure). This mutates the load table (adds a column, updates
its values) but is local/reversible SQL, not a Salesforce write --
safe to run without the org-write confirmation `bulkops` itself needs.
