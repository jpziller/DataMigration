/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 11
   of 11 (final group). Pure SQL, no Mock table -- fan-out join of
   GiftTransaction_Load x GiftDesignation_Load. Every transaction gets a
   primary designation allocation; roughly half (even LoadId) also get a
   second, smaller allocation to a different designation, modeling a real
   gift sometimes being split across two funds.

   Percent required alongside Amount -- confirmed live in the earlier
   NPSP-to-NPC PoC's own 220_npc_gifttransactiondesignation_from_allocation_load.sql
   ("Complete both the Percent and Amount fields"), reused here directly.
   Computed against each transaction's own OriginalAmount, same formula:
   a single-designation transaction lands at 100%, a split transaction's
   two rows land at 60%/40%.

   CORRECTED live: a split's two Amounts must never sum to more than the
   transaction's own OriginalAmount -- FIELD_INTEGRITY_EXCEPTION on 1 of
   60 rows, a real currency-rounding edge case (independently rounding
   60% and 40% of an odd-cent amount can round both halves UP, overshooting
   the total by a cent). Fixed by computing the primary share as a real
   ROUND(...,2) and the secondary share as the exact remainder
   (OriginalAmount - primary), not an independently-rounded 40% -- the
   two halves always sum to exactly the original amount this way. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionDesignation_Load];

WITH DesignationPool AS (
    SELECT LoadId, Id, ROW_NUMBER() OVER (ORDER BY LoadId) AS DesignationSeq, COUNT(*) OVER () AS DesignationCount
    FROM [dbo].[GiftDesignation_Load]
),
PrimaryShare AS (
    SELECT
        gt.LoadId,
        gt.Id AS GiftTransactionId,
        gt.OriginalAmount,
        CASE WHEN gt.LoadId % 2 = 0 THEN ROUND(0.6 * gt.OriginalAmount, 2) ELSE gt.OriginalAmount END AS PrimaryAmount,
        gd.Id AS PrimaryDesignationId
    FROM [dbo].[GiftTransaction_Load] gt
    JOIN DesignationPool gd ON gd.DesignationSeq = ((gt.LoadId - 1) % gd.DesignationCount) + 1
)
SELECT
    'P' + CAST(LoadId AS VARCHAR(10)) AS LoadId,
    'SNOWFAKE-GTD-P' + CAST(LoadId AS VARCHAR(10)) AS MigrationID__c,
    GiftTransactionId,
    PrimaryDesignationId AS GiftDesignationId,
    PrimaryAmount AS Amount,
    ROUND(100.0 * PrimaryAmount / OriginalAmount, 2) AS [Percent]
INTO [dbo].[GiftTransactionDesignation_Load]
FROM PrimaryShare

UNION ALL

SELECT
    'S' + CAST(ps.LoadId AS VARCHAR(10)) AS LoadId,
    'SNOWFAKE-GTD-S' + CAST(ps.LoadId AS VARCHAR(10)) AS MigrationID__c,
    ps.GiftTransactionId,
    gd2.Id AS GiftDesignationId,
    ps.OriginalAmount - ps.PrimaryAmount AS Amount,
    ROUND(100.0 * (ps.OriginalAmount - ps.PrimaryAmount) / ps.OriginalAmount, 2) AS [Percent]
FROM PrimaryShare ps
JOIN DesignationPool gd2 ON gd2.DesignationSeq = (ps.LoadId % gd2.DesignationCount) + 1
WHERE ps.LoadId % 2 = 0;
