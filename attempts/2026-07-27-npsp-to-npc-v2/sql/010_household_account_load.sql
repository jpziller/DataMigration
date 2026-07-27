/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC v2 build attempt (2026-07-27), group 1. See this attempt's
   README.md and okf/npsp-to-npc/sample-data-learnings-for-migration.md.

   CARRIED FORWARD UNCHANGED from the PoC (sql/transformations/090). The
   account/relationship layer was already correct; the sample-data loop's
   learnings concentrate in the gift objects (increment 2). This build
   re-verifies it rather than assuming, but the transform logic is the
   proven one.

   Builds HouseholdAccount_Load from dbo.Account -- NPSP auto-created
   Household Accounts replicated from NPSP_SOURCE, one per seeded Contact.
   The household becomes a target Account with RecordType = Household; its
   companion PartyRelationshipGroup is a separate later step (040), by real
   Id.

   RecordTypeId resolved by DeveloperName via dbo.RecordTypeMap (hard rule
   15 -- never hand-copy a raw org-specific RecordType Id), populated by
   `resolve-record-types Account`. Migration key MigrationID__c is the
   source record's own real Salesforce Id (the guide's recommended
   legacy-Id pattern). */

DROP TABLE IF EXISTS [dbo].[HouseholdAccount_Load];

SELECT
    a.Id AS LoadId,
    a.Id AS MigrationID__c,
    a.Name,
    rt.Id AS RecordTypeId,
    a.BillingStreet,
    a.BillingCity,
    a.BillingState,
    a.BillingPostalCode,
    a.BillingCountry,
    a.ShippingStreet,
    a.ShippingCity,
    a.ShippingState,
    a.ShippingPostalCode,
    a.ShippingCountry,
    a.Phone
INTO [dbo].[HouseholdAccount_Load]
FROM [dbo].[Account] a
CROSS JOIN (
    SELECT Id FROM [dbo].[RecordTypeMap]
    WHERE SobjectType = 'Account' AND DeveloperName = 'Household'
) rt;
