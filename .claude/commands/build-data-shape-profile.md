---
description: Build a structured, machine-readable data-shape profile per object (aggregates describe() structure, org automation, auto-generated children, and real field population).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py * build-data-shape-profile *)
---
Build data-shape profile(s) for `$ARGUMENTS` (one or more object names).

1. For the fullest profile, run `analyze-org-risk` and `profile-salesforce`
   for these objects first — the profile aggregates their output. (It works
   without them, just reporting those sections as not-yet-collected.)
2. Run: `.venv/Scripts/python.exe cli.py --org <role> build-data-shape-profile $ARGUMENTS`
   (needs an org for the live `describe()`). Writes `data_shapes/<Object>.json`
   and prints a summary.
3. Paste the actual summary output. The profile captures the object's
   *behavior* — auto-created children, active automation, real field
   population — not just describe() structure.
4. `data_shapes/*.json` is org-derived and gitignored by default (commit
   deliberately, like `metadata/`/`mapping/`). Use `show-data-shape <Object>`
   later to read one back without rebuilding.

Read-only against the org (no writes).
