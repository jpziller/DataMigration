/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 1 of ~14 (see
   okf/npsp-to-npc/ for the official migration guide this sequence
   follows, scoped down to the objects actually seeded this pass).

   Builds HouseholdAccount_Load from dbo.Account -- the 8 NPSP
   auto-created Household Accounts replicated from NPSP_SOURCE (one per
   seeded Contact; no shared multi-member households in this seed data).
   Per the guide's households-to-party-relationship-groups pattern
   (migration guide sec 5.4.1.3/7.2.3/7.2.6), the household itself becomes
   a target Account with RecordType = Household -- the companion
   PartyRelationshipGroup record is a separate later step (120), since it
   looks up to this Account's real, already-migrated Id.

   RecordTypeId is resolved by DeveloperName via dbo.RecordTypeMap (hard
   rule 15 -- never hand-copy a raw org-specific RecordType Id), populated
   by `resolve-record-types Account --org target`.

   Migration key MigrationID__c is the source record's own real Salesforce
   Id (CASESAFEID) -- matches the official guide's own recommended
   pattern ("a legacy-Id field per target object, populated with the NPSP
   record's CASESAFEID"). FLS for MigrationID__c is granted via the
   MigrationFieldAccess permission set (force-app/main/default/
   permissionsets/MigrationFieldAccess.permissionset-meta.xml), assigned
   directly to the connected NPC_TARGET_v2 user -- see hard rule 8.

   Target Account has no State/Country picklist enabled (confirmed live --
   BillingStateCode/BillingCountryCode don't exist on this org's Account),
   so plain BillingState/BillingCountry text carries across unchanged. */

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
