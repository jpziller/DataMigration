---
description: Show field-level describe() metadata for a Salesforce object (type, length, createable/updateable, references).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py describe *)
---
Describe the Salesforce object `$ARGUMENTS`.

1. Run: `.venv/Scripts/python.exe cli.py describe $ARGUMENTS`
2. Paste the actual field list — don't summarize it away. This is the
   ground truth for field API names (CLAUDE.md rule 5) — never guess a
   field name when this command can confirm it in one call.

Read-only against the org — safe to run without confirmation.
