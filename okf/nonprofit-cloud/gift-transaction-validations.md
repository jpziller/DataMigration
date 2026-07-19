---
type: PlatformValidation
title: Gift Transaction validations (AFNP)
description: Official, platform-enforced validation rules on the
  Agentforce Nonprofit Gift Transaction object -- Appendix B of
  Salesforce's migration guide. Not a migration gotcha this framework
  discovered; a documented target-platform business rule.
resource: https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf
tags: [npsp, npc, afnp, gift-transaction, validation, fundraising]
timestamp: "2026-07-18"
---
# Gift Transaction validations (AFNP)

Extracted directly from the migration guide's Appendix B, pages 71-73 --
not summarized or reworded. "Disable with Toggle" means Salesforce
provides an admin-facing switch to turn that specific rule off; where
blank, the rule cannot be disabled.

| Validation | Description | Disable with Toggle |
|---|---|---|
| Original Amount Positive | Validates that the Original Amount is greater than or equal to 0. | |
| Update Original Amount Restricted | Restricts updates to the Original Amount field when the Status is 'Paid'. | Yes* |
| Update Currency ISO Code Restricted | Restricts updates to the Currency ISO Code when the Status is 'Paid' or 'Fully Refunded'. | |
| Update Donor Restricted | Restricts updates to the Donor field when the Status is 'Paid' or 'Fully Refunded'. | Yes |
| Update Transaction Completion Date Restricted | Restricts updates to the Transaction Completion Date when the Status is 'Paid'. | Yes* |
| Transaction Status Final | Prevents invalid Gift Transaction Status changes. | |
| Transaction Completion Date Required | Requires the Transaction Completion Date to be entered when changing the Status to 'Paid' or 'Fully Refunded'. | |
| Updating the Gift Commitment | Restricts editing the Gift Commitment field when the Status is a value other than 'Unpaid' or 'Pending'. | Yes |
| Updating the Gift Commitment Schedule | Restricts editing the Gift Commitment Schedule field when the Status is a value other than 'Unpaid' or 'Pending'. | Yes |
| Transaction Due Date Required | Ensures that the Transaction Due Date is provided and not left blank. | |
| Due Date vs. Schedule Start Date | Ensures the Transaction Due Date is on or after the Gift Commitment Schedule Start Date. | |
| Due Date within Schedule Range | Ensures the Transaction Due Date is between the Start Date and End Date of the Gift Commitment Schedule. | |
| Gift Commitment Schedule Match | Ensures the Gift Commitment Schedule belongs to the associated Gift Commitment. | |
| Single Transaction for Custom Schedule† | Ensures that a Custom Gift Commitment Schedule is only linked to one Gift Transaction. | |
| Campaign and Outreach Source Match† | Validates that the Outreach Source Code is valid for the selected Campaign. | |

\* These can only be disabled if Accounting Subledger is not in use.

† **Attribution uncertain**: these two rules sit exactly at the PDF's
page 73 boundary between the Gift Transaction and Gift Commitment
Validations tables, and the extracted text is ambiguous about which
table they belong to (a two-column-layout extraction artifact, not a
content judgment call). Placed here based on thematic continuity with
the preceding Gift-Commitment-Schedule-matching cluster, but **verify
against the source PDF page 73 directly** before relying on this for a
real transform.

**Practical implication for a future NPSP→AFNP migration**: several of
these rules lock a field once `Status = 'Paid'` (or `'Fully Refunded'`)
-- Original Amount, Currency, Donor, Transaction Completion Date, the
Gift Commitment/Gift Commitment Schedule lookups. A migration loading
historical Paid transactions must get these fields right on **insert**,
since a post-load correction pass can't touch them without first
disabling the toggle-able ones (and the two marked `Yes*` need
Accounting Subledger confirmed off first). **Confirmed live** (this
framework's own NPSP-to-NPC proof-of-concept, 2026-07-18): a migration
that forgets `GiftCommitmentScheduleId` on insert and only notices later
cannot fix it with a plain `bulkops upsert` once the transaction is
already `Paid` -- "Updating the Gift Commitment Schedule" locks it. The
correction needed a delete-then-reinsert, not an in-place update.

**"Single Transaction for Custom Schedule" in a real fan-out migration
branch**: also confirmed live in the same proof-of-concept. A
multi-Payment Opportunity naturally produces one Custom-type Gift
Commitment Schedule but several Gift Transactions (one per Payment) --
linking all of them to that one shared schedule violates this rule.
Practical effect: a fan-out routing branch like this can carry
`GiftCommitmentId` (the parent commitment) on every resulting
transaction, but not `GiftCommitmentScheduleId`, unless the design
builds a schedule per transaction instead of per parent. See
`validators/GiftTransaction.md` and
`okf/npsp-to-npc/opportunity-routing.md`.

**Confirmed a second time, independently** (NPC fundraising/donor-
management Snowfakery dogfood build, 2026-07-19 — a different dataset,
different session, same org): "Transaction Due Date Required" and "Due
Date vs. Schedule Start Date" both fired live on freshly-generated data
that omitted/misordered `TransactionDueDate`, exactly as this table
predicts. Two things this second pass adds beyond what's in this table:

- **"Single Transaction for Custom Schedule" is not always enforced
  synchronously within one Bulk API 2.0 batch.** 3 real rows briefly
  succeeded linking to the same Custom-type schedule before the
  platform's own revalidation caught the violation on a later touch —
  don't assume a same-batch insert attempt will reliably reject the
  second-and-later violating row; rank candidates client-side and only
  ever send the link for one per Custom schedule to begin with.
- **Clearing an already-set `GiftCommitmentScheduleId` needs the literal
  `#N/A` Bulk API 2.0 CSV sentinel, not a blank cell** — a blank cell on
  an update is a no-op, not "set to null." Relevant to "Updating the Gift
  Commitment Schedule"'s own lock: even a correctly-`#N/A`'d clear
  attempt is rejected once `Status` has left `Unpaid`/`Pending` (matches
  this table's own restriction exactly) — the delete-then-reinsert fix
  this doc already names is confirmed the only way out, not merely one
  option among several.

See [validators/GiftTransaction.md](../../validators/GiftTransaction.md)
for the full technical write-up of this second confirmation.

# Citations

1. Migration guide, Appendix B - Fundraising Validations, "Gift
   Transaction Validations" (see [migration-guide.md](../npsp-to-npc/migration-guide.md))
