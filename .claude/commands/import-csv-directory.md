---
description: Bulk-ingest every CSV in a client-provided directory into the mirror DB, generating/reusing a numbered BULK INSERT script per file with cross-pass structure drift detection.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py import-csv-directory *)
---
Import a CSV directory for `$ARGUMENTS` (directory path, plus `--ticket`,
`--rebuild`, `--run-book`/`--run-book-tab` as needed).

1. Run: `.venv/Scripts/python.exe cli.py import-csv-directory $ARGUMENTS`
2. Report per file, most urgent first:
   - **BLOCKED**: the CSV's current structure no longer matches its
     existing script's column list (added, removed, *or reordered* — BULK
     INSERT maps columns positionally, so a reorder is exactly as
     dangerous as a rename). Show the exact diff. Do not recommend
     `--rebuild` casually — that's the architect's call once they
     understand what changed and why, not a default reaction to a block.
   - **CREATED** / **REUSED** / **REBUILT**: the table, row count, and
     duration for each successfully loaded file.
3. If nothing was blocked, say so plainly.

Writes only to the SQL Server mirror DB (never Salesforce) — same
confirm-the-org spirit as `replicate`/`import-parquet`, not `bulkops`'
per-call gate. `--ticket` is required the first time a script is
generated for a file, or when `--rebuild` is used (hard rule 10).
