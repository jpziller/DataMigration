/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 5 of ~14. Campaign is a
   core Salesforce standard object, structurally unchanged between NPSP
   and AFNP -- straightforward 1:1 carry-over into the new org (new org
   means new Ids, so this still needs its own MigrationID__c/insert like
   everything else; migration guide sec 7.4 "Migrate Campaigns"). Only
   the 2 real Campaigns our 4 seeded CampaignMembers actually reference
   (dbo.Campaign was already scoped to just those 2 at replicate time). */

DROP TABLE IF EXISTS [dbo].[Campaign_Load];

SELECT
    c.Id AS LoadId,
    c.Id AS MigrationID__c,
    c.Name,
    c.[Type],
    c.[Status],
    c.StartDate,
    c.EndDate,
    c.Description,
    c.IsActive,
    c.ExpectedRevenue,
    c.BudgetedCost,
    c.ActualCost
INTO [dbo].[Campaign_Load]
FROM [dbo].[Campaign] c;
