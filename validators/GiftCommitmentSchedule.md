---
type: ObjectValidator
title: GiftCommitmentSchedule validator
description: Object-specific findings for GiftCommitmentSchedule
  (Nonprofit Cloud/AFNP) -- Recurring-type parent GiftCommitments get an
  auto-created schedule from the platform itself; an explicit insert for
  one collides with it.
tags: [object-validator, gift-commitment-schedule, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-18"
---
# GiftCommitmentSchedule validator

## Never explicitly insert a schedule for a Recurring-type GiftCommitment
**Found:** 2026-07-18 -- 3 of 4 Recurring-Donation-derived
`GiftCommitmentSchedule` inserts failed live with
`FIELD_INTEGRITY_EXCEPTION: ...doesn't overlap with an existing schedule`,
silently recorded in the Load table's own `Error` column and never
investigated until a second architect's live review traced a downstream
`GiftTransaction`'s missing `GiftCommitmentScheduleId` back to it.
**Why:** Nonprofit Cloud auto-creates a `GiftCommitmentSchedule` itself the
moment a `GiftCommitment` is inserted with `ScheduleType = 'Recurring'` --
confirmed live on 6 of 6 real records in this org (3 auto-created for
Recurring commitments, 3 explicitly inserted by this migration for Custom
ones, zero exceptions). See
`okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md` for the
full evidence table.
**What to do:** only build an explicit `GiftCommitmentSchedule` insert row
for a `Custom`-type parent commitment
(`sql/transformations/170_npc_giftcommitmentschedule_from_rd_load.sql`'s
own `WHERE` clause). For a `Recurring`-type commitment, replicate
`GiftCommitmentSchedule` from the target org after the parent
`GiftCommitment` insert has run, and join downstream consumers (e.g.
`GiftTransaction.GiftCommitmentScheduleId`) by the real `GiftCommitmentId`
relationship instead of any local Load table bookkeeping.
**Executable check:** none yet -- see the OKF finding's own note on this.
