---
description: Create the first (or any brand-new) Migration Run Book tab from docs/MIGRATION_RUN_BOOK_TEMPLATE.md, optionally auto-filling the Load phase from analyze-load-order.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-migration-run-book *)
---
Generate a Migration Run Book tab for `$ARGUMENTS` (output workbook path,
plus `--tab <name>` required, e.g. Dev1/UAT/PROD).

1. If auto-filling the Load phase, confirm `analyze-load-order` has
   already been run for those objects (its results live in
   `dbo.ObjectLoadOrder`/`dbo.ObjectDependency`) — if not, suggest running
   it first, or run generate-migration-run-book without `--objects` for a
   blank Load phase to fill in by hand.
2. Run: `.venv/Scripts/python.exe cli.py generate-migration-run-book $ARGUMENTS`
3. This is a **new tab only** — it refuses to overwrite an existing tab name
   in the workbook, since a Migration Run Book tab holds live, manually-
   entered operational history that must never be silently clobbered. To
   carry a tab's recipe forward into a new pass (Dev -> UAT -> PROD), use
   `/add-migration-run-book-pass` instead of re-running this on the same
   tab name.
4. Report the path, the tab name, and whether the Load phase was
   auto-filled or left blank. Mention the header block too (Project/
   Source-Target Environment, Git repo/commit/scripts links, and the
   ticket-system project link if configured) — `--project`/`--source-env`/
   `--target-env`/`--ticket-url`/`--ticket-label` override the auto-filled
   defaults.

Read-only against Salesforce (no API call, just reads `dbo.ObjectLoadOrder`/
`dbo.ObjectDependency` if `--objects` is given) — safe to run without
confirmation. Note for the user: every phase's result columns (Person
Responsible, Begin/End Time, Notes, etc.) always need a human to fill
them in — `dbo.BulkOpsLog` can't see manual Setup steps like disabling
CPQ automation. Status is a real dropdown (Not Started/N/A/In Process/
Completed/Issue) with live conditional-formatting colors.
