---
description: Sample a small set of real target-object records to learn their true field-level shape -- what's actually populated, not just what describe() or a page layout shows.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py sample-reference-records *)
---
Sample reference records for `$ARGUMENTS` (object name, plus `--ids
<id1,id2,...>` or `--where "<SOQL WHERE>"` -- prefer `--ids` when the
user has specific record Ids in mind, especially a record they or
another human hand-created through the real UI flow).

1. Run: `.venv/Scripts/python.exe cli.py sample-reference-records $ARGUMENTS`
2. Report the per-field shape as a Markdown table (per this project's own
   chat-formatting convention) — field, type, populated N/M, `describe()`
   flags (createable/required/auto-default), sample value(s). Lead with
   anything populated in every sample but not obviously mapped from a
   known source field — that's the signal worth flagging (the exact
   pattern that would have caught this project's own `Name`-field
   findings on Nonprofit Cloud objects immediately instead of by
   trial-and-error).
3. This is a learning/discovery aid, usable at any point in a project —
   before a transform exists, mid-sprint, or after a UAT finding reveals
   a gap — not a one-time pre-build gate. If no Ids/filter were given and
   this fell back to "most recently created," say so explicitly and
   suggest the user provide real, known-good record Ids instead (only a
   human knows which records are genuinely good examples).
4. Complements `/compare-reference-record` (a later-stage, targeted diff
   against an existing Load table) — don't confuse the two.

Read-only — a `describe()` call, one SOQL query, one SQL Server SELECT
against `dbo.ObjectAutomationRisk` if it exists. Safe to run without
confirmation.
