---
description: Run an ad hoc SOQL query against Salesforce and show the actual results (console, CSV, or Excel).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py query *)
---
Run the SOQL query `$ARGUMENTS` against the org.

1. Run: `.venv/Scripts/python.exe cli.py query "$ARGUMENTS"`
2. Paste the actual output into the reply — don't summarize it (see
   CLAUDE.md's behavior defaults).
3. If the result was truncated (more records exist than shown), say so and
   offer `--all` or a tighter `LIMIT`/`WHERE` instead of silently moving on.
4. If asked for a file instead of console output, re-run with `--csv <path>`
   or `--excel <path>`.

Read-only against the org (REST Query API, not Bulk API) — safe to run
without confirmation.
