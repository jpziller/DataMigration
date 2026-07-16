---
type: MigrationPattern
title: Opportunity routes to Gift Transaction, Gift Commitment, or Opportunity (AFNP)
description: A single NPSP Opportunity migrates to exactly one of three
  different AFNP objects, chosen by a real conditional rule based on its
  Payment count and open/closed status -- not a fixed 1:1 object mapping.
tags: [npsp, npc, afnp, opportunity, gift-transaction, gift-commitment, migration-pattern, routing]
timestamp: "2026-07-16"
---
# Opportunity routes to Gift Transaction, Gift Commitment, or Opportunity (AFNP)

NPSP's `Opportunity` (donations, tracked via the NPSP Payment object for
installments) doesn't map to one AFNP object -- it fans out to three,
selected per-record by a real rule (guide §7.6.3-7.6.5, confirmed
against the field-mapping workbook's own Opportunity sheet and Notes):

| NPSP Opportunity has... | Migrates to |
|---|---|
| Zero or one Payment | **Gift Transaction** (a single completed/pending gift) |
| More than one Payment | **Gift Commitment** (+ a Gift Commitment Schedule for the installments) |
| Open stage (`IsClosed = false`) | Stays an **Opportunity** (still in progress, not yet a realized gift) |

The guide's own migration sequence loads these in dependency order:
Gift Commitments from Opportunities (§7.6.4) *before* Gift Transactions
from Opportunities (§7.6.5) -- a Gift Transaction against an
installment plan needs its Gift Commitment to already exist. Separately,
NPSP's standalone `Payment` object (installments/receipts against an
Opportunity) has its own routing: fans out to **Payment Instrument**,
**Gift Transaction**, and **Gift Refund**, with Gift Transactions loaded
before Gift Refunds since a Refund is a child record of the Transaction
it reverses (guide §7.6.6-7.6.7; workbook Payment sheet note).

This is the single most structurally complex mapping in the whole
migration -- see [npsp-to-afnp-field-mapping.md](npsp-to-afnp-field-mapping.md)
for the field-mapping workbook's own worked-example version of this same
routing rule, and the three
[Fundraising Validations](gift-transaction-validations.md) files for
what the target objects then enforce once records land in them.

# Citations

1. Migration guide §7.6.2-7.6.7 "Migrate Gifts (Opportunities and
   Payments)" (see [migration-guide.md](migration-guide.md))
2. NPSP to AFNP field mapping workbook, `Opportunity` and `Payment`
   sheets (see [npsp-to-afnp-field-mapping.md](npsp-to-afnp-field-mapping.md))
