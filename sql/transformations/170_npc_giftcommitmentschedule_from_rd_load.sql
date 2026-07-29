/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). Full rationale: ONLY
   'Custom'-period RDs get an explicit insert (a Recurring-type
   GiftCommitment auto-creates its schedule; a second explicit insert
   collides live -- the 2026-07-18 architect-review fix). 200-branch
   transactions read the auto-created schedule back from a live replicate
   by GiftCommitmentId, not from this table.

   v2 ADDITION (rebuild-plan finding 4 -- date-range ordering): a defensive
   forward-window guard on EndDate, mirroring sql/transformations/370. It
   is a no-op on valid data (EndDate >= StartDate passes through; NULL, i.e.
   open-ended, stays NULL) and only rewrites a genuinely backwards window
   -- cheap insurance against messy real NPSP RD dates that the PoC's own
   clean seed data never exercised. See
   okf/salesforce-platform/date-range-fields-must-be-ordered.md. */

DROP TABLE IF EXISTS [dbo].[GiftCommitmentSchedule_Load];

SELECT
    rd.Id AS LoadId,
    rd.Id AS MigrationID__c,
    gc.Id AS GiftCommitmentId,
    'Custom' AS TransactionPeriod,
    NULL AS TransactionDay,
    1 AS TransactionInterval,
    rd.npe03__Installment_Amount__c AS TransactionAmount,
    rd.npsp__StartDate__c AS StartDate,
    CASE WHEN rd.npsp__EndDate__c IS NULL THEN NULL
         WHEN rd.npsp__EndDate__c >= rd.npsp__StartDate__c THEN rd.npsp__EndDate__c
         ELSE DATEADD(YEAR, 2, rd.npsp__StartDate__c) END AS EndDate,
    'CreateTransactions' AS [Type]
INTO [dbo].[GiftCommitmentSchedule_Load]
FROM [dbo].[npe03__Recurring_Donation__c] rd
JOIN [dbo].[GiftCommitmentFromRD_Load] gc ON gc.LoadId = rd.Id
WHERE rd.npe03__Installment_Period__c NOT IN ('Monthly', 'Weekly', 'Yearly')
   OR rd.npe03__Installment_Period__c IS NULL;
