/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 5 of
   11 -- companion to 300/310. Builds ContactPointEmail_Load from
   dbo.ContactPointEmail_Mock (35 standalone rows), ParentId SQL-assigned
   across the same 23-Account pool, IsPrimary deterministic (first email
   per Account). Same disclosed Account-only scoping as 300/310.

   No real ContactPointEmail reference data exists in this org yet
   (record-counts showed 0) -- EmailAddress/UsageType are the plausible
   human-entered fields; EmailMailBox/EmailDomain (system-parsed from
   EmailAddress, never independently hand-typed) and the
   EmailLatestBounce* fields (system-populated on send failure, not
   something a human sets when creating the record) are left out. */

DROP TABLE IF EXISTS [dbo].[ContactPointEmail_Load];

WITH AccountPool AS (
    SELECT Id, ROW_NUMBER() OVER (ORDER BY Id) AS AccountSeq, COUNT(*) OVER () AS AccountCount
    FROM (
        SELECT Id FROM [dbo].[HouseholdAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[OrganizationAccount_Load]
        UNION ALL SELECT Id FROM [dbo].[PersonAccount_Load]
    ) a
),
Assigned AS (
    SELECT
        m._MockRowId,
        m.EmailAddress, m.UsageType,
        ap.Id AS AccountId,
        ROW_NUMBER() OVER (PARTITION BY ap.Id ORDER BY m._MockRowId) AS SeqWithinAccount
    FROM [dbo].[ContactPointEmail_Mock] m
    JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId - 1) % ap.AccountCount) + 1
)
SELECT
    _MockRowId AS LoadId,
    'SNOWFAKE-CPE-' + CAST(_MockRowId AS VARCHAR(10)) AS MigrationID__c,
    AccountId AS ParentId,
    EmailAddress,
    UsageType,
    CASE WHEN SeqWithinAccount = 1 THEN 1 ELSE 0 END AS IsPrimary
INTO [dbo].[ContactPointEmail_Load]
FROM Assigned;
