---
description: Show a previously-built data-shape profile for an object (auto-created children, automation, field population, structure) before building a transform.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py show-data-shape *)
---
Show the data-shape profile for `$ARGUMENTS` (an object name).

1. Run: `.venv/Scripts/python.exe cli.py show-data-shape $ARGUMENTS`
2. Paste the actual output — the structure / automation / auto-generated
   children / field-population summary is the point, not a paraphrase.
3. Read it before building a transform, alongside `gather-okf` and
   `check-validators`: it tells you the object's *behavior* (what the
   platform auto-creates, what's really populated) that `describe()` alone
   can't. If it reports "NOT scanned"/"NOT profiled", run `analyze-org-risk`
   and/or `profile-salesforce` and rebuild it with `build-data-shape-profile`
   for a fuller picture.

Read-only, no org connection needed (reads the committed JSON).
