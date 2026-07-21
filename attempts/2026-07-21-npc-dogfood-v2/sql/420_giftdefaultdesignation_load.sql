/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 11
   of 11 (final group). Pure SQL, no Mock table -- one GiftDefaultDesignation
   per GiftCommitment (15 rows), assigning each commitment a default
   designation round-robin from the 6 real GiftDesignation_Load rows,
   AllocatedPercentage = 100 (a single default each -- this build doesn't
   model a commitment split across multiple default designations).

   ParentRecordId is polymorphic on the real object (Campaign/
   GiftCommitment/Opportunity per describe()) -- scoped to GiftCommitment
   only, a deliberate, disclosed limitation: Opportunity is entirely out
   of this build's scope, and a Campaign-level default designation is a
   materially different real-world concept (a campaign-wide default fund
   vs. one specific commitment's own default) that would need its own
   separate modeling decision, not a natural extension of this same
   transform. */

DROP TABLE IF EXISTS [dbo].[GiftDefaultDesignation_Load];

WITH DesignationPool AS (
    SELECT LoadId, Id, ROW_NUMBER() OVER (ORDER BY LoadId) AS DesignationSeq, COUNT(*) OVER () AS DesignationCount
    FROM [dbo].[GiftDesignation_Load]
)
SELECT
    gc.LoadId AS LoadId,
    'SNOWFAKE-GDD-' + CAST(gc.LoadId AS VARCHAR(10)) AS MigrationID__c,
    gd.Id AS GiftDesignationId,
    gc.Id AS ParentRecordId,
    100 AS AllocatedPercentage
INTO [dbo].[GiftDefaultDesignation_Load]
FROM [dbo].[GiftCommitment_Load] gc
JOIN DesignationPool gd ON gd.DesignationSeq = ((gc.LoadId - 1) % gd.DesignationCount) + 1;
