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
   is Active, not Paused.

   ONLY 'Custom'-period RDs get an explicit insert here (added 2026-07-18,
   architect review finding). Confirmed live: when GiftCommitment.ScheduleType
   = 'Recurring' (this org's target for a Monthly/Weekly/Yearly period, see
   160), Nonprofit Cloud's own automation auto-creates a matching
   GiftCommitmentSchedule the moment the GiftCommitment itself is inserted
   -- a second, explicit insert attempt for the same commitment then fails
   live with FIELD_INTEGRITY_EXCEPTION ("doesn't overlap with an existing
   schedule"). This is exactly what happened to 3 of this project's 4
   original RD-derived schedule rows -- silently recorded as a real bulk_op()
   failure in this table's own Error column, never investigated until a
   second architect's live review of the migrated org traced a specific
   GiftTransaction's missing GiftCommitmentScheduleId back to it. Confirmed
   by direct query: all 3 "Recurring"-type commitments in this org DO have a
   real, live GiftCommitmentSchedule (auto-created, TransactionPeriod
   matching), and the 1 "Custom"-type commitment's schedule is the only one
   this script's own explicit insert actually created. See
   okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md and
   validators/GiftCommitmentSchedule.md.
   Only inserting for 'Custom' here avoids repeating the same collision on
   any future Recurring-period RD -- 200 derives GiftCommitmentScheduleId
   for a Recurring-type case by querying the org's real (auto-created)
   schedule directly, not from this table. */

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
    rd.npsp__EndDate__c AS EndDate,
    'CreateTransactions' AS [Type]
INTO [dbo].[GiftCommitmentSchedule_Load]
FROM [dbo].[npe03__Recurring_Donation__c] rd
JOIN [dbo].[GiftCommitmentFromRD_Load] gc ON gc.LoadId = rd.Id
WHERE rd.npe03__Installment_Period__c NOT IN ('Monthly', 'Weekly', 'Yearly')
   OR rd.npe03__Installment_Period__c IS NULL;
