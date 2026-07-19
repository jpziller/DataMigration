# Validators bundle update log

## 2026-07-19
* **Update**: [AccountContactRelation validator](AccountContactRelation.md)
  -- three new findings from the NPC fundraising/donor-management
  Snowfakery dogfood build: the platform auto-creates this row itself on
  Contact insert (never insert explicitly, always update -- the same
  auto-creation pattern already known for GiftCommitmentSchedule); a
  boolean field's Salesforce-reformatted echo can silently break
  `bulk_op()`'s default fingerprint match (`--fingerprint-columns Id`
  fixes it) and, found along the way, a real bug in `bulk_op()`'s own
  in-place writeback that destructively nulled a caller-supplied real Id
  on a failed match (fixed in `bulkops.py`, `_writeback_inplace()` now
  `COALESCE`s instead of overwriting); and Bulk API 2.0 needs the literal
  `#N/A` in a CSV cell to null a field on update, not a blank cell.

## 2026-07-18 (4)
* **Update**: [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md)
  -- "Executable check: none yet" replaced with a real one. New
  `child_record_risk.py`, run by default from `analyze-org-risk`, detects
  this exact auto-generation pattern by diffing real reference data
  instead of introspecting metadata the Tooling API can't see. See
  `ROADMAP.md` #79.

## 2026-07-18 (3)
* **New**: [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md) --
  never explicitly insert a schedule for a Recurring-type parent
  GiftCommitment; Nonprofit Cloud auto-creates one and rejects a second
  explicit insert. Found while fixing the GiftCommitmentScheduleId gap
  below -- 3 of 4 RD-derived schedule inserts had actually failed live all
  along, unnoticed until now.

## 2026-07-18 (2)
* **New**: [AccountContactRelation validator](AccountContactRelation.md) --
  IsIncludedInGroup/IsPrimaryMember are the real household-membership
  signal a migration must set. Found via a second architect's live review
  of the migrated `NPC_TARGET_v2` org, diagnosed using `sample-reference-records`
  against real, non-migrated reference data per their explicit instruction.
* **Correction**: [GiftTransaction validator](GiftTransaction.md),
  [PartyRelationshipGroup validator](PartyRelationshipGroup.md) -- the
  same review found `GiftTransaction.GiftCommitmentScheduleId` was never
  populated (fixed for the Recurring-Donation branch only, gated by the
  Single-Transaction-for-Custom-Schedule rule), and
  `PartyRelationshipGroup.Category` was being invented on every record when
  real reference data leaves it unset 0/10 times (now left unset).

## 2026-07-18
* **Correction**: [GiftCommitment validator](GiftCommitment.md),
  [GiftTransaction validator](GiftTransaction.md),
  [PartyRelationshipGroup validator](PartyRelationshipGroup.md) --
  the 2026-07-17 entries below mischaracterized this finding as a
  `describe()`/API mismatch (`createable: False` on a genuinely required
  `Name` field). Re-verified live while planning a pre-flight-check
  enhancement for that supposed mismatch: the real flags are
  `createable: True, nillable: False, defaultedOnCreate: False` -- an
  ordinary required field. `bulk_op()`'s pre-flight check already warned
  correctly before each failure; the real mistake was proceeding past the
  warning, not a tooling gap. All three docs corrected in place.

## 2026-07-17
* **New**: [GiftCommitment validator](GiftCommitment.md),
  [GiftTransaction validator](GiftTransaction.md),
  [PartyRelationshipGroup validator](PartyRelationshipGroup.md) --
  Nonprofit Cloud/AFNP's fundraising object family, discovered during a
  live NPSP-to-NPC migration proof-of-concept. Same root finding hit
  three separate objects independently: `Name` reports
  `createable: False` in `describe()` but is genuinely required and
  acceptable to send on insert -- confirmed a real describe()/API
  mismatch, not a fluke, once it recurred a third time.

## 2026-07-15
* **Update**: Adopted the Open Knowledge Format (OKF v0.1) — frontmatter
  added to every concept file (no body content changed), this log and
  [index.md](index.md) created. See ROADMAP.md #72.

## 2026-07-13
* **Update**: [Task validator](Task.md) — added the
  discovery-checklist polymorphic-collapse note (a Task WhatId finding
  that surfaced a real bug in `discovery_checklist.py`'s
  out-of-scope-dependency check).

## 2026-07-11
* **Initialization**: Created the bundle — [README.md](README.md),
  [Task validator](Task.md), and the four system validators formalizing
  Hard Rules 6, 7, 12, and 15.
