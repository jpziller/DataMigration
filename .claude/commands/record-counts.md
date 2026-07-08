---
description: Fast per-object record counts via Salesforce's /limits/recordCount API -- one HTTP call for many objects instead of a SOQL COUNT() per object. Approximate/cached, not exact.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py record-counts*)
---
Get record counts for `$ARGUMENTS` (one or more object names, or
`--all-objects` for the whole org).

1. Run: `.venv/Scripts/python.exe cli.py record-counts $ARGUMENTS`
2. Reformat the output as a Markdown table (`| Object | Record Count |`)
   in the reply, per this repo's tabular-results convention — don't paste
   the raw console alignment.
3. Always relay the trailing caveat line verbatim (or paraphrase it
   faithfully): this is an **approximate, cached snapshot** — confirmed
   live to lag real inserts noticeably, and objects with 0 records are
   omitted entirely rather than shown as 0. **Not** a substitute for
   `profile-salesforce`'s exact `COUNT(Id)` when validating that a load
   actually landed every row — that's what this command is explicitly
   *not* for. It's for fast, rough triage across many objects at once.

Read-only — safe to run without confirmation.
