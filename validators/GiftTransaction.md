---
type: ObjectValidator
title: GiftTransaction validator
description: Object-specific findings for GiftTransaction (Nonprofit
  Cloud/AFNP) -- Name is a genuinely required field with no default, same
  pattern as GiftCommitment/PartyRelationshipGroup; GiftCommitmentScheduleId
  must also be populated where a schedule exists, but only when doing so
  doesn't violate the Single-Transaction-for-Custom-Schedule rule.
tags: [object-validator, gift-transaction, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-18"
---
# GiftTransaction validator

## Name is a genuinely required field with no default
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept -- omitted
initially, real Bulk API call failed with `REQUIRED_FIELD_MISSING:
Required fields are missing: [Name]`.
**Correction (2026-07-18):** see [GiftCommitment](GiftCommitment.md)'s
own corrected write-up -- this is an ordinary required field
(`createable: True, nillable: False, defaultedOnCreate: False`), not a
`describe()`/API mismatch as originally (incorrectly) claimed here.
`bulk_op()`'s pre-flight check already warned about this correctly
before the failure; the mistake was proceeding past the warning.
**What to do:** always send a real `Name` value. This migration reused
the source Opportunity's/Payment's own `Name`.

## GiftCommitmentId links a Gift Transaction back to its originating Gift Commitment
**Found/confirmed:** 2026-07-17 -- not a gotcha, a design note worth
recording since it's easy to assume a Gift Transaction always stands
alone. Every Gift Transaction created from an installment of a Recurring
Donation or a multi-Payment Opportunity should carry `GiftCommitmentId`
pointing at the Gift Commitment created from that same parent -- verified
live (a Recurring-Donation-linked Opportunity's migrated Gift Transaction
correctly carried the real `GiftCommitmentId` of the Gift Commitment
built from its parent Recurring Donation). See
`okf/npsp-to-npc/opportunity-routing.md` for the full three-way routing
rule this is part of.

## GiftCommitmentScheduleId was missing entirely -- a real gap, not by design
**Found:** 2026-07-18, a second architect reviewing the live
`NPC_TARGET_v2` org flagged a specific migrated record
(`GiftTransaction 6trfn000000rknwAAA`, the Recurring-Donation-linked
Opportunity #1's transaction) as disconnected from its
`GiftCommitmentSchedule`, even though a real schedule for that same RD was
already built in step 170. Confirmed live via direct query: every migrated
`GiftTransaction`'s `GiftCommitmentScheduleId` was blank, because neither
`200` nor `210` ever populated it -- this was this migration's own
oversight, not a platform limitation or a deliberate omission.
**What to do:** `200` (the RD-linked Opportunity branch) now joins
`GiftCommitmentSchedule_Load` the same way it already joined
`GiftCommitmentFromRD_Load`, keyed by the RD's own Id.
**Constraint found while fixing this:** AFNP's own Appendix B validation,
"Single Transaction for Custom Schedule" (see
`okf/nonprofit-cloud/gift-transaction-validations.md`), only allows ONE
Gift Transaction per Custom-type Gift Commitment Schedule. `210` (the
multi-Payment-Opportunity branch) builds one Custom schedule per
Opportunity in `190` but fans out to multiple Gift Transactions per
Opportunity (one per real Payment) -- linking all of them to that one
shared schedule would violate this rule live. `210` therefore
deliberately does **not** get the same fix; its Gift Transactions
correctly keep `GiftCommitmentId` (the parent commitment) without a
`GiftCommitmentScheduleId`. A real client engagement wanting a full
schedule link on this branch would need a structurally different design
(e.g. a schedule row per Payment, not per Opportunity) -- out of scope for
this proof-of-concept's fix.
**Also relevant to any corrective reload:** the same doc's "Updating the
Gift Commitment Schedule" rule locks this field once `Status` leaves
`Unpaid`/`Pending` -- our migrated GiftTransactions are already `Paid`, so
a plain `bulkops upsert` cannot patch this onto the already-loaded live
records; a delete-then-reinsert is required instead.
**Executable check:** none yet -- same category as GiftCommitment.md's own
`ScheduleType`/`TransactionPeriod` consistency note.
**Root cause found while fixing this:** 3 of the 4 RD-derived
`GiftCommitmentSchedule` rows never made it into the local Load table at
all -- Nonprofit Cloud auto-creates a schedule for a Recurring-type
commitment, and this project's own explicit insert attempt for those 3
failed live (silently, until now). See
[GiftCommitmentSchedule validator](GiftCommitmentSchedule.md). The fix:
`200` now joins a live-replicated `dbo.GiftCommitmentSchedule` table by the
real `GiftCommitmentId`, not the local Load table's own bookkeeping, so it
finds the schedule regardless of which side (this migration or the
platform) actually created it.
