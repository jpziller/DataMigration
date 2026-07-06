---
description: Diff a filled-in mapping doc against a transform's actual INSERT INTO column list, in both directions, plus validate every referenced field is real.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-mapping-balance *)
---
Check mapping-doc/transform balance for `$ARGUMENTS` (object name, mapping
.xlsx path, transform .sql path).

1. Run: `.venv/Scripts/python.exe cli.py check-mapping-balance $ARGUMENTS`
2. Report three categories, most urgent first:
   - **Not a real field**: a field referenced by the mapping doc or the
     transform doesn't exist in the target object's *current* describe() at
     all — a typo, a removed field, or one that was never actually deployed.
     Treat this as highest priority: it would fail outright at `bulkops`
     time, not just be a documentation gap.
   - **Documented, not implemented**: the mapping doc's Target block shows a
     field as mapped, but the transform's `INSERT INTO` column list doesn't
     populate it — the transform needs updating, or the mapping doc is stale.
   - **Implemented, not documented**: the transform populates a column with
     no row showing it as mapped in the doc.
3. If all three are empty, say so plainly — don't manufacture findings.

Read-only — safe to run without confirmation.
