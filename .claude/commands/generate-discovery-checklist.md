---
description: Generate the discovery questions an architect should be asking about each object, derived from live org signals (active validation rules, RecordType usage, out-of-scope lookup dependencies) instead of a generic template.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-discovery-checklist *)
---
Generate a discovery checklist for `$ARGUMENTS` (one or more object
names, plus optional `--output <path.md>`).

1. Run: `.venv/Scripts/python.exe cli.py generate-discovery-checklist $ARGUMENTS`
2. Relay the questions back per object — these are meant to be asked of
   the client during discovery, not answered here.
3. Remind, if relevant: this is the companion to `/bootstrap-project`
   running the other direction — the questions come from real, live
   signals (an active validation rule's `ErrorDisplayField`, whether the
   object carries `RecordTypeId`, a reference field pointing at an object
   not yet in this candidate list), never a generic checklist template.
4. If an object shows a dependency question (depends on an object not in
   this list), mention that adding that object to the next run would
   suppress it, or confirm with the client whether it's genuinely out of
   scope.

Read-only against Salesforce (`describe()` + a live `analyze-org-risk`-
style scan per object) — no mirror-DB dependency, safe to run without
confirmation, and works even before the SQL Server side of a project
exists yet.
