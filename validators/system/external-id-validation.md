---
type: SystemValidator
title: Live Migration Key Validation Rule (Hard Rule 12)
description: Confirm the migration-key field is genuinely flagged External
  ID and Unique in the target org's live describe() before any load --
  never assumed from the mapping doc's field name or the transform's
  column name, since org state is the one side that can silently drift.
tags: [system-validator, hard-rule-12, external-id, describe]
timestamp: "2026-07-11"
---
# Live Migration Key Validation Rule (System Validator)

CLAUDE.md Hard Rule #12. Applies to every object before its first
`bulkops insert`/`upsert` (or a delete resolved by external id).

## What happens if skipped
The mapping doc or the transform's own column name might call a field
`Legacy_Id__c`/`MigrationID__c` and assume it's a real, working external
ID — but that field might not actually be deployed yet, might not be
flagged **External ID**, or might not be flagged **Unique**, in the
*target org's current state*. Loading against a field that looks right
but isn't actually configured as an external id breaks upsert semantics
and the fingerprint-based result mapping (Hard Rule #4) that depends on
it being genuinely unique.

## Why
A field's intended role (migration key) is a mapping-doc/transform-code
convention; whether the org's live `describe()` actually agrees is a
separate, checkable fact — and the only one of the two that can silently
drift (a field can be modified or never fully deployed) without any local
sign of it.

## What to do
Check live, every time, before the first insert/upsert against a given
object in a given org — don't assume from the mapping doc's field name or
the transform's column name. Do not proceed until it passes. Fixing a
failing field is another team's job (this framework doesn't create or
alter Salesforce metadata to make a check pass) — this rule only gates on
it already being correctly in place.

## Executable check
```
.venv/Scripts/python.exe cli.py validate-external-id <Object> <Field>
```
Read-only, no confirmation needed (it's just a `describe()` read).
Exits nonzero on failure so it can gate a script rather than only being
eyeballed.
