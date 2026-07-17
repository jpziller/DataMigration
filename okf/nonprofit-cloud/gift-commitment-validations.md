---
type: PlatformValidation
title: Gift Commitment validations (AFNP)
description: Official, platform-enforced validation rules on the
  Agentforce Nonprofit Gift Commitment object -- Appendix B of
  Salesforce's migration guide.
resource: https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf
tags: [npsp, npc, afnp, gift-commitment, validation, fundraising]
timestamp: "2026-07-16"
---
# Gift Commitment validations (AFNP)

Extracted directly from the migration guide's Appendix B, pages 73-74.
"Disable with Toggle" means Salesforce provides an admin-facing switch to
turn that specific rule off; where blank, the rule cannot be disabled.

| Validation | Description | Disable with Toggle |
|---|---|---|
| Expected Total Amount Not Negative | Validates that the Expected Total Commitment Amount is greater than or equal to 0. | |
| End Date Greater than Start Date | Prevents the Expected End Date from being before the Expected Start Date. | |
| Prevent Schedule Type Updates When Gift Commitment Schedule Exists | Prevents updating the Schedule Type when the Commitment has an associated Gift Commitment Schedule. | |
| Update Status to Draft Restricted | Prevents moving a commitment back to 'Draft' status once it is 'Active' and has associated Gift Transactions. | Yes |
| Update Status to Closed Restricted | Prevents changing the Status from Closed to any Status other than Active when it has associated Gift Transactions. | Yes |
| Update Status to Paused Restricted | Prevents updating the status to Paused when the current Gift Commitment Schedule type is Pause Transactions. | |
| Update Paused Status Restricted | Prevents updating the status from Paused to any value other than Lapsed, Failing, or Active when the current Gift Commitment Schedule type is Create Transactions. | |
| Update Currency ISO Code Restricted | Restricts updates to the Currency ISO Code when Gift Commitment Schedule records exist. | |

**Practical implication**: the Status lifecycle (Draft → Active →
Closed/Paused) is one-directional once Gift Transactions or a Gift
Commitment Schedule exist against a commitment. A migration should
generally load Gift Commitments in their final intended Status, or
accept that some of these transitions become permanently blocked once
downstream Gift Transactions/Schedules are created.

# Citations

1. Migration guide, Appendix B - Fundraising Validations, "Gift
   Commitment Validations" (see [migration-guide.md](../npsp-to-npc/migration-guide.md))
