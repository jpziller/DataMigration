---
description: Run ANSI SQL against the Data Cloud tenant's own query API (for what plain SOQL can't do).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py data-cloud-query *)
---
Run the Data Cloud SQL query `$ARGUMENTS`.

1. Run: `.venv/Scripts/python.exe cli.py data-cloud-query "$ARGUMENTS"`
2. Paste the actual output into the reply — don't summarize it (see
   CLAUDE.md's behavior defaults).
3. If it fails with the invalid_scope guidance, relay that message —
   it means the current auth's connected app lacks Data Cloud OAuth
   scopes (see ROADMAP.md #18 for the tested External Client App setup),
   not a user permission problem.

Note: basic single-DLO/DMO lookups don't need this — plain `/query` works
on `__dlo`/`__dlm` objects directly. Reach for this specifically for
cross-object Data Cloud SQL. Read-only — safe to run without confirmation.
