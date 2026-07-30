/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). Full rationale: the 4
   single-Payment Opportunities route to Gift Transaction,
   joined to their one Payment; the RD's first-installment Opportunity gets
   GiftCommitmentId + GiftCommitmentScheduleId (the latter read from a live
   dbo.GiftCommitmentSchedule replicate by real GiftCommitmentId, since the
   schedule is often platform-auto-created and never in
   GiftCommitmentSchedule_Load). Status/PaymentMethod/AcknowledgementStatus
   picklist mappings and Name-required-on-insert as in the PoC.

   PIPELINE DEPENDENCY: dbo.GiftCommitmentSchedule must
   be freshly replicated from the target org AFTER 160/170 run and BEFORE
   this script.

   v2 ADDITION (rebuild-plan finding 4): a defensive two-sided clamp on
   TransactionDueDate into the joined schedule's window, mirroring
   sql/transformations/390. No-op when the payment date already falls
   inside the schedule window (or when there is no schedule); only guards a
   real payment dated outside its RD schedule window, which AFNP's
   TransactionDueDate validation (Appendix B) would otherwise reject. The
   PoC's clean seed data never exercised this; real NPSP data can. See
   okf/salesforce-platform/date-range-fields-must-be-ordered.md. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionFromOpp_Load];

SELECT
    o.Id AS LoadId,
    o.Id AS MigrationID__c,
    o.Name,
    pa.Id AS DonorId,
    rdgc.Id AS GiftCommitmentId,
    rdsched.Id AS GiftCommitmentScheduleId,
    -- Status/dates keyed on whether the Payment was actually paid (found
    -- live on real NPSP data): NPSP has unpaid/pledged installments (npe01__Paid__c =
    -- false) with no payment date, only a scheduled due date. AFNP's
    -- GiftTransaction Status = 'Paid' REQUIRES a completion date, so a
    -- hardcoded 'Paid' fails on those (INVALID_INPUT/FIELD_INTEGRITY). The
    -- PoC's seed was all-paid, so this only surfaced on real NPSP data.
    CASE WHEN p.npe01__Paid__c = 1 THEN 'Paid' ELSE 'Unpaid' END AS [Status],
    'Individual' AS GiftType,
    p.npe01__Payment_Amount__c AS OriginalAmount,
    -- TransactionDate is the completion date -- only a paid gift has one.
    CASE WHEN p.npe01__Paid__c = 1 THEN p.npe01__Payment_Date__c END AS TransactionDate,
    -- Due date: the actual payment date if paid, else the scheduled date;
    -- then clamped into the schedule window (finding 4). Always populated
    -- (TransactionDueDate is required, Appendix B).
    CASE
        WHEN rdsched.Id IS NOT NULL AND rdsched.StartDate > COALESCE(p.npe01__Payment_Date__c, p.npe01__Scheduled_Date__c)
            THEN rdsched.StartDate
        WHEN rdsched.Id IS NOT NULL AND rdsched.EndDate IS NOT NULL
             AND rdsched.EndDate < COALESCE(p.npe01__Payment_Date__c, p.npe01__Scheduled_Date__c)
            THEN rdsched.EndDate
        ELSE COALESCE(p.npe01__Payment_Date__c, p.npe01__Scheduled_Date__c)
    END AS TransactionDueDate,
    CASE WHEN p.npe01__Paid__c = 1 THEN p.npe01__Payment_Date__c END AS CheckDate,
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
