---
description: Write an object's full describe() to metadata/<Object>.json (a local, gitignored-by-default snapshot).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py dump-describe *)
---
Dump full describe() metadata for `$ARGUMENTS` to `metadata/$ARGUMENTS.json`.

1. Run: `.venv/Scripts/python.exe cli.py dump-describe $ARGUMENTS`
2. Report the path written. This is gitignored by default (`metadata/*.json`
   — every org's schema differs, so a describe snapshot isn't template
   content) — mention that committing it is a deliberate per-project choice,
   not automatic, if the user asks about it.

Read-only against the org; writes only a local JSON file — safe to run
without confirmation.
