---
type: ObjectValidator
title: GiftDefaultDesignation validator
description: Object-specific findings for GiftDefaultDesignation
  (Nonprofit Cloud/AFNP) -- the platform auto-creates a 100% default
  designation on GiftCommitment insert; never insert or update this
  object. Auto-creation correlates with ScheduleType='Recurring' (12/15
  confirmed) -- Custom-type commitments and Campaign never get one, so a
  consumer must replicate + LEFT JOIN, never assume universal coverage.
tags: [object-validator, gift-default-designation, nonprofit-cloud, afnp, gift-commitment, auto-created-child-record]
timestamp: "2026-07-24"
---
# GiftDefaultDesignation validator

## The platform auto-creates a 100% default designation on GiftCommitment insert -- never insert or update
**Found:** 2026-07-21, second NPC fundraising dogfood rebuild attempt.
An explicit insert of one GiftDefaultDesignation per GiftCommitment (15
rows, round-robin across this build's own 6 GiftDesignation_Load rows,
each at 100%) failed 15 of 15 live with:

```
FIELD_INTEGRITY_EXCEPTION: Designations can't exceed 100% on a gift
transaction. Adjust your designations and save again.
```

**Root cause, confirmed live:** querying the org directly for 3 of this
build's own real GiftCommitment Ids each showed exactly one
already-existing GiftDefaultDesignation row -- `AllocatedPercentage =
100`, `GiftDesignationId` pointing at this org's own real, pre-existing
default `GiftDesignation` (`Name = "General fund"`, identifiable
dynamically via `GiftDesignation.IsDefault = true` -- see
[GiftDesignation.md](GiftDesignation.md)'s own `IsDefault` finding,
confirmed 2026-07-24). The platform creates this the instant
`GiftCommitment` is inserted -- same auto-creation family as
[AccountContactRelation](AccountContactRelation.md) and
[GiftCommitmentSchedule](GiftCommitmentSchedule.md). This build's own
explicit insert pushed the real total to 200%, rejected outright by the
platform's own rollup validation. All 15 inserts failed cleanly (0
succeeded), so no partial-success cleanup was needed.

**Update, 2026-07-24:** re-confirmed across all 15 real GiftCommitment
records in the second rebuild attempt (not just the original 3) while
building the corrected GiftTransactionDesignation inheritance logic --
see [GiftTransactionDesignation.md](GiftTransactionDesignation.md). The
auto-creation itself is NOT universal: **12 of 15 (all Recurring-type)
have an auto-created GDD; the 3 Custom-type commitments do not.** Also
confirmed Campaign never gets one at all (0 of 3 real Campaigns checked).
This mirrors the same Recurring-vs-Custom split already known for
GiftCommitmentSchedule auto-creation (see
[GiftCommitmentSchedule.md](GiftCommitmentSchedule.md)) -- strong evidence
both are side effects of the same underlying platform mechanism (the
NextGen commitment processing job / the "Manage Recurring Gift Commitment
Schedule" Invocable Action) rather than two unrelated behaviors. This
doesn't change the rule below (still never insert/update
GiftDefaultDesignation) -- it changes what a *consumer* of this data
(GiftTransactionDesignation's own transform) must check for: replicate
and `LEFT JOIN`, never assume every commitment has one.

**What to do:** never insert AND never update this object -- caught live
by the user directly, generalizing a rule this project had previously
only applied narrowly (don't stamp `MigrationID__c` on an auto-created
`AccountContactRelation` row) into a blanket rule covering every
auto-created record on any object: don't touch it at all unless real
evidence shows a human actually needs to change something on it (see
[AccountContactRelation.md](AccountContactRelation.md)'s own 2026-07-21
correction, which found the opposite -- IsIncludedInGroup/IsPrimaryMember
should also never be updated). The org's real default designation link
is exactly what a human-created commitment gets automatically too; there
is no evidenced reason to believe a human ever repoints it to a
different designation through normal use. Skip building a Load table for
this object entirely.

**Executable check:** the existing `child_record_risk.py` auto-generated-
child-record check (`analyze-org-risk`) should be able to flag this
relationship empirically the same way it already does for
GiftCommitment -> GiftCommitmentSchedule -- not yet re-run against this
specific pairing to confirm the threshold catches it; worth verifying on
a future pass.
