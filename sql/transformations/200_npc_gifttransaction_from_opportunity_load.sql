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

   Status = 'Paid' for all 4 (real, Closed Won, already-paid gifts).
   TransactionDueDate is required (Appendix B) and has no better source
   than the payment date itself here. PaymentMethod mapped by real
   picklist value -- npe01__Payment_Method__c's Cash/Check/Credit Card/
   ACH/PayPal all exist verbatim on the target, direct 1:1.
   AcknowledgementStatus mapped from the payment's own
   npsp__Payment_Acknowledgment_Status__c (To Be Acknowledged/Acknowledged/
   Do Not Acknowledge -> To Be Sent/Sent/Don't Send).

   Name required on insert despite describe() reporting createable=false
   -- same real describe()/API mismatch as PartyRelationshipGroup.Name
   (120) and GiftCommitment.Name (160), confirmed live via
   REQUIRED_FIELD_MISSING. Reuses the Opportunity's own Name. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionFromOpp_Load];

SELECT
    o.Id AS LoadId,
    o.Id AS MigrationID__c,
    o.Name,
    pa.Id AS DonorId,
    rdgc.Id AS GiftCommitmentId,
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
WHERE o.Id IN (
    SELECT npe01__Opportunity__c FROM [dbo].[npe01__OppPayment__c]
    GROUP BY npe01__Opportunity__c
    HAVING COUNT(*) = 1
);
