---
type: ObjectValidator
title: PartyRelationshipGroup validator
description: Object-specific findings for PartyRelationshipGroup
  (Nonprofit Cloud/AFNP) -- Name is a genuinely required field with no
  default, same pattern as GiftCommitment/GiftTransaction; no exact
  "Household" Category value exists; Category should not be invented at
  all, per real reference-record evidence.
tags: [object-validator, party-relationship-group, nonprofit-cloud, afnp, npsp-to-npc, household]
timestamp: "2026-07-18"
---
# PartyRelationshipGroup validator

## Name is a genuinely required field with no default
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept -- the
first of three objects this same pass to hit this pattern (also
[GiftCommitment](GiftCommitment.md) and [GiftTransaction](GiftTransaction.md)).
Omitted initially, real Bulk API insert failed with
`REQUIRED_FIELD_MISSING: Required fields are missing: [Name]`.
**Correction (2026-07-18):** see GiftCommitment.md's own corrected
write-up -- an ordinary required field (`createable: True, nillable:
False, defaultedOnCreate: False`), not a `describe()`/API mismatch as
originally (incorrectly) claimed here. `bulk_op()`'s pre-flight check
already warned about this correctly before the failure.
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
**Correction (2026-07-18):** the guidance above was wrong in practice.
A second architect reviewed the live `NPC_TARGET_v2` org and flagged the
migrated household data as looking off; using `sample-reference-records`
against 10 real, non-migrated PartyRelationshipGroup records in that same
org showed `Category` populated **0 of 10 times**. Real household groups
in this org essentially never set it at all -- inventing
`'Staying under same roof'` on every one of our 8 migrated records was
itself a shape defect, not a harmless pragmatic default. **What to do
now:** leave `Category` unset unless a real client conversation gives a
specific reason to populate it -- don't default it just because a
plausible-looking picklist value exists. `Type = 'Household'` is still
correct (matches real usage). Fixed in
`sql/transformations/120_npc_partyrelationshipgroup_load.sql`.

## Address and other fields real reference records sometimes populate
**Found:** 2026-07-18, same review pass. The same 10-record sample showed
`PrimaryStreet`/`PrimaryCity`/`PrimaryState`/`PrimaryPostalCode`/
`PrimaryCountry` populated 2-3 of 10 times, and `GroupIncome`/`GroupSize`/
`Subtype` populated 1-2 of 10 times -- none of which the migration
originally touched.
**What to do:** the address fields have a natural, evidenced source (the
household Account's own Billing address, already carried in
`HouseholdAccount_Load`) and were added. `GroupIncome`/`GroupSize`/
`Subtype` were deliberately left unset -- too sparse in real data (1-2/10)
to treat as a reliable pattern worth inventing a derivation for; a real
engagement should ask the client rather than guess.
