---
type: PlatformFinding
title: GiftRefund/GiftSoftCredit/GiftTransactionDesignation -- real validation rules found live
description: Real platform-enforced validation rules on GiftRefund,
  GiftSoftCredit, and GiftTransactionDesignation, found live during the
  NPC fundraising/donor-management Snowfakery dogfood build -- these
  three objects are not covered by the migration guide's own extracted
  Appendix B validation tables (Gift Transaction/Gift Commitment/Gift
  Commitment Schedule only).
tags: [npc, afnp, gift-refund, gift-soft-credit, gift-transaction-designation, validation, platform-finding, fundraising]
timestamp: "2026-07-19"
---
# GiftRefund/GiftSoftCredit/GiftTransactionDesignation -- real validation rules found live

**Scope note:** unlike `gift-transaction-validations.md`/
`gift-commitment-validations.md`/`gift-commitment-schedule-validations.md`,
this doc's rules were NOT extracted from the migration guide's Appendix
B — that appendix only tables Gift Transaction, Gift Commitment, and
Gift Commitment Schedule. These three objects' constraints were found
empirically, via real `FIELD_INTEGRITY_EXCEPTION`/`INVALID_INPUT`
failures during a real load (2026-07-19, `NPC_TARGET_v2`).

## GiftRefund
Three independent constraints tying a refund to its parent
`GiftTransaction`:
1. The parent transaction's `Status` must already be `'Paid'` —
   `"Select a gift transaction that's already paid."`
2. `Amount` must not exceed the parent's own `OriginalAmount` —
   `"Enter an amount for refund that's less than or equal to the current
   amount of the gift transaction."`
3. `Date` must be on or after the parent's own `TransactionDate` (its
   completion date) — `"Enter a date for refund that's on or after the
   Transaction Completion Date."`

## GiftSoftCredit
`PartialAmount` and `PartialPercent` are mutually exclusive —
`"Enter a value only in the Partial Amount field or the Partial Percent
field."` Send exactly one, never both.

## GiftTransactionDesignation
`Percent` is required alongside `Amount` (already known from the
earlier NPSP-to-NPC proof-of-concept, confirmed again here). Less
obvious: when a single `GiftTransaction` is split across more than one
`GiftDesignation`, the individual rows' `Amount`s must sum to no more
than the transaction's own `OriginalAmount` —
`"Adjust the designations so that the total designation amount doesn't
exceed the transaction amount."` A naive implementation that rounds each
share's percentage independently (e.g. 60% and 40% each rounded to 2
decimals separately) can overshoot the true total by a cent on an
odd-cent amount and trip this rule. Compute one share as a real rounded
value and every other share as the exact remainder instead.

`Amount` also appears to become locked on this object once the parent
transaction reaches a certain state, matching the same "field locked
after Status change" pattern confirmed for `GiftTransaction.
GiftCommitmentScheduleId` — but this was not chased to a confirmed root
cause or a working fix in the session that found it (1 real row was left
without its correction). See
`validators/GiftTransactionDesignation.md` for the open account.

# Citations

1. Live-confirmed, 2026-07-19, `NPC_TARGET_v2`. Not present in the
   migration guide's own Appendix B validation tables as of this
   writing.
