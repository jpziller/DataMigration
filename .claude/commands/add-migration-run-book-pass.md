---
description: Copy a Migration Run Book tab's recipe (Stage/Object/Dependency/Critical/JIRA Ticket Link) into a new tab for a fresh pass (Dev -> UAT -> PROD), blanking every execution-result column.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py add-migration-run-book-pass *)
---
Add a new pass to `$ARGUMENTS` (workbook path, plus `--from-tab <existing>`
and `--to-tab <new>` required).

1. Run: `.venv/Scripts/python.exe cli.py add-migration-run-book-pass $ARGUMENTS`
2. This copies the source tab's recipe columns (Stage, Object, Dependency,
   Critical, JIRA Ticket Link — the same schema across every phase)
   verbatim — including any rows a human added by hand since the tab was
   generated — and blanks every result column (Status reset to "Not
   Started" rather than left empty, Person Responsible, Begin/End Time,
   Execution Time, Notes, Total/Success/Failed Records, Success Percent,
   Error Details) for the fresh pass. Critical/Status conditional-
   formatting rules are re-applied so coloring stays live for the new tab.
3. Header block: Project/Source Environment/ticket-system link carry
   forward from the source tab unless `--project`/`--source-env`/
   `--ticket-url`/`--ticket-label` override them. Commit/Branch and the
   Scripts link always refresh to the *current* Git state. Target
   Environment is **never** silently carried forward (Dev/UAT/PROD are
   different Salesforce orgs) — pass `--target-env` explicitly, or it's
   left for a human to fill in.
4. Refuses to overwrite an existing `--to-tab` name — no silent data loss.
5. Report which tab was copied into which new tab.

Read-only against Salesforce and the mirror DB (pure spreadsheet operation)
— safe to run without confirmation.
