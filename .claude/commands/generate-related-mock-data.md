---
description: Generate relationship-aware mock data across multiple objects via Snowfakery (children really reference their parents).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-related-mock-data *), Read(_stage/**)
---
Generate related mock data for `$ARGUMENTS` (object names, with per-object
counts — e.g. `Account Contact --count Account=10 --count Contact=3`; if
the user gave objects but no counts, ask what counts they want rather than
guessing — top-level counts are totals, nested counts are per-parent).

1. Run: `.venv/Scripts/python.exe cli.py generate-related-mock-data <Objects...> --count NAME=N ...`
2. Report: the recipe path written to `_stage/` (it's reviewable/hand-editable),
   which object nested under which parent, rows written per `<Object>_Mock`
   table, and skipped fields.
3. If it fails on an unresolved circular dependency, relay that clearly —
   the object set can't be auto-nested and needs narrowing or a hand-built
   recipe.

Writes only to `<Object>_Mock` tables in the mirror DB — never touches
Salesforce (a child's parent link is a synthetic `_ParentMockRef` column,
not a real Salesforce Id). Safe to run without confirmation.
