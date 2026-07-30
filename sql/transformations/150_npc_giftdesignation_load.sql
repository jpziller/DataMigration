/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md).

   GiftDesignation is AFNP's replacement for NPSP's General Accounting Unit
   (migration guide sec 7.5). Near-direct 1:1: Name/Description/IsActive;
   the remaining GiftDesignation fields are AFNP-computed rollups (never
   migrated). NOTE (sample-data learning): the platform auto-creates a
   GiftDefaultDesignation off GiftDesignation/GiftCommitment -- see the
   doc-only 215 and validators/GiftDefaultDesignation.md; nothing to do
   here, but a downstream consumer (220) must account for it. */

DROP TABLE IF EXISTS [dbo].[GiftDesignation_Load];

SELECT
    g.Id AS LoadId,
    g.Id AS MigrationID__c,
    g.Name,
    g.npsp__Description__c AS Description,
    g.npsp__Active__c AS IsActive
INTO [dbo].[GiftDesignation_Load]
FROM [dbo].[npsp__General_Accounting_Unit__c] g;
