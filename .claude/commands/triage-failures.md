---
description: Group a completed bulkops run's failures by normalized error signature and map well-known Salesforce Bulk API error codes to a likely root cause and which command to run next.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py triage-failures *)
---
Triage failures for `$ARGUMENTS` (a load table that's already been
through `bulkops`, or its `<table>_Result` table -- same table
`/bulkops-retry` reads).

1. Run: `.venv/Scripts/python.exe cli.py triage-failures $ARGUMENTS`
   (add `--object <Object>` for real cross-references, and
   `--mapping-path <path>` alongside `--object` for the
   `REQUIRED_FIELD_MISSING` check specifically).
2. If it reports nothing to triage, say so plainly and stop.
3. Otherwise report each distinct error signature (biggest count first),
   its likely cause, and the suggested next step(s) -- this is
   deliberately advisory only: it never changes data and never re-runs
   `bulkops` itself.
4. Remind, if relevant: field-name extraction only happens for
   `REQUIRED_FIELD_MISSING`'s stable bracketed-list message shape --
   every other error code gets guidance text only, never an invented
   field-position guess. `DUPLICATE_VALUE` never gets a live
   cross-reference either, since `analyze-org-risk` doesn't scan
   Salesforce's separate DuplicateRule metadata type today.
5. If `--object`/`--mapping-path` weren't passed and the failures include
   `REQUIRED_FIELD_MISSING` or `FIELD_CUSTOM_VALIDATION_EXCEPTION`,
   mention that re-running with those flags would add real, data-driven
   detail instead of generic guidance.

Read-only, advisory only — safe to run without confirmation.
