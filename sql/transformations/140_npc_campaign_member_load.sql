/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 6 of ~14. Needs Campaign_Load
   already loaded (130, real CampaignId) and the target-side Person Account
   replicate already pulled back into dbo.Account (see 110's header --
   ContactId is each person's own auto-generated PersonContactId, not the
   Account Id itself).

   HasResponded confirmed live as not createable on this org's
   CampaignMember -- dropped from the column list (INVALID_FIELD_FOR_
   INSERT_UPDATE otherwise). MigrationID__c also needed its own dedicated
   deploy pass here -- initially missed in the Phase 1 metadata deploy,
   caught live by this load's own pre-flight check ("not a real field on
   CampaignMember"). */

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
