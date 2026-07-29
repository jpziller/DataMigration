/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md).

   Needs Campaign_Load already loaded (130, real CampaignId) and the
   target-side Person Account replicate back in dbo.Account (ContactId is
   each person's own auto-generated PersonContactId, not the Account Id --
   see 110's header).

   HasResponded is not createable on this org's CampaignMember (dropped --
   INVALID_FIELD_FOR_INSERT_UPDATE otherwise, confirmed live in the PoC).
   MigrationID__c must be deployed to CampaignMember with FLS (bulkops'
   pre-flight check catches it if missing). */

DROP TABLE IF EXISTS [dbo].[CampaignMember_Load];

SELECT
    cm.Id AS LoadId,
    cm.Id AS MigrationID__c,
    camp.Id AS CampaignId,
    pa.PersonContactId AS ContactId,
    cm.[Status]
INTO [dbo].[CampaignMember_Load]
FROM [dbo].[CampaignMember] cm
JOIN [dbo].[Campaign_Load] camp ON camp.LoadId = cm.CampaignId
JOIN [dbo].[Account] pa ON pa.MigrationID__c = cm.ContactId;
