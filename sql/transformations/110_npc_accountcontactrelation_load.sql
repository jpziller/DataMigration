/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 3 of ~14. "New Data" per
   the official field-mapping workbook's own taxonomy (no direct NPSP
   source field correspondence -- auto-map was skipped for this object,
   see PR discussion) -- this is a synthesized relationship record, not a
   1:1 field carry-over.

   Links each household Account (090, already loaded) to its person
   account's own auto-generated "shadow" Contact (100, already loaded --
   PersonContactId only exists on the target org's Account row AFTER that
   insert actually ran, hence this being its own later step rather than
   folded into 090/100). dbo.Account currently holds a fresh, target-side
   replicate of the 8 just-created Person Accounts (re-pulled specifically
   for PersonContactId) -- NOT the original source household Accounts
   090 already consumed; re-running 090 after this point would need a
   fresh source-side Account replicate first.

   dbo.Contact (source-side, untouched since Phase 2) is the join spine:
   Contact.AccountId is the NPSP household Account's own source Id,
   matching HouseholdAccount_Load.LoadId; Contact.Id is the source Contact
   Id, matching the target Person Account's MigrationID__c (set in 100). */

DROP TABLE IF EXISTS [dbo].[AccountContactRelation_Load];

SELECT
    c.Id AS LoadId,
    c.Id AS MigrationID__c,
    ha.Id AS AccountId,
    pa.PersonContactId AS ContactId,
    1 AS IsActive
INTO [dbo].[AccountContactRelation_Load]
FROM [dbo].[Contact] c
JOIN [dbo].[HouseholdAccount_Load] ha ON ha.LoadId = c.AccountId
JOIN [dbo].[Account] pa ON pa.MigrationID__c = c.Id;
