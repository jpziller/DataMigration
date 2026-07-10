---
description: Diff a filled-in mapping doc against a transform's actual INSERT INTO column list, in both directions, plus validate every referenced field is real and no target field is duplicated.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-mapping-balance *)
---
Check mapping-doc/transform balance for `$ARGUMENTS` (object name, mapping
.xlsx path, transform .sql path).

1. Run: `.venv/Scripts/python.exe cli.py check-mapping-balance $ARGUMENTS`
2. Report five categories, most urgent first:
   - **Not a real field**: a field referenced by the mapping doc or the
     transform doesn't exist in the target object's *current* describe() at
     all — a typo, a removed field, or one that was never actually deployed.
     Treat this as highest priority: it would fail outright at `bulkops`
     time, not just be a documentation gap.
   - **Duplicate implemented column** (hard rule 14): the transform's own
     `INSERT INTO`/`CREATE TABLE` column list names the same column twice —
     this breaks the actual SQL outright, fix before ever running it.
   - **Duplicate target field** (hard rule 14): two or more rows in this one
     mapping-doc sheet chose the same Target Field — different sheets/scripts
     targeting the same field is fine and expected, but not two rows within
     one sheet.
   - **Documented, not implemented**: the mapping doc's Target block shows a
     field as mapped, but the transform's `INSERT INTO` column list doesn't
     populate it — the transform needs updating, or the mapping doc is stale.
   - **Implemented, not documented**: the transform populates a column with
     no row showing it as mapped in the doc.
3. If all five are empty, say so plainly — don't manufacture findings.

Read-only — safe to run without confirmation.
