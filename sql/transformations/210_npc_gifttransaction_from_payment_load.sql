/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 13 of ~14. The other half
   of the multi-Payment routing (180/190): each of the 5 real Payments
   under Opportunity #5 (2 payments) and #6 (3 payments) becomes its own
   Gift Transaction, linked via GiftCommitmentId to the Gift Commitment
   180 already created from their shared parent Opportunity (migration
   guide sec 7.6.6 "Create Gift Transactions from Payments" -- loaded
   after 180/190, since a transaction against a schedule needs that
   schedule's commitment to already exist).

   Same field mapping as 200 (Status/PaymentMethod/AcknowledgementStatus/
   Name-required-on-insert) -- see that script's header for the full
   picklist-mapping rationale, not repeated here. DonorId still resolves
   through the parent Opportunity's npsp__Primary_Contact__c (Payment
   itself carries no independent donor reference). */

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
