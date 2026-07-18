# Validators bundle update log

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
