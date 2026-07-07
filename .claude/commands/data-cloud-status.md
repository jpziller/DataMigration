---
description: Check processing status for Data Cloud jobs -- Calculated Insights, Data Streams, DSOs, Identity Resolution, Data Transforms, Data Graphs.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py data-cloud-status *)
---
Check Data Cloud status for `$ARGUMENTS` (a type — one of
`calculated-insight`, `data-stream`, `dso`, `identity-resolution`,
`data-transform`, `data-graph` — optionally followed by a specific Name).

1. Run: `.venv/Scripts/python.exe cli.py data-cloud-status $ARGUMENTS`
2. Paste the actual output into the reply — don't summarize it.
3. If the user is waiting on a job to finish (e.g. LastRunStatus is
   IN_PROGRESS or PROCESSING), offer to keep polling with scheduled
   wakeups until it completes rather than making them re-ask.

Plain core-org SOQL — no Data Cloud tenant token needed. Read-only, safe
to run without confirmation.
