---
description: Generate a Mermaid ERD for a target-org data model (core + custom objects), styled to approximate Salesforce Data Model Notation, for import into Lucid.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-target-data-model *)
---
Generate a target data model diagram for `$ARGUMENTS` (object names, plus
`--output` and optional `--mapping-path`).

1. Run: `.venv/Scripts/python.exe cli.py generate-target-data-model $ARGUMENTS`
2. Confirm the file was written and report the object count.
3. Remind, if relevant: relationships here are real (from live `describe()`
   via `load_order.py`), not guessed — composition (filled diamond) is
   master-detail, aggregation (hollow diamond) is lookup, and each object is
   colored by its real Standard/Custom/External type. A best-effort Mermaid
   `classDiagram` approximation of Salesforce's own SDMN notation (palette
   reused from `forcedotcom/sf-skills`), not a pixel-perfect reproduction.

Read-only against Salesforce — safe to run without confirmation.
