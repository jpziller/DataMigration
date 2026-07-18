---
type: PlatformFinding
title: GiftCommitmentSchedule is auto-created for Recurring-type GiftCommitments
description: Nonprofit Cloud (AFNP) automatically creates a
  GiftCommitmentSchedule when a GiftCommitment's ScheduleType is
  'Recurring' -- a second, explicit insert for the same commitment fails
  live. Confirmed on 6 of 6 real records in this org, not previously
  documented in the migration guide's own Appendix B tables.
tags: [npsp, npc, afnp, gift-commitment, gift-commitment-schedule, automation, platform-finding]
timestamp: "2026-07-18"
---
# GiftCommitmentSchedule is auto-created for Recurring-type GiftCommitments

**Found:** 2026-07-18, tracing a second architect's live-review finding (a
migrated `GiftTransaction` missing its `GiftCommitmentScheduleId`) back to
its actual root cause. This project's own `170_npc_giftcommitmentschedule_from_rd_load.sql`
originally tried to explicitly insert a `GiftCommitmentSchedule` for all 4
Recurring-Donation-derived `GiftCommitment` records. 3 of the 4 inserts
failed live with:

```
FIELD_INTEGRITY_EXCEPTION: You can create the gift commitment schedule
only when it doesn't overlap with an existing schedule.
```

This was recorded in the Load table's own `Error` writeback column at the
time but never investigated until this pass.

**Root cause, confirmed live:** querying the target org directly for every
`GiftCommitmentSchedule` tied to this project's 6 real `GiftCommitment`
records (4 Recurring-Donation-derived, 2 multi-Payment-Opportunity-derived)
showed all 6 already have a real, live schedule:

| GiftCommitment ScheduleType | TransactionPeriod on its real schedule | Who created it |
|---|---|---|
| Recurring (Monthly) | Monthly | **Auto-created by the platform** |
| Recurring (Yearly) | Yearly | **Auto-created by the platform** |
| Recurring (Monthly) | Monthly | **Auto-created by the platform** |
| Custom | Custom | This migration's own explicit insert (170) |
| Custom | Custom | This migration's own explicit insert (190) |
| Custom | Custom | This migration's own explicit insert (190) |

6 of 6 real records are consistent with one rule: **when a `GiftCommitment`
is inserted with `ScheduleType = 'Recurring'`, Nonprofit Cloud automatically
creates its own matching `GiftCommitmentSchedule` immediately** -- an
explicit second insert for that same commitment is redundant and is
rejected by the platform's own "doesn't overlap" validation.
`ScheduleType = 'Custom'` does **not** trigger this auto-creation; those
commitments genuinely need an explicit `GiftCommitmentSchedule` insert.

**What to do:**
- A transform building `GiftCommitmentSchedule` rows for a `Recurring`-type
  commitment should **not** attempt to insert one at all -- filter those
  rows out before the insert, the way
  `170_npc_giftcommitmentschedule_from_rd_load.sql` now does (`WHERE`
  clause restricting to non-Recurring periods only).
- To learn the real (auto-created) schedule's Id for a `Recurring`-type
  commitment -- needed anywhere downstream that wants to reference it (e.g.
  `GiftTransaction.GiftCommitmentScheduleId`) -- **replicate
  `GiftCommitmentSchedule` from the target org** after the parent
  `GiftCommitment` insert has actually run, then join by the real
  `GiftCommitmentId` (a Salesforce relationship, reliable regardless of
  which side created the schedule) rather than by any local Load table's
  own `LoadId`/`MigrationID__c` bookkeeping, which only ever reflects what
  *this migration* explicitly tried to insert.
- This is the same "two-pass requery" shape already established for
  `dbo.Account`/`PersonContactId` in
  `sql/transformations/110_npc_accountcontactrelation_load.sql`'s own
  header comment -- a general pattern, not a one-off: some target objects
  get real child records the platform creates on its own, and a migration
  that only ever inserts and never reads back will silently miss them.

**Executable check:** none yet -- worth a future pre-flight check that
warns before attempting an explicit child-object insert whose parent's own
field values (`ScheduleType = 'Recurring'` here) are known to trigger
platform auto-creation, the same category of check `analyze-org-risk`
already does for validation rules/triggers/Flows, just for a *declarative*
automation rule instead of Apex/Flow metadata (which this specific
behavior doesn't appear to be -- no matching Flow/trigger found via
`analyze-org-risk` against `GiftCommitment`, consistent with this being
core managed-package platform behavior, not client-configured automation).

# Citations

1. Live-confirmed, 2026-07-18, `NPC_TARGET_v2` -- not documented in the
   migration guide's own Appendix B validation tables (see
   `okf/nonprofit-cloud/gift-commitment-schedule-validations.md`,
   `gift-commitment-validations.md`) as of this writing.
