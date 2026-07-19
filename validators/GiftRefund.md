---
type: ObjectValidator
title: GiftRefund validator
description: Object-specific findings for GiftRefund (Nonprofit
  Cloud/AFNP) -- three real Appendix-B-style validation rules tying a
  refund to its parent GiftTransaction's own state.
tags: [object-validator, gift-refund, nonprofit-cloud, afnp, gift-transaction]
timestamp: "2026-07-19"
---
# GiftRefund validator

## Three real constraints tying a refund to its parent GiftTransaction
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build -- a real insert against 25 generated rows failed
`FIELD_INTEGRITY_EXCEPTION` on every row that violated any of three
independent rules:
1. The parent `GiftTransaction.Status` must already be `'Paid'` --
   `"Select a gift transaction that's already paid."`
2. `Amount` must not exceed the parent transaction's own `OriginalAmount`
   -- `"Enter an amount for refund that's less than or equal to the
   current amount of the gift transaction."`
3. `Date` must be on or after the parent transaction's own
   `TransactionDate` (its completion date) -- `"Enter a date for refund
   that's on or after the Transaction Completion Date."`
**Why:** Snowfakery generates every field independently, with no
awareness of the parent object's own values -- the same root cause
already hit on `Campaign.StartDate/EndDate` and
`GiftTransaction.TransactionDueDate`, just spanning two objects here
(child field vs. parent field) instead of two fields on one object.
**What to do:** filter to only parent transactions with `Status = 'Paid'`
(the other statuses are simply not eligible for a refund at all -- don't
try to force a status change instead), and clamp `Amount`/`Date` against
the parent's own `OriginalAmount`/`TransactionDate` rather than trusting
the Mock table's independently-random values. See
`sql/transformations/400_giftrefund_load.sql`.
**Executable check:** none yet -- a pre-load consistency check comparing
a refund's own values against its parent transaction's (both already
known at Load-table-build time) would catch this before the live API
call, same category as GiftCommitment.md's ScheduleType/TransactionPeriod
note.

## Real bug found while fixing this: pyodbc's fast_executemany truncates long, variable-length error writeback
**Found:** same session, while debugging the failures above. `bulk_op()`'s
own in-place writeback (`_writeback_inplace()` in `bulkops.py`) crashed
outright with `String data, right truncation: length 666 buffer 510`
instead of recording the real per-row errors -- pyodbc's
`fast_executemany` (enabled globally in `sql_client.py`) infers a bound
string parameter's buffer size from an early row in a batch UPDATE, then
truncates a later row whose value is longer. Real Salesforce validation
messages vary widely in length (a single-rule failure vs. several rules
failing on one row, as happened here), so this is a real, general risk
for any object's writeback, not specific to GiftRefund. **Fixed** in
`_writeback_inplace()` -- one `execute()` call per row instead of a
single executemany-style call with the whole batch; writeback is a small,
bounded number of rows, so this has no meaningful performance cost.
