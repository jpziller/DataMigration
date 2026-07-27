/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC v2 build attempt (2026-07-27), group 4. CARRIED FORWARD
   UNCHANGED from the PoC (sql/transformations/120).

   One PartyRelationshipGroup per household Account (010, already loaded),
   Type = "Household", looking up to that Account's real, already-migrated
   Id (migration guide sec 7.2.6 -- Account first, PartyRelationshipGroup
   second, by real Id, never combined into one insert).

   Category left unset (2026-07-18 architect-review finding: real
   PartyRelationshipGroup rows in the target org populate it 0/10 -- see
   validators/PartyRelationshipGroup.md). Primary address fields sourced
   from the household Account's own Billing address (already in
   HouseholdAccount_Load). Name is a genuinely required field with no
   platform default -- reuses the household Account's Name. */

DROP TABLE IF EXISTS [dbo].[PartyRelationshipGroup_Load];

SELECT
    ha.LoadId AS LoadId,
    ha.LoadId AS MigrationID__c,
    ha.Id AS AccountId,
    ha.Name,
    'Household' AS [Type],
    'Active' AS [Status],
    ha.BillingStreet AS PrimaryStreet,
    ha.BillingCity AS PrimaryCity,
    ha.BillingState AS PrimaryState,
    ha.BillingPostalCode AS PrimaryPostalCode,
    ha.BillingCountry AS PrimaryCountry
INTO [dbo].[PartyRelationshipGroup_Load]
FROM [dbo].[HouseholdAccount_Load] ha;
