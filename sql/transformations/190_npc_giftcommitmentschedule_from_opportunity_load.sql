/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 11 of ~14. Second half of
   the Opportunity multi-Payment routing (180) -- needs 180's real,
   already-loaded GiftCommitmentId.

   TransactionPeriod = 'Custom', matching 180's ScheduleType = 'Custom'
   (the same cross-object validation found live in 160/170). TransactionAmount
   is each Opportunity's total Amount divided by its real Payment count --
   a representative average installment size, since a Custom schedule has
   no single natural "period amount" the way a Recurring one does.
   TransactionInterval/TransactionDay are not meaningful for a Custom
   period and are left NULL -- confirmed live neither is required outside
   the Monthly-specific TransactionDay rule (Appendix B). */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentScheduleFromOpp_Load];

SELECT
    o.Id AS LoadId,
    o.Id AS MigrationID__c,
    gc.Id AS GiftCommitmentId,
    'Custom' AS TransactionPeriod,
    o.Amount / pc.PaymentCount AS TransactionAmount,
    o.CloseDate AS StartDate,
    'CreateTransactions' AS [Type]
INTO [dbo].[GiftCommitmentScheduleFromOpp_Load]
FROM [dbo].[Opportunity] o
JOIN [dbo].[GiftCommitmentFromOpp_Load] gc ON gc.LoadId = o.Id
JOIN (
    SELECT npe01__Opportunity__c AS OppId, COUNT(*) AS PaymentCount
    FROM [dbo].[npe01__OppPayment__c]
    GROUP BY npe01__Opportunity__c
) pc ON pc.OppId = o.Id;
