---
description: Generate one Mermaid ERD per subject area for source staging tables, with naming-convention-guessed relationships flagged for review.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-source-data-model *)
---
Generate source data model diagram(s) for `$ARGUMENTS` (one or more
`--subject-area "Name:Table1,Table2"`, plus `--output-dir` and optional
`--schema`/`--mapping-path`).

1. Run: `.venv/Scripts/python.exe cli.py generate-source-data-model $ARGUMENTS`
2. Report each file written, and **every guessed relationship printed** —
   these come from a naming-convention heuristic only (staging tables carry
   no real foreign keys), never a confirmed fact. Present them as "review
   these" findings, not as settled truth.
3. Subject-area groupings are the human's own choice, not auto-clustered —
   don't second-guess or suggest different groupings unless asked.

Read-only — safe to run without confirmation.
