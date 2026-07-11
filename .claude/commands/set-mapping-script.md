---
description: Fill in a mapping doc object's "Transform Script:" header field with the real transform script, auto-resolved -- run only after the script is actually built.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py set-mapping-script *)
---
Set the Transform Script header field for `$ARGUMENTS` (object name and
mapping doc path; optional `--dir source_ingestion`).

1. Run: `.venv/Scripts/python.exe cli.py set-mapping-script $ARGUMENTS`
2. Paste the actual output — it confirms which script filename was set.
3. If it errors with "No transform script found", the real script hasn't
   been built yet — this command is meant to run only after it exists,
   never guessed ahead of time.

Writes to the mapping doc (not read-only), but is a small, safe, targeted
update — only that object's header field, never the Target block a human
fills in.
