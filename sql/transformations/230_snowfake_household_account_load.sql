/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 1 of
   11 (see the approved plan for the full sequence). Unlike the earlier
   NPSP-to-NPC PoC (090-220), this data has no real source system --
   it's generated fresh via `generate-related-mock-data Account Contact
   --count Account=8 --count Contact=1-3` (Hard Rule 11's explicit
   exception: framework-generated data may be carried to a full,
   completed load, unlike real client data) specifically to learn NPC's
   real target-data shape across its full fundraising surface, not just
   what a source system happened to map to.

   Builds HouseholdAccount_Load from dbo.Account_Mock -- one row per
   generated household. RecordTypeId resolved by DeveloperName via
   dbo.RecordTypeMap (hard rule 15, populated by `resolve-record-types
   Account --org target`) -- Household's real DeveloperName is literally
   "Household" (confirmed live; NOT to be confused with Business_Account,
   which is the real "Organization" RecordType despite the name --
   see okf/nonprofit-cloud/person-accounts-and-record-types.md).

   Every record's Name gets a literal "Snowfake-" prefix (per the user's
   own instruction) so this practice data stays visually identifiable in
   the org, alongside MigrationID__c as the real, load-bearing unique key
   (Hard Rules 4/7) -- there's no real source Id to reuse this time, so
   MigrationID__c is a synthetic value keyed off the Mock table's own
   row id.

   Field selection deliberately narrow -- same curated set the PoC's own
   090 script used (Name, Billing and Shipping address, Phone) plus
   Description and the NPC-specific Preferred_Contact_Method__c, both
   plausible for a human-entered household. Deliberately excludes the
   Mockaroo-generated business-shaped fields also present on Account_Mock
   (Industry, AnnualRevenue, NumberOfEmployees, TickerSymbol, Website,
   AccountNumber, Sic/SicDesc, Ownership) -- a real household a human
   creates through the NPC UI would never populate those. */

DROP TABLE IF EXISTS [dbo].[HouseholdAccount_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-HH-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    'Snowfake-' + m.Name AS Name,
    rt.Id AS RecordTypeId,
    m.BillingStreet,
    m.BillingCity,
    m.BillingState,
    m.BillingPostalCode,
    m.BillingCountry,
    m.ShippingStreet,
    m.ShippingCity,
    m.ShippingState,
    m.ShippingPostalCode,
    m.ShippingCountry,
    m.Phone,
    m.Description,
    m.Preferred_Contact_Method__c
INTO [dbo].[HouseholdAccount_Load]
FROM [dbo].[Account_Mock] m
CROSS JOIN (
    SELECT Id FROM [dbo].[RecordTypeMap]
    WHERE SobjectType = 'Account' AND DeveloperName = 'Household'
) rt;
