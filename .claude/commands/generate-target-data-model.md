---
description: Generate a Mermaid ERD for a target-org data model (core + custom objects), styled to approximate Salesforce Data Model Notation, for import into Lucid.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-target-data-model *)
---
Generate a target data model diagram for `$ARGUMENTS` (object names, plus
`--output` and optional `--mapping-path`).

1. Run: `.venv/Scripts/python.exe cli.py generate-target-data-model $ARGUMENTS`
2. Confirm the file was written and report the object count.
3. Remind, if relevant: relationships here are real (from live `describe()`
   via `load_order.py`), not guessed — solid lines are master-detail, dashed
   lines are lookup. This is a best-effort Mermaid approximation of
   Salesforce's own SDMN notation, not a pixel-perfect reproduction — colors/
   border styles from the real notation don't survive into Mermaid.

Read-only against Salesforce — safe to run without confirmation.
