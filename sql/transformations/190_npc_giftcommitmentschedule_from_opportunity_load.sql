/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). Second half of the
   Opportunity multi-Payment routing (180). TransactionPeriod='Custom'
   (matches 180's ScheduleType). TransactionAmount is the Opportunity total
   divided by its real Payment count (a representative Custom installment).
   StartDate only (no EndDate -- no window to order). */

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
