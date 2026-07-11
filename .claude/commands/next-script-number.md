---
description: Suggest the next number for a new sql/transformations/ or sql/source_ingestion/ script, following the project's gap-of-10 numbering convention.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py next-script-number *)
---
Suggest a script number for `$ARGUMENTS` (optional: `--dir source_ingestion`,
or `--after <NNN> --before <MMM>` to insert between two existing scripts).

1. Run: `.venv/Scripts/python.exe cli.py next-script-number $ARGUMENTS`
2. Paste the actual output — it's just a single zero-padded number.
3. Use that number when naming the new script (e.g. `040_account_load.sql`).

Read-only, advisory only — never creates, renames, or renumbers a file
itself. Scripts are numbered in gaps of 10 (010, 020, 030...) specifically
so a script that needs to be inserted later between two that already exist
can take an unused number in that gap (via `--after`/`--before`) without
renumbering anything already committed.
