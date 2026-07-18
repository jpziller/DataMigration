/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 12 of ~14. Opportunity
   routing (okf/npsp-to-npc/opportunity-routing.md): the 4 Opportunities
   with exactly ONE real Payment (confirmed live, including the 3
   NPSP-auto-generated ones the original seed Load table never tracked)
   route to Gift Transaction, joined to that one Payment for the real
   transaction-level detail (amount/date/method) rather than using
   Opportunity-level fields.

   Opportunity #1 (npe03__Recurring_Donation__c populated) is the
   RD's own auto-generated first-installment Opportunity -- migrated as
   its own real Gift Transaction (not skipped as historical noise, per
   explicit decision this planning session), with GiftCommitmentId set to
   the Gift Commitment 160 already created from that same RD. Opportunities
   #2/#3/#4 (standalone) get no GiftCommitmentId.

   GiftCommitmentScheduleId (added 2026-07-18, architect review finding):
   Opportunity #1 also gets GiftCommitmentScheduleId -- originally missing
   entirely (this migration's own gap), caught when a second architect
   reviewing the live org flagged this exact record
   (GiftTransaction 6trfn000000rknwAAA) as disconnected from its schedule.
   Joined against dbo.GiftCommitmentSchedule -- a live, target-org replicate
   keyed by the real GiftCommitmentId, NOT GiftCommitmentSchedule_Load's own
   LoadId. This distinction matters: GiftCommitmentSchedule_Load only
   reflects rows 170 explicitly tried to insert, but Nonprofit Cloud
   auto-creates a GiftCommitmentSchedule itself whenever the parent
   GiftCommitment.ScheduleType = 'Recurring' (confirmed live -- see 170's
   own header and okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md).
   3 of this project's 4 RD-derived schedules were auto-created this way and
   never appeared in GiftCommitmentSchedule_Load at all (170's own explicit
   insert for them failed live with a real, previously uninvestigated
   FIELD_INTEGRITY_EXCEPTION). Querying the real dbo.GiftCommitmentSchedule
   replicate by GiftCommitmentId is correct regardless of whether the
   schedule was auto-created or explicitly inserted.
   Deliberately NOT extended to 210 (the multi-Payment-Opportunity branch)
   -- see that script's own header for why (the "Single Transaction for
   Custom Schedule" validation, okf/nonprofit-cloud/gift-transaction-
   validations.md). See validators/GiftTransaction.md and
   validators/GiftCommitmentSchedule.md.

   New pipeline dependency: dbo.GiftCommitmentSchedule must be freshly
   replicated from the target org AFTER 160/170 actually run (so the
   auto-created rows exist to read back) and BEFORE this script --
   `python cli.py --org target replicate GiftCommitmentSchedule` -- the
   same two-pass-requery shape 110's own header already describes for
   dbo.Account/PersonContactId.

   Status = 'Paid' for all 4 (real, Closed Won, already-paid gifts).
   TransactionDueDate is required (Appendix B) and has no better source
   than the payment date itself here. PaymentMethod mapped by real
   picklist value -- npe01__Payment_Method__c's Cash/Check/Credit Card/
   ACH/PayPal all exist verbatim on the target, direct 1:1.
   AcknowledgementStatus mapped from the payment's own
   npsp__Payment_Acknowledgment_Status__c (To Be Acknowledged/Acknowledged/
   Do Not Acknowledge -> To Be Sent/Sent/Don't Send).

   Name is a genuinely required field with no platform default (confirmed
   live via REQUIRED_FIELD_MISSING when omitted -- describe() shows
   createable: True, nillable: False, defaultedOnCreate: False, same as
   PartyRelationshipGroup.Name (120) and GiftCommitment.Name (160); not a
   describe()/API mismatch as an earlier version of this comment claimed,
   see validators/GiftTransaction.md's own correction). Reuses the
   Opportunity's own Name. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionFromOpp_Load];

SELECT
    o.Id AS LoadId,
    o.Id AS MigrationID__c,
    o.Name,
    pa.Id AS DonorId,
    rdgc.Id AS GiftCommitmentId,
    rdsched.Id AS GiftCommitmentScheduleId,
    'Paid' AS [Status],
    'Individual' AS GiftType,
    p.npe01__Payment_Amount__c AS OriginalAmount,
    p.npe01__Payment_Date__c AS TransactionDate,
    p.npe01__Payment_Date__c AS TransactionDueDate,
    p.npe01__Payment_Date__c AS CheckDate,
    CASE p.npe01__Payment_Method__c
        WHEN 'Cash' THEN 'Cash'
        WHEN 'Check' THEN 'Check'
        WHEN 'Credit Card' THEN 'Credit Card'
        WHEN 'ACH' THEN 'ACH'
        WHEN 'PayPal' THEN 'PayPal'
        ELSE 'Unknown'
    END AS PaymentMethod,
    CASE p.npsp__Payment_Acknowledgment_Status__c
        WHEN 'To Be Acknowledged' THEN 'To Be Sent'
        WHEN 'Acknowledged' THEN 'Sent'
        WHEN 'Do Not Acknowledge' THEN 'Don''t Send'
        ELSE 'To Be Sent'
    END AS AcknowledgementStatus,
    p.npsp__Payment_Acknowledged_Date__c AS AcknowledgementDate
INTO [dbo].[GiftTransactionFromOpp_Load]
FROM [dbo].[Opportunity] o
JOIN [dbo].[Account] pa ON pa.MigrationID__c = o.npsp__Primary_Contact__c
JOIN [dbo].[npe01__OppPayment__c] p ON p.npe01__Opportunity__c = o.Id
LEFT JOIN [dbo].[GiftCommitmentFromRD_Load] rdgc ON rdgc.LoadId = o.npe03__Recurring_Donation__c
LEFT JOIN [dbo].[GiftCommitmentSchedule] rdsched ON rdsched.GiftCommitmentId = rdgc.Id
WHERE o.Id IN (
    SELECT npe01__Opportunity__c FROM [dbo].[npe01__OppPayment__c]
    GROUP BY npe01__Opportunity__c
    HAVING COUNT(*) = 1
);
