---
type: ObjectValidator
title: GiftCommitment validator
description: Object-specific findings for GiftCommitment (Nonprofit Cloud/
  AFNP) -- Name is a genuinely required field with no default, and
  ScheduleType must match the Gift Commitment Schedule's own
  TransactionPeriod mapping.
tags: [object-validator, gift-commitment, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-17"
---
# GiftCommitment validator

## Name is a genuinely required field with no default
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept, first
`bulkops insert` against a real GiftCommitment Load table -- omitted
initially, and the real Bulk API call failed with
`REQUIRED_FIELD_MISSING: Required fields are missing: [Name]`.
**Correction (2026-07-18):** this entry originally claimed a
`describe()`/API mismatch (`createable: False` but genuinely required) --
that was wrong, caught by planning a follow-up fix and re-checking
`describe()` directly. The real flags are `createable: True, nillable:
False, defaultedOnCreate: False` -- an ordinary required field, not an
ambiguous one. `bulk_op()`'s own pre-flight check (`bulkops.py`'s
`_preflight_check()`) correctly printed `Warning: required field(s) not
sent... ['Name']` before the failed insert; the actual mistake was
proceeding past that warning instead of treating it as a hard stop. (The
genuinely `createable: False` case on this same object family is
`GiftCommitmentSchedule.Name` -- a real auto-generated field,
`defaultedOnCreate: True`, correctly never needs a value and never hit
this failure. Don't confuse the two.)
**What to do:** always send a real `Name` value in the transform for this
object -- this migration reused the source Recurring Donation's own
`Name`; any reasonable human-readable label works. More generally: treat
`bulk_op()`'s `required field(s) not sent` warning as a hard stop before
running a real load, not something to note and proceed past.

## ScheduleType must match the linked Gift Commitment Schedule's TransactionPeriod
**Found:** 2026-07-17, same migration pass -- a `FIELD_INTEGRITY_EXCEPTION`
on 1 of 4 `GiftCommitmentSchedule` rows: "Prevent mismatched schedule
types... Gift Commitment Schedule types (recurring or custom) match the
Schedule Type specified on the Gift Commitment."
**Why:** a real, documented Appendix B validation rule (see
`okf/npsp-to-npc/gift-commitment-validations.md`) -- a schedule whose
`TransactionPeriod` maps to `'Custom'` (no direct target period, e.g. a
source Quarterly or "1st and 15th" installment) requires its parent
Gift Commitment's own `ScheduleType` to also be `'Custom'`, not
`'Recurring'`.
**What to do:** compute `ScheduleType` on the Gift Commitment transform
with the *exact same* period-mapping `CASE` expression used for
`TransactionPeriod` on the Gift Commitment Schedule transform, so the two
never drift apart -- see `sql/transformations/160_npc_giftcommitment_from_rd_load.sql`
and `170_npc_giftcommitmentschedule_from_rd_load.sql` for the paired
pattern.
**Executable check:** none yet -- a pre-load consistency check comparing
a Gift Commitment's `ScheduleType` against its linked Schedule's
`TransactionPeriod` (both already known at Load-table-build time) would
catch this before the live API call rather than after.
