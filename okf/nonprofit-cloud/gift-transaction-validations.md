---
type: PlatformValidation
title: Gift Transaction validations (AFNP)
description: Official, platform-enforced validation rules on the
  Agentforce Nonprofit Gift Transaction object -- Appendix B of
  Salesforce's migration guide. Not a migration gotcha this framework
  discovered; a documented target-platform business rule.
resource: https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf
tags: [npsp, npc, afnp, gift-transaction, validation, fundraising]
timestamp: "2026-07-16"
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
Accounting Subledger confirmed off first).

# Citations

1. Migration guide, Appendix B - Fundraising Validations, "Gift
   Transaction Validations" (see [migration-guide.md](../npsp-to-npc/migration-guide.md))
