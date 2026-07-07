---
description: List every Calculated Insight in the org with its dimensions, measures, and last-processed time.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py list-calculated-insights*)
---
List the org's Calculated Insights.

1. Run: `.venv/Scripts/python.exe cli.py list-calculated-insights`
2. Paste the actual output into the reply — don't summarize it.
3. Note the real CI object names end in `__cio` — that exact name is what
   `/query-calculated-insight` needs, not the display name.

Read-only — safe to run without confirmation.
