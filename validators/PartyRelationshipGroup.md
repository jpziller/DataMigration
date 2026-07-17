---
type: ObjectValidator
title: PartyRelationshipGroup validator
description: Object-specific findings for PartyRelationshipGroup
  (Nonprofit Cloud/AFNP) -- Name is required on insert despite describe()
  reporting createable=false, same pattern as GiftCommitment/GiftTransaction;
  no exact "Household" Category value exists.
tags: [object-validator, party-relationship-group, nonprofit-cloud, afnp, npsp-to-npc, household]
timestamp: "2026-07-17"
---
# PartyRelationshipGroup validator

## Name is required on insert despite describe() reporting createable=false
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept -- the
first of three objects this same pass to hit this pattern (also
[GiftCommitment](GiftCommitment.md) and [GiftTransaction](GiftTransaction.md)).
**What happens:** `describe('PartyRelationshipGroup')` reports `Name` as
`createable: False`; the real Bulk API insert fails with
`REQUIRED_FIELD_MISSING: Required fields are missing: [Name]` if it's
omitted.
**Why:** see GiftCommitment.md's write-up for the full reasoning -- a
real `describe()`/API mismatch across this whole AFNP fundraising/CRM
object family, not specific to this one object.
**What to do:** always send a real `Name` value. This migration reused
the linked household Account's own `Name` (e.g. "Chen Household").

## No exact "Household" Category value exists
**Found:** 2026-07-17 -- confirmed live via `describe()`'s real
`picklistValues` for `Category`: `['Staying under same roof', 'Meals
together']`. No `'Household'` value, even though `Type` does have a real
`'Household'` value.
**Why:** `Category` and `Type` are two different picklists on this
object with different intents -- `Type` names the relationship-group
kind (`Household`), `Category` describes *why* the group is related
(shared living situation, shared meals). NPSP's own household concept
doesn't map cleanly to either alone.
**What to do:** set `Type = 'Household'` (the structurally correct
field) and `Category = 'Staying under same roof'` as the closest
practical fit -- not a perfect semantic match, a pragmatic default. A
real client engagement should confirm this default with the client
rather than assume it's always right (e.g. a household migrated from
NPSP data with an explicit "meals together" business meaning would want
the other `Category` value instead).
**Executable check:** none -- a picklist-value choice, not something to
automate.
