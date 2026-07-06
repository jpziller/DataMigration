---
description: Write an object's full describe() to metadata/<Object>.json for git (a committed describe snapshot).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py dump-describe *)
---
Dump full describe() metadata for `$ARGUMENTS` to `metadata/$ARGUMENTS.json`.

1. Run: `.venv/Scripts/python.exe cli.py dump-describe $ARGUMENTS`
2. Report the path written, and mention it's meant to be committed
   (`metadata/*.json` — committed describe snapshots, per CLAUDE.md's
   "Where things live").

Read-only against the org; writes only a local JSON file — safe to run
without confirmation. Committing it is a separate, explicit step.
