---
type: ObjectValidator
title: GiftCommitmentSchedule validator
description: Object-specific findings for GiftCommitmentSchedule
  (Nonprofit Cloud/AFNP) -- Recurring-type parent GiftCommitments
  SOMETIMES get an auto-created schedule from the platform itself
  (confirmed both ways live, in two different sessions); check what's
  actually missing before inserting rather than assuming either way.
tags: [object-validator, gift-commitment-schedule, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-19"
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
**Executable check:** built 2026-07-18 -- `analyze-org-risk` now runs
`child_record_risk.py`'s auto-generated-child-record check by default,
which empirically diffs real reference data since this behavior isn't
visible via the Tooling API. See the OKF finding's own note on this and
`ROADMAP.md` #79.

## CORRECTION (2026-07-19): the auto-creation is not reliably reproducible -- check what's missing, don't assume either way
**Found:** NPC fundraising/donor-management Snowfakery dogfood build,
same session as the [ContactContactRelation](ContactContactRelation.md)/
[AccountContactRelation](AccountContactRelation.md) findings. This
build's own 12 Recurring-type `GiftCommitment` inserts got ZERO
auto-created schedules -- the exact opposite of the 3/3 confirmed above.
Verified from both directions (`GiftCommitment.CurrentGiftCmtScheduleId`
and a direct `GiftCommitmentSchedule` query), confirmed stable over an
extended period (not an async-processing delay), and confirmed that
updating an already-inserted commitment's fields afterward does NOT
retroactively trigger it (deleted and reinserted 12 real records to test
this cleanly). Compared field-by-field against the one real working
example from the earlier PoC's own data and found no reproducible
trigger condition (tried matching its blank `ExpectedEndDate` -- no
effect).
**Why:** genuinely unclear. The Tooling API can't see managed-package-
internal Flow/automation logic (the same structural blind spot
`child_record_risk.py` already exists to work around empirically, not by
introspection) -- a plausible but unconfirmed guess is a Bulk-API-2.0-
vs-UI-single-record-insert context difference in which automation
contexts fire, but this wasn't isolated with confidence.
**What to do now:** never assume either "always auto-creates" or "never
auto-creates" as a fixed rule. After the parent `GiftCommitment` insert,
replicate `GiftCommitmentSchedule` for this migration's own
`GiftCommitmentId`s FIRST, then build the explicit-insert Load table
only for commitments that genuinely have no real schedule yet
(`LEFT OUTER JOIN` against the replicated table, `WHERE existing.Id IS
NULL`) -- safe under either platform behavior, never collides with a
real auto-created row. See
`sql/transformations/370_giftcommitmentschedule_load.sql` for the
corrected pattern. A Recurring-type commitment that needs an explicit
schedule this way has no real source recurrence period to map from (this
build's own Snowfakery data) -- 'Monthly' was used as the most common
real-world cadence, a reasonable default rather than evidenced fact.
**Executable check:** the existing `child_record_risk.py` check still
correctly flags this object as having auto-generation risk (a real
non-1:1 relationship rate would still show up) -- but it can't
distinguish "always," "sometimes," or "never" from one snapshot,
consistent with everything else found this session.
