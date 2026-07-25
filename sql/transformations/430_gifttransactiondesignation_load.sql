/* No ticket -- no ticket system in use for this project (hard rule 10).

   PROMOTED (2026-07-24) from attempts/2026-07-21-npc-sample-v2/sql/ --
   the Replace-model promotion described in CLAUDE.md's "Library vs.
   attempts workspace" section, now that this fix is proven live (39/40
   corrected rows loaded against NPC_TARGET_v2). This replaces the
   library's own earlier version, which used a round-robin allocation
   across fabricated GiftDesignation_Load rows -- confirmed wrong by a
   real Nonprofit Cloud architect's review; see
   validators/GiftTransactionDesignation.md for the full account. Only
   this one script is promoted here, not the rest of the 2026-07-21
   rebuild attempt -- the other 19 scripts in that attempt remain
   unpromoted, parallel to this library's earlier (first-build) versions
   of the same objects.

   NPC fundraising/donor-management Snowfakery sample data recipe, group 11
   of 11 (final group).

   CORRECTED live (2026-07-24): a real Nonprofit Cloud architect (Ali)
   reviewed this build's earlier output and confirmed the original
   approach -- round-robin allocation across this build's own 6 fabricated
   GiftDesignation_Load rows, entirely independent of the parent's real
   GiftDefaultDesignation -- was fundamentally wrong, not a minor miss.
   See validators/GiftTransactionDesignation.md for the full account.

   The real rule: a GiftTransactionDesignation must be INHERITED from its
   parent's real GiftDefaultDesignation(s) -- same designation(s), same
   split -- never independently chosen. Parent hierarchy: GiftCommitment,
   if there is one; else Campaign (this build has no Opportunity object in
   scope); else the org-wide default designation. GDDs can be multiple
   (an even split across 2-3 designations); a transaction should get one
   GiftTransactionDesignation row per real GDD row on its parent,
   mirroring each GDD's own AllocatedPercentage.

   Reads two live-replicated (never inserted/updated -- see
   validators/GiftDefaultDesignation.md and validators/GiftDesignation.md)
   snapshot tables, NOT Load tables:
     python cli.py --org target replicate GiftDefaultDesignation
     python cli.py --org target replicate GiftDesignation --raw
   (--raw needed for GiftDesignation only -- a real replicate.py bug found
   live: one of its decimal rollup fields, e.g. AverageTransactionAmount,
   overflows this backend's inferred SQL Server NUMERIC precision for a
   couple of real, long-lived designation records, raising pyodbc's
   "Converting decimal loses precision" in typed mode. --raw's
   store-everything-as-text path sidesteps it; IsDefault is compared as
   the literal text 'true' below as a result. GiftDefaultDesignation
   didn't hit this in typed mode, so it's replicated normally. See
   ROADMAP.md #81.)

   Confirmed live in NPC_TARGET_v2 while building this: 12 of this
   build's own 15 real GiftCommitment records (all Recurring-type) have
   an auto-created GiftDefaultDesignation; the 3 Custom-type ones don't.
   Campaign never gets one at all (0 of 3 real Campaigns checked). The
   org-wide default designation is "General fund",
   GiftDesignation.IsDefault = 'true' -- looked up dynamically here, never
   a hardcoded Id. GiftDefaultDesignation.ParentRecordId is polymorphic
   (GiftCommitment `6gcfn...` or Campaign `701fn...` prefix, confirmed by
   real Id values in this org) -- joined against both GiftCommitment_Load
   and Campaign_Load's real Ids below, never assumed to be one or the
   other.

   Percent required alongside Amount -- confirmed live in the earlier
   NPSP-to-NPC PoC's own 220_npc_gifttransactiondesignation_from_allocation_load.sql
   ("Complete both the Percent and Amount fields"), reused here directly.
   AllocatedPercentage is mirrored from the real parent GDD row(s)
   (or 100 for the org-wide-default fallback) rather than recomputed.

   CARRIED FORWARD from the original build: a multi-way split's Amounts
   must sum to EXACTLY the transaction's own OriginalAmount, never two-plus
   independently-rounded percentages (which can overshoot by a cent on an
   odd-cent amount -- FIELD_INTEGRITY_EXCEPTION, hit live on the original
   fabricated-split design). Every split row but the last gets a real
   ROUND(...,2) share; the last gets the exact remainder. This build's real
   GDD splits are all single-designation (100%) so the correction is inert
   in practice here, but the general-N-way-split logic is kept since Ali
   confirmed GDDs "can also come in multiples" on other real data.

   FOUND live building this: a first draft fell through to Campaign/org-
   default only when GiftCommitmentId was NULL outright -- 3 transactions
   linked to one of this build's 3 Custom-type commitments (the ones with
   no auto-created GDD at all, see validators/GiftDefaultDesignation.md's
   Recurring/Custom split) got ZERO GiftTransactionDesignation rows as a
   result, silently. Ali's hierarchy ("Gift Commitment, if there is one")
   describes which PARENT to check, not a guarantee that parent's GDD is
   populated -- this build's own Custom/Recurring GDD gap is a quirk of
   this synthetic data, not something her rule anticipated. Interpreting
   "no GDD found on the linked commitment" the same as "no commitment
   link" and falling through the rest of the chain (Campaign, then org
   default) is the safer reading: every real transaction should end up
   with SOME designation, and nothing in the confirmed rule forbids it.
   Fixed below by testing NOT EXISTS a matching GDD at each stage, not
   just NULL on the FK column itself. */

DROP TABLE IF EXISTS [dbo].[GiftTransactionDesignation_Load];

WITH CommitmentGDD AS (
    SELECT
        gdd.ParentRecordId AS GiftCommitmentId,
        gdd.GiftDesignationId,
        gdd.AllocatedPercentage,
        ROW_NUMBER() OVER (PARTITION BY gdd.ParentRecordId ORDER BY gdd.Id) AS SplitSeq,
        COUNT(*) OVER (PARTITION BY gdd.ParentRecordId) AS SplitCount
    FROM [dbo].[GiftDefaultDesignation] gdd
    JOIN [dbo].[GiftCommitment_Load] gc ON gc.Id = gdd.ParentRecordId
),
CampaignGDD AS (
    SELECT
        gdd.ParentRecordId AS CampaignId,
        gdd.GiftDesignationId,
        gdd.AllocatedPercentage,
        ROW_NUMBER() OVER (PARTITION BY gdd.ParentRecordId ORDER BY gdd.Id) AS SplitSeq,
        COUNT(*) OVER (PARTITION BY gdd.ParentRecordId) AS SplitCount
    FROM [dbo].[GiftDefaultDesignation] gdd
    JOIN [dbo].[Campaign_Load] c ON c.Id = gdd.ParentRecordId
),
OrgDefault AS (
    SELECT TOP 1 Id AS GiftDesignationId
    FROM [dbo].[GiftDesignation]
    WHERE [IsDefault] = 'true'
),
Source AS (
    -- 1. GiftCommitment's real GDD(s), when the transaction is commitment-linked
    --    AND that commitment actually has one (not every commitment does --
    --    see the Recurring/Custom split noted above).
    SELECT
        gt.LoadId, gt.Id AS GiftTransactionId, gt.OriginalAmount,
        cg.GiftDesignationId, cg.AllocatedPercentage, cg.SplitSeq, cg.SplitCount
    FROM [dbo].[GiftTransaction_Load] gt
    JOIN CommitmentGDD cg ON cg.GiftCommitmentId = gt.GiftCommitmentId

    UNION ALL

    -- 2. else Campaign's real GDD(s), when the transaction has no usable
    --    commitment GDD but does have a campaign link with its own GDD.
    SELECT
        gt.LoadId, gt.Id, gt.OriginalAmount,
        cg.GiftDesignationId, cg.AllocatedPercentage, cg.SplitSeq, cg.SplitCount
    FROM [dbo].[GiftTransaction_Load] gt
    JOIN CampaignGDD cg ON cg.CampaignId = gt.CampaignId
    WHERE NOT EXISTS (SELECT 1 FROM CommitmentGDD c1 WHERE c1.GiftCommitmentId = gt.GiftCommitmentId)

    UNION ALL

    -- 3. else the org-wide default, at 100% -- the final fallback for
    --    everything not covered by 1 or 2.
    SELECT
        gt.LoadId, gt.Id, gt.OriginalAmount,
        od.GiftDesignationId, 100 AS AllocatedPercentage, 1 AS SplitSeq, 1 AS SplitCount
    FROM [dbo].[GiftTransaction_Load] gt
    CROSS JOIN OrgDefault od
    WHERE NOT EXISTS (SELECT 1 FROM CommitmentGDD c1 WHERE c1.GiftCommitmentId = gt.GiftCommitmentId)
      AND NOT EXISTS (SELECT 1 FROM CampaignGDD cg WHERE cg.CampaignId = gt.CampaignId)
),
WithAmount AS (
    SELECT
        *,
        SUM(CASE WHEN SplitSeq < SplitCount
                 THEN ROUND(AllocatedPercentage / 100.0 * OriginalAmount, 2)
                 ELSE 0 END) OVER (PARTITION BY LoadId) AS PriorRoundedTotal
    FROM Source
)
SELECT
    CAST(LoadId AS VARCHAR(10)) + '-' + CAST(SplitSeq AS VARCHAR(10)) AS LoadId,
    'SNOWFAKE-GTD-' + CAST(LoadId AS VARCHAR(10)) + '-' + CAST(SplitSeq AS VARCHAR(10)) AS MigrationID__c,
    GiftTransactionId,
    GiftDesignationId,
    CASE WHEN SplitSeq < SplitCount
         THEN ROUND(AllocatedPercentage / 100.0 * OriginalAmount, 2)
         ELSE OriginalAmount - PriorRoundedTotal
    END AS Amount,
    AllocatedPercentage AS [Percent]
INTO [dbo].[GiftTransactionDesignation_Load]
FROM WithAmount;
