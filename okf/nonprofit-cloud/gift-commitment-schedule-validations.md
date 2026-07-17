---
type: PlatformValidation
title: Gift Commitment Schedule validations (AFNP)
description: Official, platform-enforced validation rules on the
  Agentforce Nonprofit Gift Commitment Schedule object -- Appendix B of
  Salesforce's migration guide.
resource: https://resources.docs.salesforce.com/rel1/doc/en-us/static/pdf/Agentforce_Nonprofit_Migration_Guide_v2.pdf
tags: [npsp, npc, afnp, gift-commitment-schedule, validation, fundraising]
timestamp: "2026-07-16"
---
# Gift Commitment Schedule validations (AFNP)

Extracted directly from the migration guide's Appendix B, pages 74-77.
"Disable with Toggle" means Salesforce provides an admin-facing switch to
turn that specific rule off; where blank, the rule cannot be disabled.

| Validation | Description | Disable with Toggle |
|---|---|---|
| Transaction Interval Positive | Checks that the Transaction Interval is a value greater than 0. | |
| Transaction Amount Not Negative | Ensures the Transaction Amount is greater than or equal to 0. | |
| End Date Greater Than Start Date | Ensures that the End Date is not earlier than the Start Date. | |
| Transaction Day Required for Monthly | Ensures that the Transaction Day value is greater than 0 if the Transaction Period is 'Monthly'. | |
| Transaction Interval Less than 100 | Ensures that the Transaction Interval is less than or equal to 100. | |
| Transaction Period Required for Recurring | Ensures that the Installment Period is populated for recurring schedules. | |
| Prevent Editing When Schedule Has Transactions | Prevent field edits when a Schedule has associated Gift Transactions. | Yes |
| Schedule Start Date Before Transaction Due Date | Ensures the Schedule's Start Date is before an associated earliest Gift Transaction's Due Date. | |
| Schedule End Date Should be After Latest Transaction Due Date | Ensures the Schedule's End Date is after the latest associated Gift Transaction's Due Date. | |
| Require Gift Commitment for Custom Schedules | Ensures that custom Gift Commitment Schedules are associated with a Gift Commitment Id. | |
| Custom Schedules Can't be Paused | Ensures that the Pause Transactions schedule type is not selected when creating a custom schedule. | |
| Custom Schedules can only be created on Gift Commitment with a Custom Schedule Type | Ensures that only custom Gift Commitment Schedules can be created/associated with Gift Commitments with a custom type. | |
| Limit of 50 Custom Schedules | Ensures that only 50 custom Gift Commitment Schedules are created in one request. | |
| Prevent overlapping schedules | Ensures that Gift Commitment Schedules don't overlap with other existing schedules. | |
| Prevent Schedule creation when Gift Commitment Schedule Type is Blank | Ensures Gift Commitment Schedules can only be associated with Gift Commitments that don't have a blank Schedule Type. | |
| Prevent mismatched schedule types | Ensures Gift Commitment Schedule types (recurring or custom) match the Schedule Type specified on the Gift Commitment. | |

**Practical implication**: several rules constrain schedule/transaction
ordering directly (Schedule Start Date must precede its earliest Gift
Transaction's Due Date, End Date must follow the latest one) -- a bulk
load building both a Gift Commitment Schedule and its Gift Transactions
in the same pass needs the schedule's own date range calculated *before*
generating the transaction rows, not derived from them afterward. The
"Limit of 50 Custom Schedules... in one request" bound is also a real
batch-size constraint worth carrying into `batch_advisor.py`'s
heuristics if a real project builds this object.

# Citations

1. Migration guide, Appendix B - Fundraising Validations, "Gift
   Commitment Schedule Validations" (see
   [migration-guide.md](../npsp-to-npc/migration-guide.md))
