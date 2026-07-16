---
type: SystemValidator
title: RecordType Resolution Rule (Hard Rule 15)
description: Resolve the target org's real RecordTypes into
  dbo.RecordTypeMap and JOIN by DeveloperName to populate RecordTypeId --
  RecordType Ids are org-specific and never portable, so a hand-copied
  source Id either fails or silently resolves to the wrong record type.
tags: [system-validator, hard-rule-15, record-types]
timestamp: "2026-07-11"
---
# RecordType Resolution Rule (System Validator)

CLAUDE.md Hard Rule #15. Applies to any object whose Load table populates
`RecordTypeId` — conditional on the object, not universal like rules 6/7/12,
but still a system-level check (not object-specific knowledge) whenever
it's relevant.

## What happens if skipped
RecordType `Id` values are **org-specific** and never portable across
orgs — a RecordType Id copied from a source system, a sandbox, or a prior
org will not resolve to the same (or any) real record type in the target
org. Hand-copying a raw source Id into `RecordTypeId` either fails outright
or, worse, silently resolves to the *wrong* record type in the target org
if the Id happens to collide with something else there.

## Why
`DeveloperName` (not `Id`) is the one RecordType identifier that's
actually portable across orgs — it's the human-chosen API name, not an
org-generated primary key.

## What to do
Resolve the target org's real RecordTypes first, then have the
transform's own SQL `JOIN dbo.RecordTypeMap` by `DeveloperName` to
populate `RecordTypeId` — never hand-copy a raw Id from the source. This
design deliberately has **no automatic unresolved-value guard**: use a
`LEFT JOIN` so an unmatched `DeveloperName` surfaces as a visible `NULL
RecordTypeId` rather than silently failing later, and manually verify no
row is left unresolved before loading.

## Executable check
```
.venv/Scripts/python.exe cli.py resolve-record-types <Object>
```
Read-only against Salesforce (queries the org's real RecordType rows),
writes only to `dbo.RecordTypeMap` (shared across every object in the
project, like `dbo.FieldProfile`). After running it, confirm no row in
the built Load table has a NULL `RecordTypeId` where one was expected —
this framework doesn't do that verification automatically; a simple
`SELECT COUNT(*) FROM <LoadTable> WHERE RecordTypeId IS NULL` against the
transform's own `LEFT JOIN` catches it.
