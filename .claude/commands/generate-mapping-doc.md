---
description: Generate a field-mapping Excel tab (one row per source field) for a source SQL table -> target Salesforce object.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-mapping-doc *)
---
Generate a mapping tab for `$ARGUMENTS` (target object name, output path,
source SQL table name — all three required).

1. Run: `.venv/Scripts/python.exe cli.py generate-mapping-doc $ARGUMENTS`
   (convention: one shared workbook for the whole project, e.g.
   `mapping/Migration_Mapping.xlsx` — reuse the same output path across
   objects. Each run adds/replaces that object's own sheet; it does not
   overwrite the rest of the workbook.)
2. Structure (matches a real-world field-inventory template — one row per
   **source** field, not target): header block (Source/Target object
   names), then columns Source Object / Field API / Field Label / Data Type
   / Description / Data Profile Populated On / Data Profile % / Notes / Migrate
   Data / Migrate Field / Biz Review Req / Biz Decision / [spacer] / Target
   Object / Field API / Field Label / Data Type / Description / Notes. The
   Target block is left blank — it does **not** guess the mapping (that's a
   human, or a future auto-mapping tool).
3. If profiling data already exists for the source table (`/profile`),
   "Data Profile Populated On"/"Data Profile %" are pre-filled automatically —
   mention this if it happened.
4. Report the path and row count, and remind the user the Target block is a
   starting structure to fill in, not a finished mapping.

Read-only against the org and mirror DB; writes only a local .xlsx file —
safe to run without confirmation. `mapping/*.xlsx` is gitignored by default
(it's project-specific mapping decisions, not template content) — mention
that committing it is a deliberate choice if the user asks.
