/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md).

   Campaign is a core standard object, structurally unchanged between NPSP
   and AFNP -- a 1:1 carry-over into the new org (new org = new Ids, so it
   still needs its own MigrationID__c/insert; migration guide sec 7.4).
   Scope is whatever the replicate step pulled into dbo.Campaign (the PoC
   scoped it to just the Campaigns its CampaignMembers referenced). */

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
