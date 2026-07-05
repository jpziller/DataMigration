---
description: Generate a field-mapping Excel workbook for a Salesforce object from its describe() metadata.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-mapping-doc *)
---
Generate a mapping doc for `$ARGUMENTS` (an object name, optionally with an
output path and `--source-table <Table>`).

1. Run: `.venv/Scripts/python.exe cli.py generate-mapping-doc $ARGUMENTS`
   (default output path convention: `mapping/<Object>_Mapping.xlsx`)
2. This produces one row per target field (type, required, real picklist
   values) with blank Source Field/Source Type/Transformation Notes columns
   — it does **not** guess the mapping, that's a human (or a future
   auto-mapping tool) task. If `--source-table` was given, a companion
   reference sheet lists that table's columns.
3. Report the path and row count, and remind the user this is a starting
   structure to fill in, not a finished mapping.

Read-only against the org; writes only a local .xlsx file — safe to run
without confirmation.
