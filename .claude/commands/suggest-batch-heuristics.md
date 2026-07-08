---
description: Print candidate reference/batch_size_heuristics.json edits based on this project's own converged load history.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py suggest-batch-heuristics*)
---
Suggest batch-size heuristic updates.

1. Run: `.venv/Scripts/python.exe cli.py suggest-batch-heuristics`
2. Paste the actual output into the reply — don't summarize it.
3. This never writes the file itself — if there are suggestions, offer to
   help edit `reference/batch_size_heuristics.json`'s `object_seeds`, but
   only commit the change if the user asks; a human decides what cross-
   project knowledge is worth keeping, same as the field-synonym thesaurus.

Read-only — safe to run without confirmation.
