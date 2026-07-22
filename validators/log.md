# Validators bundle update log

## 2026-07-21
* **New**: [GiftDefaultDesignation validator](GiftDefaultDesignation.md)
  -- the platform auto-creates a 100% default designation the instant a
  GiftCommitment is inserted; an explicit insert collided
  (FIELD_INTEGRITY_EXCEPTION, "Designations can't exceed 100%"), 15 of
  15 failed cleanly. Never insert or update this object. Found during
  the second NPC fundraising dogfood rebuild attempt
  (`attempts/2026-07-21-npc-dogfood-v2/`).
* **Update (correction)**: [AccountContactRelation validator](AccountContactRelation.md)
  -- the first build's own fix (replicate + update IsIncludedInGroup/
  IsPrimaryMember) was itself wrong, caught directly by the user: no
  auto-created record should be updated, not even for a seemingly
  necessary field. Real, IsDirect=true-filtered evidence (5 of 5) shows
  these fields stay False/False -- the earlier "10/10 populated, mixed
  True/False" finding was contaminated by an unfiltered sample that
  picked up unrelated business-relationship rows. Reverted the 19 real
  rows this rebuild had already updated back to False/False.
* **Update**: [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md)
  -- the documented "Manage Recurring Gift Commitment Schedule" Invocable
  Action was tried for real this pass (not just researched) and worked
  cleanly for all 12 Recurring-type commitments, zero collisions -- see
  `okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md`'s own
  update for the full account, including the one-record-per-call
  constraint found live.
* **Methodology note**: this pass surfaced a general principle worth
  stating once, not per-object: never insert OR update a platform
  auto-created record unless real, filtered reference-data evidence
  (not a broad/unfiltered sample) shows a human genuinely needs to
  change something on it. See
  [okf/nonprofit-cloud/never-update-auto-created-records.md](../okf/nonprofit-cloud/never-update-auto-created-records.md).

## 2026-07-20
* **New**: [GiftDesignation validator](GiftDesignation.md) -- can't
  delete an active GiftDesignation, found purging every migrated record
  from `NPC_TARGET_v2` to reset the org before a fresh rebuild attempt.
* **Update**: [AccountContactRelation validator](AccountContactRelation.md)
  -- a "direct" relationship (IsDirect=true) can't be deleted
  independently; delete the owning Contact instead. Found during the
  same purge.
* **New OKF doc**: [okf/nonprofit-cloud/full-org-reset-between-build-attempts.md](../okf/nonprofit-cloud/full-org-reset-between-build-attempts.md)
  -- the full reverse-dependency delete sequence for the NPC fundraising
  object family, both quirks above, and the relationship-traced deletion
  technique for AccountContactRelation (no migration key of its own).

## 2026-07-19 (6)
* **Update**: [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md),
  [okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md](../okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md)
  -- the real mechanism found: official docs confirm a "Manage Recurring
  Gift Commitment Schedule" Invocable Action (not fired by a plain Bulk
  API insert) and a real nightly "NextGen commitment processing job"
  batch. A human Nonprofit Cloud architect confirmed live: a schedule
  does get created for a "regular" recurring type (e.g. Monthly);
  "irregular" pledge-type commitments don't, or only get the first
  covered. Narrows the earlier same-day correction ("sometimes,
  unexplained") to a real, meaningful distinction plus a likely timing
  artifact, not platform inconsistency. Exact mechanical trigger still
  open. Also now commented directly in `sql/transformations/360`/`370`.

## 2026-07-19 (5)
* **New**: [GiftTransactionDesignation validator](GiftTransactionDesignation.md)
  -- a split allocation's two Amounts must sum to an exact remainder
  (not two independently-rounded percentages, which can overshoot by a
  cent); Amount also appears to lock once the parent transaction reaches
  a certain state, matching the same pattern already found on
  GiftCommitment/GiftTransaction, but left unresolved this pass (1 of 60
  rows, a known accepted gap in this practice build).

## 2026-07-19 (4)
* **New**: [GiftRefund validator](GiftRefund.md) -- three real
  constraints tying a refund to its parent GiftTransaction (must be
  Paid, Amount <= OriginalAmount, Date >= TransactionDate); also where a
  real pyodbc fast_executemany bug in `_writeback_inplace()` was found
  and fixed (long, variable-length error messages truncating and
  crashing the writeback -- now one execute() per row).
* **New**: [GiftSoftCredit validator](GiftSoftCredit.md) -- RecipientId
  is an Account not a Contact (confirmed live); PartialAmount/
  PartialPercent are mutually exclusive.
* **Update**: [GiftTransaction validator](GiftTransaction.md) -- two new
  findings: TransactionDueDate required + must not precede its linked
  schedule's StartDate; a Custom-type schedule allows only ONE linked
  transaction (with a real Bulk-API-batch race letting more than one
  briefly succeed), clearing the link afterward needs the `#N/A`
  sentinel and is blocked entirely once Status leaves Unpaid/Pending.

## 2026-07-19 (3)
* **Correction**: [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md),
  [okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md](../okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md)
  -- the "Recurring-type GiftCommitment always auto-creates its own
  schedule" finding (confirmed 3/3 and 6/6 in two earlier sessions) does
  NOT hold universally. This session's NPC dogfood build inserted 12
  fresh Recurring-type commitments and got zero auto-created schedules,
  verified multiple ways. Root platform cause still unclear (Tooling-API-
  invisible). Corrected guidance: check what's actually missing (replicate
  + LEFT JOIN) before deciding whether to insert, rather than assuming
  either "always" or "never" from a prior finding.

## 2026-07-19 (2)
* **New**: [Contact Point (Address/Phone/Email) validator](ContactPointAddress.md)
  -- covers all three Contact Point objects together (they share the
  same real shape/scoping questions). ParentId is polymorphic Account/
  Individual, scoped to Account only; real ContactPointAddress data is
  much sparser than describe() suggests (Street/PostalCode/AddressType
  etc. essentially unpopulated in a real 3-record sample); boolean
  fields can silently break bulk_op()'s default fingerprint matching,
  same root cause as the AccountContactRelation finding below.

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
