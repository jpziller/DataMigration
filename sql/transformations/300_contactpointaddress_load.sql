/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 5 of
   11. Builds ContactPointAddress_Load from dbo.ContactPointAddress_Mock
   (35 standalone rows -- Account wasn't in the same
   generate-related-mock-data call, so ParentId is naturally skipped by
   the engine; assigned here via SQL instead across the combined 23-Account
   pool: 8 household + 5 organization + 10 person, round-robin so every
   Account gets at least one).

   ParentId is polymorphic on the real object (Account or Individual --
   see describe()), but Individual isn't in this build's 20-object scope
   (no MigrationID__c plan, nothing else references it) -- scoped to
   Account only, a deliberate, disclosed limitation. Confirmed live via
   sample-reference-records that real ParentId values in this org are
   Account-shaped anyway.

   Field selection follows real reference-record evidence
   (sample-reference-records ContactPointAddress, 3 real rows, Phase 0):
   City/State/Country/Name/IsDefault/IsThirdPartyAddress/IsUndeliverable
   were populated; Street, PostalCode, AddressType, UsageType,
   PreferenceRank, ActiveFromDate/ActiveToDate, BestTimeToContact*,
   Seasonal fields, and the LastChangeOfAddress/LastAddressStd geocoding
   fields were NOT -- a thin sample (n=3), but the only real evidence
   available, and this build's whole point is matching real shape rather
   than inventing a plausible-looking superset. IsPrimary is set
   deterministically (first address per Account, by _MockRowId), not
   from the Mock table's own random value -- real data showed IsPrimary
   True on 3/3, consistent with "the address" being primary by default
   when there's only one. */

DROP TABLE IF EXISTS [dbo].[ContactPointAddress_Load];

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
        m.Name, m.City, m.State, m.Country, m.IsDefault, m.IsThirdPartyAddress, m.IsUndeliverable,
        ap.Id AS AccountId,
        ROW_NUMBER() OVER (PARTITION BY ap.Id ORDER BY m._MockRowId) AS SeqWithinAccount
    FROM [dbo].[ContactPointAddress_Mock] m
    JOIN AccountPool ap ON ap.AccountSeq = ((m._MockRowId - 1) % ap.AccountCount) + 1
)
SELECT
    _MockRowId AS LoadId,
    'SNOWFAKE-CPA-' + CAST(_MockRowId AS VARCHAR(10)) AS MigrationID__c,
    AccountId AS ParentId,
    'Snowfake-' + Name AS Name,
    City,
    State,
    Country,
    IsDefault,
    IsThirdPartyAddress,
    IsUndeliverable,
    CASE WHEN SeqWithinAccount = 1 THEN 1 ELSE 0 END AS IsPrimary
INTO [dbo].[ContactPointAddress_Load]
FROM Assigned;
