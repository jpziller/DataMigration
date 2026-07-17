---
type: ObjectValidator
title: GiftCommitment validator
description: Object-specific findings for GiftCommitment (Nonprofit Cloud/
  AFNP) -- Name is required on insert despite describe() reporting
  createable=false, and ScheduleType must match the Gift Commitment
  Schedule's own TransactionPeriod mapping.
tags: [object-validator, gift-commitment, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-17"
---
# GiftCommitment validator

## Name is required on insert despite describe() reporting createable=false
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept, first
`bulkops insert` against a real GiftCommitment Load table.
**What happens:** `describe('GiftCommitment')` reports `Name` as
`createable: False`, so it's excluded from `bulk_op()`'s auto-derived send
columns by default -- the pre-flight check only warns
("required field(s) not sent... only fails if nothing else defaults
them"), doesn't block. The real Bulk API call then fails with
`REQUIRED_FIELD_MISSING: Required fields are missing: [Name]`.
**Why:** a genuine `describe()`/Bulk-API-reality mismatch on this object --
confirmed live, not assumed. The same pattern hit
[GiftTransaction](GiftTransaction.md) and
[PartyRelationshipGroup](PartyRelationshipGroup.md) independently in the
same migration pass, all three showing the identical `createable: False`
signal for a field that's actually required and genuinely acceptable to
send. `describe()`'s `createable` flag can't be trusted at face value for
`Name` on this object family -- it doesn't distinguish "auto-generated,
truly read-only" (e.g. `GiftCommitmentSchedule.Name`, which really is
read-only and never needed a value) from "required, mislabeled." There's
no way to tell which case you're in from `describe()` alone; it has to be
learned live or from this entry.
**What to do:** always send a real `Name` value in the transform for this
object -- don't rely on the pre-flight warning being survivable. This
migration reused the source Recurring Donation's own `Name`; any
reasonable human-readable label works.
**Executable check:** none yet -- a pre-flight enhancement that escalates
this specific ambiguity (required=true *and* createable=false) to a
louder warning, rather than the current generic wording, would help
future projects notice it before the first failed load rather than after.

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
