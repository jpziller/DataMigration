/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see postmortems/2026-07-27-npsp-to-npc-v2-real-run.md and
   okf/npsp-to-npc/reference-implementation.md). The account/relationship
   layer (090-140) is the proven, real-data-verified transform logic; the
   platform learnings concentrate in the gift objects (150-220).

   Builds HouseholdAccount_Load from dbo.Account -- NPSP auto-created
   Household Accounts replicated from NPSP_SOURCE, one per seeded Contact.
   The household becomes a target Account with RecordType = Household; its
   companion PartyRelationshipGroup is a separate later step (120), by real
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
