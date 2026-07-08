---
description: Create the first (or any brand-new) run-book tab from docs/RUN_BOOK_TEMPLATE.md, optionally auto-filling Script/Transformation rows from analyze-load-order.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-run-book *)
---
Generate a run-book tab for `$ARGUMENTS` (output workbook path, plus
`--tab <name>` required, e.g. Dev1/UAT/PROD).

1. If auto-filling the Script/Transformation section, confirm
   `analyze-load-order` has already been run for those objects (its results
   live in `dbo.ObjectLoadOrder`/`dbo.ObjectDependency`) — if not, suggest
   running it first, or run generate-run-book without `--objects` for a
   blank section to fill in by hand.
2. Run: `.venv/Scripts/python.exe cli.py generate-run-book $ARGUMENTS`
3. This is a **new tab only** — it refuses to overwrite an existing tab name
   in the workbook, since a run-book tab holds live, manually-entered
   operational history that must never be silently clobbered. To carry a
   tab's recipe forward into a new pass (Dev -> UAT -> PROD), use
   `/add-run-book-pass` instead of re-running this on the same tab name.
4. Report the path, the tab name, and whether the Script/Transformation
   section was auto-filled or left blank.

Read-only against Salesforce (no API call, just reads `dbo.ObjectLoadOrder`/
`dbo.ObjectDependency` if `--objects` is given) — safe to run without
confirmation. Note for the user: Pre-/Post-Migration result columns (Person
Responsible, Start, End, Notes) always need a human to fill them in —
`dbo.BulkOpsLog` can't see manual Setup steps like disabling CPQ automation.
