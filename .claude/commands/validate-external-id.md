---
description: Confirm a mapping doc's declared migration-key target field is genuinely externalId+unique in the live org's describe() before any load.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py validate-external-id *)
---
Validate the migration-key field for `$ARGUMENTS` (object name, field API name).

1. Run: `.venv/Scripts/python.exe cli.py validate-external-id $ARGUMENTS`
2. Report plainly:
   - **OK**: the field is real and flagged both External ID and Unique --
     safe to use as a migration key.
   - **NOT VALID**: list each problem exactly as reported (not a real
     field on the object; not flagged External ID; not flagged Unique).
     Do not recommend loading until this is fixed -- and it is not this
     framework's job to create or fix the field, only to gate on it being
     correctly in place (hard rule 12). Fixing it is another team's task.

Read-only — safe to run without confirmation.
