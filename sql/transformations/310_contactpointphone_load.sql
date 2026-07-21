/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 5 of
   11 -- companion to 300. Builds ContactPointPhone_Load from
   dbo.ContactPointPhone_Mock (35 standalone rows), ParentId SQL-assigned
   across the same 23-Account pool, IsPrimary deterministic (first phone
   per Account). Scoped to Account only, same disclosed limitation as 300
   (real object's ParentId is polymorphic Account/Individual; Individual
   is out of this build's 20-object scope).

   No real ContactPointPhone reference data exists in this org yet
   (record-counts showed 0), unlike ContactPointAddress -- field
   selection here is a reasonable judgment call, not real-data-evidenced:
   TelephoneNumber/AreaCode/PhoneType/IsSmsCapable/IsPersonalPhone/
   IsBusinessPhone/UsageType are plausible human-entered fields;
   FormattedInternational/NationalPhoneNumber (system-computed display
   values, never hand-typed), ExtensionNumber, BestTimeToContact*, and
   ActiveFromDate/ActiveToDate are left out for the same minimal-realistic-
   shape reasoning as 300. */

DROP TABLE IF EXISTS [dbo].[ContactPointPhone_Load];

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
        m.AreaCode, m.TelephoneNumber, m.PhoneType, m.IsSmsCapable, m.IsPersonalPhone,
        m.IsBusinessPhone, m.UsageType,
        ap.Id AS AccountId,
        ROW_NUMBER() OVER (PARTITION BY ap.Id ORDER BY m._MockRowId) AS SeqWithinAccount
    FROM [dbo].[ContactPointPhone_Mock] m
    JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId - 1) % ap.AccountCount) + 1
)
SELECT
    _MockRowId AS LoadId,
    'SNOWFAKE-CPP-' + CAST(_MockRowId AS VARCHAR(10)) AS MigrationID__c,
    AccountId AS ParentId,
    AreaCode,
    TelephoneNumber,
    PhoneType,
    IsSmsCapable,
    IsPersonalPhone,
    IsBusinessPhone,
    UsageType,
    CASE WHEN SeqWithinAccount = 1 THEN 1 ELSE 0 END AS IsPrimary
INTO [dbo].[ContactPointPhone_Load]
FROM Assigned;
