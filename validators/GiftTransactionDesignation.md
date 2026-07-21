---
type: ObjectValidator
title: GiftTransactionDesignation validator
description: Object-specific findings for GiftTransactionDesignation
  (Nonprofit Cloud/AFNP) -- a split allocation's amounts must be computed
  as an exact remainder, not two independently-rounded shares, and
  Amount appears locked once the parent transaction reaches a certain
  state, matching the same "field locked after Status change" pattern
  already found on GiftCommitment/GiftTransaction.
tags: [object-validator, gift-transaction-designation, nonprofit-cloud, afnp, gift-transaction]
timestamp: "2026-07-19"
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
