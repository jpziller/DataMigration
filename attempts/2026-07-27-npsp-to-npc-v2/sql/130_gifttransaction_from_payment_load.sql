/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC v2 build attempt (2026-07-27), group 13. CARRIED FORWARD
   UNCHANGED from the PoC (sql/transformations/210) -- each real Payment
   under a multi-Payment Opportunity becomes its own Gift Transaction,
   linked via GiftCommitmentId (NOT GiftCommitmentScheduleId: AFNP's
   "Single Transaction for Custom Schedule" validation forbids >1
   transaction per Custom schedule -- see the PoC header and
   okf/nonprofit-cloud/gift-transaction-validations.md). Same field
   mapping as 120.

   NOTE (v2, rebuild-plan finding 4): no schedule is joined here (by
   design), so the 120-style due-date clamp isn't applied. If a real
   client's Payment dates fall outside their commitment window and hit the
   TransactionDueDate validation, add a clamp against
   GiftCommitmentScheduleFromOpp_Load.StartDate (joined by GiftCommitmentId)
   -- deliberately left out until real data shows it's needed, to avoid an
   untested change to a validated transform. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionFromPayment_Load];

SELECT
    p.Id AS LoadId,
    p.Id AS MigrationID__c,
    p.Name,
    pa.Id AS DonorId,
    gc.Id AS GiftCommitmentId,
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
INTO [dbo].[GiftTransactionFromPayment_Load]
FROM [dbo].[npe01__OppPayment__c] p
JOIN [dbo].[Opportunity] o ON o.Id = p.npe01__Opportunity__c
JOIN [dbo].[Account] pa ON pa.MigrationID__c = o.npsp__Primary_Contact__c
JOIN [dbo].[GiftCommitmentFromOpp_Load] gc ON gc.LoadId = o.Id;
