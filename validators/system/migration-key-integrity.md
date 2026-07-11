# Migration Key Integrity Rule (System Validator)

CLAUDE.md Hard Rule #7. Applies to **every object**, every `*_Load` table,
no exceptions — this is the "is the migration key populated and unique"
check.

## What happens if skipped
`bulkops`' result mapping is fingerprint-based (Hard Rule #4, Fingerprint
Result Mapping), not row-order — Bulk API 2.0 returns success/failure sets
with no guaranteed order, so results are matched back to the submitted
rows by fingerprinting each row's sent columns (or, with
`--fingerprint-columns`, just the migration key alone). A duplicate or
NULL migration key breaks that matching silently: two rows with the same
key fingerprint become genuinely ambiguous, surfacing later as an
unexplained `ambiguous` count in `bulkops`' summary — *after* a real
Salesforce API call has already run, not before.

## Why
This is a data-integrity gate, not a data-quality one. A duplicate key
means the fingerprint (or the external-id upsert match) can no longer
distinguish two rows — it's not "some rows might be slightly off," it's
"the framework's own result-writeback mechanism has broken down for those
rows."

## What to do
Resolve every duplicate/NULL the check reports before ever calling
`bulkops` — don't let it surface later as an unexplained `ambiguous`
count. This is unconditional: every `*_Load` table, every migration key
column, every time.

## Executable check
```
.venv/Scripts/python.exe cli.py check-load-table-duplicate-keys <LoadTable> <MigrationKeyColumn>
```
`load_table_prep.py` — plain Python + inline SQL, works on either SQL
backend. Exits nonzero if anything is found, so it can gate a script
rather than only being eyeballed.
