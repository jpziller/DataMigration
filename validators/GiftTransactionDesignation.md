---
type: ObjectValidator
title: GiftTransactionDesignation validator
description: Object-specific findings for GiftTransactionDesignation
  (Nonprofit Cloud/AFNP) -- a split allocation's amounts must be computed
  as an exact remainder, not two independently-rounded shares. A second,
  separate insert-time failure on a standalone (no GiftCommitmentId),
  fully-refunded transaction remains genuinely unresolved -- refund
  status and rounding have both been ruled out as the sole cause; sample
  size (n=1) is too small to confirm standalone-vs-commitment-linked as
  the real differentiator.
tags: [object-validator, gift-transaction-designation, nonprofit-cloud, afnp, gift-transaction]
timestamp: "2026-07-21"
---
# GiftTransactionDesignation validator

## A split's two Amounts must sum to exactly the transaction's OriginalAmount
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build -- 1 of 60 generated rows (a 60/40 split across two
designations) failed `FIELD_INTEGRITY_EXCEPTION: "Adjust the designations
so that the total designation amount doesn't exceed the transaction
amount."` Root cause: computing each share independently as
`ROUND(pct * OriginalAmount, 2)` can round BOTH shares up on an odd-cent
amount, overshooting the true total by a cent.
**What to do:** compute the primary share as a real rounded value, and
the secondary share as the exact remainder (`OriginalAmount -
PrimaryAmount`), never as its own independently-rounded percentage --
the two always sum to exactly the original amount this way. See
`sql/transformations/430_gifttransactiondesignation_load.sql`.

## Amount may be locked once the parent GiftTransaction reaches a certain state -- unresolved
**Found:** same session, while correcting the one already-failed row
above. The first (pre-fix) load already created a `P38` row with the old,
unrounded `Amount` (7405.518); once the fix computed a clean 7405.52/
4937.01 split, the plan was to correct `P38`'s `Amount` via a plain
`update` (not touching the non-updateable `GiftTransactionId`) and then
insert the now-correctly-summing `S38`. **The `update` itself failed**
with the identical `FIELD_INTEGRITY_EXCEPTION`, even though 7405.52 alone
is well under the transaction's 12342.53 total and no sibling `S38` row
existed yet to conflict with. This strongly resembles the same "field
locked after Status change" pattern already confirmed for
`GiftCommitment.CurrentGiftCmtScheduleId` and
`GiftTransaction.GiftCommitmentScheduleId` (both in
[GiftCommitmentSchedule.md](GiftCommitmentSchedule.md)/
[GiftTransaction.md](GiftTransaction.md)) -- but this specific instance
was not chased to a confirmed root cause or a working fix; the
delete-and-reinsert pattern that resolved the other two cases was not
attempted here. **Left as a known, accepted gap** in this practice
build -- 59 of 60 GiftTransactionDesignation rows loaded correctly (1
transaction, LoadId 38, has only its 60% primary allocation, no 40%
secondary). A real client engagement hitting this should try the same
delete-and-reinsert approach documented for the other two cases before
assuming it's a different root cause.

## SECOND, SEPARATE occurrence (2026-07-21) -- corrects the "locked after Status change" theory above, still unresolved
**Found:** second NPC fundraising dogfood rebuild attempt, a completely
fresh insert this time (not a follow-up correction like LoadId 38
above) -- `P9`, a standalone (no split, no `S9` counterpart) 100%
designation, failed on its very first insert attempt with the identical
`FIELD_INTEGRITY_EXCEPTION: "Adjust the designations so that the total
designation amount doesn't exceed the transaction amount."` This alone
already narrows the picture: since this was a first-ever insert, not an
update against an already-loaded row, the original "field locked after
Status change" theory (which specifically explains why an *update*
would fail) doesn't fit this occurrence -- something about this specific
transaction rejects a fresh insert outright.

**Investigated live, two hypotheses tested and ruled out:**
1. **Rounding/precision mismatch** -- checked the sent `Amount` against
   the org's live `OriginalAmount` at 10 decimal places: both exactly
   `78364.8000000000`. Not a rounding issue this time (unlike LoadId 38
   above, which genuinely was one).
2. **Fully-refunded transactions can't accept a 100% designation** -- the
   failed transaction is `IsFullyRefunded = true`
   (`RefundedAmount = OriginalAmount = 78364.8`). But this build's
   *other* refunded transaction (`P30`/`S30`, a 60/40 split) is **also**
   `IsFullyRefunded = true` with `RefundedAmount` exactly equal to its
   own `OriginalAmount` too -- and it succeeded cleanly. Refund status
   alone does not explain the difference.

**The one real, remaining difference found:** the failed transaction
(`P9`) is **standalone** -- `GiftCommitmentId` is blank. The succeeded
one (`P30`) is **commitment-linked** (`GiftCommitmentId`/
`GiftCommitmentScheduleId` both populated). No pre-existing/auto-created
`GiftTransactionDesignation` row was found on the failed transaction
either (queried directly, zero rows), ruling out an auto-created-row
collision the same family as
[AccountContactRelation](AccountContactRelation.md)/
[GiftDefaultDesignation](GiftDefaultDesignation.md).

**Why this is not being chased further right now:** this build only
produced 2 refunded transactions total -- one of each shape (standalone
vs. commitment-linked). "Standalone + fully-refunded fails, commitment-
linked + fully-refunded succeeds" is an n=1-vs-n=1 comparison, not a
confirmed rule -- a real, concrete lead, not proven causation.
Confirming it needs one of: (a) a real migration with enough refunded,
standalone transactions to test the pattern at real scale, (b) more
real, human-created reference data in `NPC_TARGET_v2` covering this
combination (a task for Ali, not something this framework can generate
meaningfully), or (c) official Nonprofit Cloud documentation on how
refunds interact with designation validation, not yet found. Per this
project's own "test and ask questions, don't brute-force" principle,
guessing further from a 2-example sample isn't worth it -- this stays a
documented, open gap until one of those three becomes available.
**What to do in the meantime:** treat "standalone + fully-refunded"
GiftTransactionDesignation inserts as a known risk; a real client
engagement hitting this should check `GiftCommitmentId`/refund status
before assuming the earlier rounding-based explanation applies.
