---
type: MigrationPattern
title: Allocation's Opportunity-level granularity vs. Gift Transaction Designation's per-transaction granularity (AFNP)
description: NPSP's Allocation splits one Opportunity's total gift across
  GAUs, but AFNP's Gift Transaction Designation attaches to a single Gift
  Transaction -- when an Opportunity fans out into more than one Gift
  Transaction (the multi-Payment routing branch), a single Allocation has
  no one correct Gift Transaction to attach to.
tags: [npsp, npc, afnp, allocation, gift-transaction-designation, gau, migration-pattern, routing]
timestamp: "2026-07-17"
---
# Allocation vs. Gift Transaction Designation granularity mismatch (AFNP)

Confirmed live during a real NPSP-to-NPC migration proof-of-concept, not
theorized in advance: NPSP's `Allocation` object splits one
`Opportunity`'s total gift amount across one or more General Accounting
Units (GAUs) — it's fundamentally **Opportunity-level**. AFNP's
`GiftTransactionDesignation` (migration guide sec 7.6.12 "Create Gift
Transaction Designations") is fundamentally **Gift-Transaction-level**:
`GiftTransactionId` is a single lookup, one designation row always
attaches to exactly one transaction.

These granularities only actually collide when an Opportunity's own
[three-way routing](opportunity-routing.md) sends it down the
multi-Payment branch — more than one real Payment means the Opportunity
becomes a Gift Commitment, and each of its Payments becomes its own,
separate Gift Transaction. An Allocation against that Opportunity now has
**no single correct Gift Transaction** to attach its designation to; the
split it represents was always meant at the whole-gift level, not any
one installment.

## The pattern, confirmed with real numbers

A seeded proof-of-concept Opportunity with 3 equal $500 Payments (routed
to 3 separate Gift Transactions) had 2 Allocations against it: $1,000 to
one GAU, $500 to another. Neither Allocation maps to exactly one of the 3
Gift Transactions.

**Approach taken**: split each such Allocation proportionally across
every Payment-level Gift Transaction under its Opportunity, weighted by
that Payment's own share of the Opportunity's total `Amount`:

```
DesignationAmount = Allocation.Amount * (Payment.Amount / Opportunity.Amount)
```

For the 3 equal $500 payments above, the $1,000 Allocation becomes 3
Gift Transaction Designation rows of $333.33 each; the $500 Allocation
becomes 3 rows of $166.67 each — 2 Allocations become 6 designation rows,
and the split amounts sum back exactly to the original totals (verified:
$1,000 + $500 = $1,500, matching the Opportunity's own `Amount`).
`GiftTransactionDesignation` also requires `Percent` alongside `Amount`
(a real cross-field `INVALID_INPUT` validation, confirmed live, not
documented in the Appendix B tables reviewed for
[the platform validations](gift-transaction-validations.md)) — computed
against each row's own Gift Transaction's amount so a plain 1:1
Allocation always lands at exactly 100%.

Allocations against an Opportunity with **zero or one** real Payment
(the single-Payment routing branch) need no splitting at all — a plain
1:1 join to that Opportunity's own single Gift Transaction.

## Why this is a real, recurring pattern, not just this proof-of-concept's problem

This will hit **every** real NPSP-to-AFNP engagement whose source data
has both (a) Allocations in real use, and (b) Opportunities with more
than one Payment — a very common combination for any nonprofit tracking
fund-level attribution on installment or multi-payment gifts. It is not
addressed explicitly anywhere in the official migration guide's own
Opportunity/Payment/Allocation sheets reviewed so far (see
[the field-mapping workbook notes](npsp-to-afnp-field-mapping.md)) — the
guide's own sequence lists "Create Gift Transaction Designations" as
step 7.6.12 without addressing this specific granularity mismatch.

The proportional-split approach above is a defensible default, not
necessarily the *only* correct one — a real client engagement should
confirm this choice explicitly rather than assume it (e.g. a client might
instead want the full Allocation amount attached to only the *first*
Payment's Gift Transaction, if their own reporting treats a multi-payment
gift's fund designation as a single upfront commitment rather than a
per-installment split).

# Citations

1. Migration guide sec 7.6.12 "Create Gift Transaction Designations" (see
   [migration-guide.md](migration-guide.md))
2. [Opportunity routing](opportunity-routing.md) -- the routing rule that
   creates the underlying granularity mismatch
