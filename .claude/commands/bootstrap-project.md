---
description: Bootstrap a new migration project from a discovery-AI-produced YAML brief -- confirms every object is real, runs analyze-load-order, and scaffolds a Migration Run Book.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py bootstrap-project *)
---
Bootstrap a project for `$ARGUMENTS` (brief YAML path, Run Book output
path, plus `--tab <name>` required).

1. Run: `.venv/Scripts/python.exe cli.py bootstrap-project $ARGUMENTS`
2. Report the confirmed object count and any problems (a typo'd or
   nonexistent object plainly named) — never silently skipped.
3. If the brief's `target_org_alias` doesn't match this session's actual
   configured org alias, relay that warning plainly — it's informational,
   not a hard block (the brief may predate the final alias decision).
4. If a ticket was given, mention it's a reminder for the Script Ticket
   Traceability Rule (hard rule 10) once real transform scripts get
   built — not something written into the Run Book itself.
5. State the natural next step: profile the source tables, then
   `generate-mapping-doc`/`auto-map` — this bootstrap deliberately never
   guesses mapping, field lists, or transform logic from the brief's own
   notes.

Read-only against Salesforce (only calls `describe()`); writes the
mirror DB's load-order tables and a new Migration Run Book tab (refuses
to overwrite an existing one) — safe to run without confirmation.
