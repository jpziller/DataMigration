---
description: Diff a filled-in mapping doc against a transform's actual INSERT INTO column list, in both directions.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-mapping-balance *)
---
Check mapping-doc/transform balance for `$ARGUMENTS` (object name, mapping
.xlsx path, transform .sql path).

1. Run: `.venv/Scripts/python.exe cli.py check-mapping-balance $ARGUMENTS`
2. Report both directions clearly:
   - **Documented, not implemented**: the mapping doc says a field is
     mapped (has a Source Field filled in) but the transform's `INSERT INTO`
     column list doesn't populate it — the transform needs updating, or the
     mapping doc is stale.
   - **Implemented, not documented**: the transform populates a column with
     no corresponding mapped row in the doc. This also catches a transform
     referencing a field that doesn't exist in the object's *current*
     describe() at all (it can't have a row if it isn't a real field) —
     treat that case as higher priority, since it would fail outright at
     `bulkops` time, not just be an undocumented mapping.
3. If both lists are empty, say so plainly — don't manufacture findings.

Read-only — safe to run without confirmation.
