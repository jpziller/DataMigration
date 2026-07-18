---
type: MigrationPattern
title: Name is a required field with no default on several fundraising objects (Nonprofit Cloud/AFNP)
description: GiftCommitment, GiftTransaction, and PartyRelationshipGroup
  all require a real Name value on insert with no platform-provided
  default -- confirmed live across all three, a genuinely required field
  in each case (not a describe() ambiguity, an earlier version of this
  finding claimed otherwise and was wrong).
tags: [npc, afnp, name-field, describe, nonprofit-cloud, data-quality]
timestamp: "2026-07-17"
---
# Name is a required field with no default (Nonprofit Cloud/AFNP)

**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept, across
three separate objects independently — `GiftCommitment`, `GiftTransaction`,
`PartyRelationshipGroup` (full object-level detail in each object's own
validator: [validators/GiftCommitment.md](../../validators/GiftCommitment.md),
[validators/GiftTransaction.md](../../validators/GiftTransaction.md),
[validators/PartyRelationshipGroup.md](../../validators/PartyRelationshipGroup.md)).

**What happens:** `Name` is not populated by any transform against these
objects by default (there's no obvious 1:1 source field the way there is
for, say, `Account.Name`), and omitting it fails the real Bulk API insert
with `REQUIRED_FIELD_MISSING: Required fields are missing: [Name]`.

**Correction (2026-07-18):** this entry originally claimed
`describe()`'s `createable` flag reports `False` for `Name` on these
objects while the field is genuinely required and acceptable to send —
framed as a `describe()`/API mismatch. **That was wrong**, caught while
planning a follow-up fix and re-checking `describe()` directly against
the live target org: the real flags are `createable: True, nillable:
False, defaultedOnCreate: False` on all three objects — an ordinary
required field with no default, not an ambiguous one.
`bulkops.py`'s pre-flight check (`_preflight_check()`) already prints a
correct `Warning: required field(s) not sent...` for exactly this case
before any live API call — the actual lesson from this migration is to
treat that warning as a hard stop, not evidence to proceed past. (The
genuinely `createable: False` case that exists elsewhere on this same
object family, `GiftCommitmentSchedule.Name`, has `defaultedOnCreate:
True` — a real auto-generated field that correctly never needs a value —
and was mistakenly conflated with the other three in the original
version of this finding.)

**Why this is still a genuinely platform-level, source-agnostic finding**
(not tied to NPSP as the source): any migration into Nonprofit Cloud,
regardless of what system it's migrating *from*, needs to populate a
real `Name` value on `GiftCommitment`, `GiftTransaction`, and
`PartyRelationshipGroup` — there's no natural source field for this on
any of the three (they're all target-side compound/relationship records,
not 1:1 field carry-overs), so a real transform has to choose one
deliberately (this migration reused each object's most relevant related
record's own `Name` — the source Recurring Donation/Opportunity/Payment
for the first two, the linked household Account for the third).

**What to do:** always send a real `Name` value in the transform for
these three objects. More generally, run `bulkops` once against a small
test batch for any new AFNP object before a real load, and treat its
pre-flight `required field(s) not sent` warning (if any) as something to
fix before proceeding, not just a note in passing.
