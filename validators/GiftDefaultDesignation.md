---
type: ObjectValidator
title: GiftDefaultDesignation validator
description: Object-specific findings for GiftDefaultDesignation
  (Nonprofit Cloud/AFNP) -- the platform auto-creates a 100% default
  designation the instant a GiftCommitment is inserted; never insert or
  update this object.
tags: [object-validator, gift-default-designation, nonprofit-cloud, afnp, gift-commitment, auto-created-child-record]
timestamp: "2026-07-21"
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
default `GiftDesignation` (the same org-wide default noted in
[GiftDesignation.md](GiftDesignation.md)'s own `IsDefault` finding). The
platform creates this the instant `GiftCommitment` is inserted -- same
auto-creation family as [AccountContactRelation](AccountContactRelation.md)
and [GiftCommitmentSchedule](GiftCommitmentSchedule.md). This build's own
explicit insert pushed the real total to 200%, rejected outright by the
platform's own rollup validation. All 15 inserts failed cleanly (0
succeeded), so no partial-success cleanup was needed.

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
