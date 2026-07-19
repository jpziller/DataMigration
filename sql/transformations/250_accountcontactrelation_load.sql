/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 2 of
   11.

   CORRECTED live (new finding, not anticipated in the plan): Salesforce
   auto-creates an AccountContactRelation (IsDirect = true) the instant a
   Contact is inserted with a real AccountId -- confirmed live, all 16 of
   this build's own Contacts already had one the moment 240 finished
   loading, before this script ever ran. This is the same auto-creation
   pattern already found once for GiftCommitmentSchedule (see
   validators/GiftCommitmentSchedule.md) -- an explicit INSERT here
   collided with the real, already-existing row (submitted 16, succeeded
   0, failed 0 -- no error, since bulk_op()'s own fingerprint-based result
   mapping simply never matched anything real). Never insert
   AccountContactRelation explicitly; replicate the real, already-created
   rows instead (`replicate AccountContactRelation --where "IsDirect =
   true"`) and UPDATE them with the fields the auto-creation doesn't set:
   IsIncludedInGroup/IsPrimaryMember are the real household-membership
   signal, not just AccountId/ContactId -- see
   validators/AccountContactRelation.md (found during the earlier NPSP-
   to-NPC PoC). Every generated member gets IsIncludedInGroup = true;
   exactly one member per household gets IsPrimaryMember = true, chosen
   deterministically by lowest Contact_Load.LoadId (this data has no
   NPSP npo02__Household_Naming_Order__c equivalent to rank by).
   MigrationID__c is backfilled onto the real auto-created row too, for
   the same traceability every other object in this build gets. */

DROP TABLE IF EXISTS [dbo].[AccountContactRelation_Load];

SELECT
    c.LoadId AS LoadId,
    acr.Id AS Id,
    'SNOWFAKE-ACR-' + CAST(c.LoadId AS VARCHAR(10)) AS MigrationID__c,
    c.AccountId AS REF_AccountId,  -- bookkeeping only (hard rule 13), for the Sort column below; AccountId itself isn't updateable
    1 AS IsIncludedInGroup,
    CASE WHEN c.LoadId = (
        SELECT MIN(c2.LoadId) FROM [dbo].[Contact_Load] c2 WHERE c2.AccountId = c.AccountId
    ) THEN 1 ELSE 0 END AS IsPrimaryMember
INTO [dbo].[AccountContactRelation_Load]
FROM [dbo].[Contact_Load] c
JOIN [dbo].[AccountContactRelation] acr
    ON acr.AccountId = c.AccountId AND acr.ContactId = c.Id;
