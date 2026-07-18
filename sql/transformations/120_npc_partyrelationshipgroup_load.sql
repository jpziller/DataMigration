/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 4 of ~14. "New Data" per
   the field-mapping workbook's taxonomy -- one PartyRelationshipGroup per
   household Account (090, already loaded), Type = "Household", looking
   up to that Account's real, already-migrated Id (migration guide sec
   7.2.6 -- Account first, PartyRelationshipGroup second, by real Id,
   never combined into one insert).

   Category (corrected 2026-07-18, architect review finding): originally
   set to "Staying under same roof" as the closest real picklist value to
   NPSP's own household concept -- but sample-reference-records against 10
   real, non-migrated PartyRelationshipGroup records in the live target org
   showed Category populated 0 of 10 times. Real household groups in this
   org essentially never set it, so inventing a value on every one of our 8
   records was itself a shape defect (technically valid, but visibly
   different from how a real/human-created household group looks). Left
   unset now -- see validators/PartyRelationshipGroup.md.

   PrimaryStreet/PrimaryCity/PrimaryState/PrimaryPostalCode/PrimaryCountry
   (added 2026-07-18, same review): the same reference sample showed these
   populated 2-3 of 10 times -- sourced directly from the household
   Account's own Billing address, already carried in HouseholdAccount_Load
   (090), no new join needed.

   Name is a genuinely required field with no platform default (confirmed
   live -- REQUIRED_FIELD_MISSING when omitted; describe() shows
   createable: True, nillable: False, defaultedOnCreate: False, an
   ordinary required field, not a describe()/API mismatch -- an earlier
   version of this comment claimed otherwise and was wrong, see
   validators/PartyRelationshipGroup.md's own correction). Reuses the
   household Account's own Name. */

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
