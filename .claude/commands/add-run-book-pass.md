---
description: Copy a run-book tab's recipe (Items/Script names/Dependencies/Critical flags) into a new tab for a fresh pass (Dev -> UAT -> PROD), blanking every execution-result column.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py add-run-book-pass *)
---
Add a new pass to `$ARGUMENTS` (workbook path, plus `--from-tab <existing>`
and `--to-tab <new>` required).

1. Run: `.venv/Scripts/python.exe cli.py add-run-book-pass $ARGUMENTS`
2. This copies the source tab's recipe columns (Item/Critical for Pre-/
   Post-Migration; Script # / Name/Dependency for Script/Transformations)
   verbatim — including any rows a human added by hand since the tab was
   generated — and blanks every result column (Person Responsible, Start,
   End, Row Count, Rows Loaded, % Loaded, Errors/Issues, Notes, Total Time)
   for the fresh pass. Critical-row red coloring is reapplied based on the
   copied Critical values.
3. Refuses to overwrite an existing `--to-tab` name — no silent data loss.
4. Report which tab was copied into which new tab.

Read-only against Salesforce and the mirror DB (pure spreadsheet operation)
— safe to run without confirmation.
