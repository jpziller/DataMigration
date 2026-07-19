/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 2 of
   11. Pure SQL, no Mock table -- one relationship per household with 2+
   members, self-joining Contact_Load within the same AccountId (real
   Snowfakery can't express "two distinct fields on one child both
   targeting the same object" -- ContactId and RelatedContactId both ->
   Contact -- a genuine gap in build_recipe()'s parent-edge dedup found
   live building this; see snowfakery_data.py's own module docstring for
   the full account. Worth a future engine fix, not attempted this pass).

   PartyRoleRelationId: real reference-record evidence
   (sample-reference-records) showed this populated 15/15 (100%) on real
   ContactContactRelation rows -- not something to leave null. Investigated
   live: PartyRoleRelation for Contact_Contact_Relationship is a small,
   fixed reference set (7 real rows: Parent-Child, Spouse, Sibling, Friend,
   Neighbor, Colleague), replicated into dbo.PartyRoleRelation (330) above
   -- picked round-robin per household here, not randomly, so this stays
   reproducible. HierarchyType is always 'Peer' in real data (42/42,
   confirmed live) regardless of which role was chosen -- set unconditionally,
   never derived from the role. RelatedInverseRecordId is left unset (0%
   real population, confirmed live) -- see validators/ContactContactRelation.md. */

DROP TABLE IF EXISTS [dbo].[ContactContactRelation_Load];

WITH HouseholdPairs AS (
    SELECT
        c1.AccountId,
        c1.Id AS ContactId,
        c1.LoadId AS ContactLoadId,
        c2.Id AS RelatedContactId,
        ROW_NUMBER() OVER (ORDER BY c1.AccountId) AS HouseholdSeq
    FROM [dbo].[Contact_Load] c1
    JOIN [dbo].[Contact_Load] c2
        ON c2.AccountId = c1.AccountId
        AND c2.LoadId = (SELECT MIN(c3.LoadId) FROM [dbo].[Contact_Load] c3
                          WHERE c3.AccountId = c1.AccountId AND c3.LoadId > c1.LoadId)
    WHERE c1.LoadId = (SELECT MIN(c4.LoadId) FROM [dbo].[Contact_Load] c4 WHERE c4.AccountId = c1.AccountId)
),
Roles AS (
    SELECT Id, RoleName,
        ROW_NUMBER() OVER (ORDER BY Id) AS RoleSeq,
        COUNT(*) OVER () AS RoleCount
    FROM [dbo].[PartyRoleRelation]
    WHERE RelationshipObjectName = 'Contact_Contact_Relationship'
)
SELECT
    hp.ContactLoadId AS LoadId,
    'SNOWFAKE-CCR-' + CAST(hp.ContactLoadId AS VARCHAR(10)) AS MigrationID__c,
    hp.ContactId,
    hp.RelatedContactId,
    r.Id AS PartyRoleRelationId,
    'Peer' AS HierarchyType,
    1 AS IsActive
INTO [dbo].[ContactContactRelation_Load]
FROM HouseholdPairs hp
JOIN Roles r ON r.RoleSeq = ((hp.HouseholdSeq - 1) % r.RoleCount) + 1;
