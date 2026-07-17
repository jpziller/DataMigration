/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 4 of ~14. "New Data" per
   the field-mapping workbook's taxonomy -- one PartyRelationshipGroup per
   household Account (090, already loaded), Type = "Household", looking
   up to that Account's real, already-migrated Id (migration guide sec
   7.2.6 -- Account first, PartyRelationshipGroup second, by real Id,
   never combined into one insert).

   Category = "Staying under same roof" is the closest real picklist
   value (confirmed live) to NPSP's own household concept -- no exact
   "Household" Category value exists on this target org.

   Name is required on insert despite describe() reporting createable =
   false (confirmed live -- REQUIRED_FIELD_MISSING, not
   INVALID_FIELD_FOR_INSERT_UPDATE, so the Bulk API genuinely accepts a
   sent value here even though describe()'s own flag says otherwise; a
   real describe()/API mismatch, not a mistaken assumption). Reuses the
   household Account's own Name. */

DROP TABLE IF EXISTS [dbo].[PartyRelationshipGroup_Load];

SELECT
    ha.LoadId AS LoadId,
    ha.LoadId AS MigrationID__c,
    ha.Id AS AccountId,
    ha.Name,
    'Household' AS [Type],
    'Staying under same roof' AS Category,
    'Active' AS [Status]
INTO [dbo].[PartyRelationshipGroup_Load]
FROM [dbo].[HouseholdAccount_Load] ha;
