---
description: Query a specific Calculated Insight's actual computed data by its real __cio name.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py query-calculated-insight *)
---
Query the Calculated Insight `$ARGUMENTS` (the real object name ending in
`__cio` — run `/list-calculated-insights` first if only the display name
is known).

1. Run: `.venv/Scripts/python.exe cli.py query-calculated-insight $ARGUMENTS`
2. Paste the actual output into the reply — don't summarize it.
3. An empty result is expected if the CI hasn't finished processing —
   check with `/data-cloud-status calculated-insight <Name>` and offer to
   poll with scheduled wakeups until it flips to SUCCESS.

Read-only — safe to run without confirmation.
