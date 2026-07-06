---
description: Cross-reference the objects a migration touches against the target org's live automation (validation rules, Apex triggers, record-triggered Flows, workflow rules, approval processes).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py analyze-org-risk *)
---
Analyze automation risk for `$ARGUMENTS` (one or more Salesforce object
names, optionally followed by `--mapping-path <xlsx>`).

1. Run: `.venv/Scripts/python.exe cli.py analyze-org-risk $ARGUMENTS`
2. This is an **object-level** automation inventory, not a field-level
   formula parser — it reports what validation rules, Apex triggers,
   record-triggered Flows, legacy workflow rules, and approval processes
   exist on each object, not a guarantee of exactly which ones would fire
   on which migrated row. Say this plainly if asked "will this definitely
   break" — the honest answer is "here's what to review," not a guarantee.
3. If `--mapping-path` is given, an active validation rule's
   `ErrorDisplayField` is cross-referenced against that object's actually-
   migrated target fields (`Migrate Data == Yes` in the mapping doc) and
   flagged as a **direct hit** — a much stronger signal than "this rule
   exists somewhere on the object." Call out direct hits first.
4. Report, per object: counts of each automation type, then the full text
   of every *active* validation rule's error message (these are the ones
   that can outright reject a row), with direct hits called out
   distinctly. If any warnings are reported (a metadata query failed for
   that object), say so rather than silently treating it as "no findings."
5. Point out that this is read-only reconnaissance, not a decision — actual
   handling (bypass a trigger, fix data to satisfy a rule, disable a Flow
   temporarily) is the same "logic disablement" judgment call already
   covered in `docs/MIGRATION_PLAYBOOK.md` §6, not something this command
   does for you.

Read-only against the org (Tooling API + standard Query API, both
read-only calls); writes only to `dbo.ObjectAutomationRisk` in the mirror
DB — safe to run without confirmation.
