---
description: Flag every mapping-doc row marked Migrate Data = Yes with no Target Field chosen yet, and attempt a describe()-driven suggestion for each.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-required-mappings *)
---
Check for unmapped required fields for `$ARGUMENTS` (object name, mapping
.xlsx path).

1. Run: `.venv/Scripts/python.exe cli.py check-required-mappings $ARGUMENTS`
2. Report each gap plainly: the source field, and either the suggested
   target field (with match method/confidence) or that no confident
   suggestion was found and it needs manual review.
3. If there are no gaps, say so plainly — don't manufacture findings.

Read-only — never writes into the mapping doc (that's `auto-map`'s job;
this is a diagnostic, not a second writer). Safe to run without
confirmation.
