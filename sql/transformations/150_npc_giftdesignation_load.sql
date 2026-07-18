/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 7 of ~14. GiftDesignation
   is AFNP's replacement for NPSP's General Accounting Unit (migration
   guide sec 7.5 "Migrate Gift Designations (GAUs)") -- a near-direct
   1:1 carry-over: Name/Description/IsActive map cleanly, GiftDesignation's
   remaining fields are all AFNP-computed rollup aggregates (mirroring the
   GAU's own rollup fields, which are Disregard per the workbook's own
   taxonomy -- never migrated, always recomputed by the target platform). */

DROP TABLE IF EXISTS [dbo].[GiftDesignation_Load];

SELECT
    g.Id AS LoadId,
    g.Id AS MigrationID__c,
    g.Name,
    g.npsp__Description__c AS Description,
    g.npsp__Active__c AS IsActive
INTO [dbo].[GiftDesignation_Load]
FROM [dbo].[npsp__General_Accounting_Unit__c] g;
