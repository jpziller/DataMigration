---
description: Print bulkops' dynamic batch-size recommendation for an object, with full rationale, without loading anything.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py recommend-batch-size *)
---
Recommend a batch size for `$ARGUMENTS` (an object name).

1. Run: `.venv/Scripts/python.exe cli.py recommend-batch-size $ARGUMENTS`
2. Paste the actual output into the reply — don't summarize it. The
   rationale lines (seed knowledge, org automation, load history) are the
   point of this command, not just the final number.
3. If the rationale says `analyze-org-risk` hasn't been run yet, or that
   `dbo.BulkOpsLog` predates batch-size tracking, mention that as an easy
   next step to get a better-informed recommendation.

Read-only, no Salesforce call — safe to run without confirmation.
