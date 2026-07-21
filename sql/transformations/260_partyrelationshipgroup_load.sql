/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 2 of
   11. Pure SQL, no Mock table -- one PartyRelationshipGroup per household
   Account (230, already loaded), looking up to its real Id.

   Per validators/PartyRelationshipGroup.md (found during the earlier
   NPSP-to-NPC PoC): Name is required with no platform default (reuses
   the household Account's own already-"Snowfake-"-prefixed Name);
   Type = 'Household' is correct; Category is deliberately left unset
   (real reference-record evidence showed ~0% population, so inventing a
   value would itself be a shape defect, not a harmless default); primary
   address fields are sourced from the household Account's own Billing
   address, same as the PoC's own 120 script. */

DROP TABLE IF EXISTS [dbo].[PartyRelationshipGroup_Load];

SELECT
    ha.LoadId AS LoadId,
    'SNOWFAKE-PRG-' + CAST(ha.LoadId AS VARCHAR(10)) AS MigrationID__c,
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
