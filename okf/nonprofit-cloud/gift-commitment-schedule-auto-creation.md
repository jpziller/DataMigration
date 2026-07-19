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

**Executable check:** built 2026-07-18, same day this was found —
`child_record_risk.py`'s `detect_auto_generated_children()`, run
automatically by `analyze-org-risk` (`--skip-child-shape-check` to opt
out). Since this behavior genuinely isn't visible via the Tooling API (no
matching Flow/trigger found against `GiftCommitment`, confirmed live —
this is core managed-package platform behavior, not client-configured
automation), the check infers it empirically instead: sample real,
non-migrated `GiftCommitment` records and see what fraction already have a
real `GiftCommitmentSchedule`.
Live dogfooding this against `NPC_TARGET_v2` found a real calibration gap
before it found the right answer: this org's broader real `GiftCommitment`
population mixes `Recurring`/`Custom` types together, so only 6 of 10
sampled real records showed a real schedule (60%) — below the tool's
original 80% default threshold, which missed this exact relationship on
the first live run (it caught a different real one instead,
`GiftCommitmentSchedule -> GiftTransaction`, 100%). Recalibrated the
default to 50% based on this real evidence; re-running the same live
command now correctly flags `GiftCommitment -> GiftCommitmentSchedule` at
60% — confirmed directly, not assumed. See `ROADMAP.md` #79 for the full
account.

**CORRECTION (2026-07-19):** this "always auto-creates" rule does not
hold universally. A later session's NPC fundraising/donor-management
Snowfakery dogfood build inserted 12 fresh Recurring-type
`GiftCommitment` records into the same org and got ZERO auto-created
schedules -- verified from both directions, confirmed stable over an
extended period (not an async delay), and confirmed that updating an
already-inserted commitment's fields afterward does not retroactively
trigger it. The root platform cause remains genuinely unclear (still a
Tooling-API-invisible blind spot) -- a plausible but unconfirmed guess is
a Bulk-API-2.0-vs-UI-single-record-insert context difference. **The safe
pattern going forward is defensive, not predictive:** after inserting a
`GiftCommitment`, replicate `GiftCommitmentSchedule` for its Id and check
what's actually there before deciding whether an explicit insert is
needed -- never assume "always" or "never" from a prior session's
finding, even a well-confirmed one like this one originally was. See
[validators/GiftCommitmentSchedule.md](../../validators/GiftCommitmentSchedule.md)'s
own correction entry and
`sql/transformations/370_giftcommitmentschedule_load.sql` for the
corrected implementation.

# Citations

1. Live-confirmed, 2026-07-18, `NPC_TARGET_v2` -- not documented in the
   migration guide's own Appendix B validation tables (see
   `okf/nonprofit-cloud/gift-commitment-schedule-validations.md`,
   `gift-commitment-validations.md`) as of this writing.
2. Correction live-confirmed, 2026-07-19, same org -- see the correction
   note above.
