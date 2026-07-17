/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 9 of ~14. Second half of
   the Recurring Donation -> Gift Commitment routing (migration guide sec
   7.6.2) -- needs 160's real, already-loaded GiftCommitmentId (hard rule
   6/7 territory: this table's own single parent lookup).

   TransactionPeriod mapped by real picklist value from
   npe03__Installment_Period__c (Monthly/Quarterly/Yearly/Weekly/
   '1st and 15th') -- Quarterly and '1st and 15th' have no direct target
   equivalent (target only has Monthly/Daily/Weekly/Yearly/Custom,
   confirmed live), so both fall through to 'Custom'.

   TransactionDay is required when TransactionPeriod = 'Monthly' (Appendix
   B validation: "Transaction Day Required for Monthly") -- all 4 seeded
   RDs have NULL npsp__Day_of_Month__c, so this defaults to day 1 for the
   2 Monthly rows; harmless NULL for the other periods, which don't
   require it.

   TransactionInterval defaults to 1 (every period) -- NPSP's own RD model
   has no direct "every N periods" concept to carry over. Type is always
   'CreateTransactions' (never 'PauseTransactions') since every seeded RD
   is Active, not Paused. */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentSchedule_Load];

SELECT
    rd.Id AS LoadId,
    rd.Id AS MigrationID__c,
    gc.Id AS GiftCommitmentId,
    CASE rd.npe03__Installment_Period__c
        WHEN 'Monthly' THEN 'Monthly'
        WHEN 'Weekly' THEN 'Weekly'
        WHEN 'Yearly' THEN 'Yearly'
        ELSE 'Custom'
    END AS TransactionPeriod,
    CASE WHEN rd.npe03__Installment_Period__c = 'Monthly'
         THEN COALESCE(rd.npsp__Day_of_Month__c, '1')
         ELSE NULL
    END AS TransactionDay,
    1 AS TransactionInterval,
    rd.npe03__Installment_Amount__c AS TransactionAmount,
    rd.npsp__StartDate__c AS StartDate,
    rd.npsp__EndDate__c AS EndDate,
    'CreateTransactions' AS [Type]
INTO [dbo].[GiftCommitmentSchedule_Load]
FROM [dbo].[npe03__Recurring_Donation__c] rd
JOIN [dbo].[GiftCommitmentFromRD_Load] gc ON gc.LoadId = rd.Id;
