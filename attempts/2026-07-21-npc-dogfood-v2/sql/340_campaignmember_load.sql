/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 6 of
   11 -- companion to 330. Builds CampaignMember_Load from
   dbo.CampaignMember_Mock (19 rows, nested under Campaign in the same
   generate-related-mock-data call -- _ParentMockRef resolves to
   Campaign_Load.LoadId).

   ContactId is SQL-assigned (CampaignMember.ContactId is a real
   reference field, but its target -- Contact -- wasn't in the same
   generate-related-mock-data call as Campaign/CampaignMember, so the
   engine naturally skips it) against the combined real Contact pool:
   the 16 household members (Contact_Load) plus the 10 Person Accounts'
   own platform-auto-created shadow Contact (Account.PersonContactId,
   replicated fresh above) -- a Person Account always has a real backing
   Contact record even though this build never inserts one directly.
   Round-robin assignment, same pattern as the Contact Point loads. */

DROP TABLE IF EXISTS [dbo].[CampaignMember_Load];

WITH ContactPool AS (
    SELECT Id, ROW_NUMBER() OVER (ORDER BY Id) AS ContactSeq, COUNT(*) OVER () AS ContactCount
    FROM (
        SELECT Id FROM [dbo].[Contact_Load]
        UNION ALL
        SELECT PersonContactId AS Id FROM [dbo].[Account] WHERE PersonContactId IS NOT NULL
    ) c
)
SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-CM-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    camp.Id AS CampaignId,
    cp.Id AS ContactId,
    m.Status
INTO [dbo].[CampaignMember_Load]
FROM [dbo].[CampaignMember_Mock] m
JOIN [dbo].[Campaign_Load] camp ON camp.LoadId = m._ParentMockRef
JOIN ContactPool cp ON cp.ContactSeq = ((m._MockRowId - 1) % cp.ContactCount) + 1;
