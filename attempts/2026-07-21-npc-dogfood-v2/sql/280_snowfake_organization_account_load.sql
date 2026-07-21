/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 3 of
   11. Builds OrganizationAccount_Load from dbo.Account_Mock (5 fresh
   rows from `generate-related-mock-data Account --count Account=5`,
   overwriting 230's now-already-consumed household rows).

   RecordTypeId resolved via dbo.RecordTypeMap -- the real "Organization"
   RecordType's DeveloperName is Business_Account (Name: "Organization
   Business Account"), NOT Org_Business_Account (Name: "Business
   Account", a different, generic default type) -- a real naming trap
   confirmed live and documented in
   okf/nonprofit-cloud/person-accounts-and-record-types.md. Unlike the
   household load (230), business-shaped fields (Website, Industry,
   AnnualRevenue, NumberOfEmployees, Phone) ARE plausible here and are
   included. */

DROP TABLE IF EXISTS [dbo].[OrganizationAccount_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-ORG-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
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
    m.Website,
    m.Industry,
    m.AnnualRevenue,
    m.NumberOfEmployees,
    m.Description
INTO [dbo].[OrganizationAccount_Load]
FROM [dbo].[Account_Mock] m
CROSS JOIN (
    SELECT Id FROM [dbo].[RecordTypeMap]
    WHERE SobjectType = 'Account' AND DeveloperName = 'Business_Account'
) rt;
