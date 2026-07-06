---
description: List queryable Salesforce objects in the org (add --all for non-queryable ones too).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py list-objects*)
---
List Salesforce objects for `$ARGUMENTS` (empty, or `--all` for
non-queryable objects too).

1. Run: `.venv/Scripts/python.exe cli.py list-objects $ARGUMENTS`
2. Paste the actual output — don't just say "here are the objects," show
   them (see CLAUDE.md's behavior defaults).

Read-only against the org — safe to run without confirmation.
