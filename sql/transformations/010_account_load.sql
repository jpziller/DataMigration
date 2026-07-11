/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Builds Account_Load from the Snowfakery-generated
   Account_Mock table. Migration key MigrationID__c is regenerated from
   _MockRowId (guaranteed unique), NOT copied from Account_Mock's own
   Snowfakery-generated value for that field.

   FLS for MigrationID__c on Account/Contact/Opportunity/Task is granted
   via the MigrationFieldAccess permission set (force-app/main/default/
   permissionsets/MigrationFieldAccess.permissionset-meta.xml), not the
   Admin profile -- see CLAUDE.md hard rule 8. */

DROP TABLE IF EXISTS "dbo"."Account_Load";

CREATE TABLE "dbo"."Account_Load" AS
SELECT
    _MockRowId AS LoadId,
    CAST(_MockRowId AS TEXT) AS MigrationID__c,
    Name,
    Type,
    BillingStreet,
    BillingCity,
    BillingState,
    BillingPostalCode,
    BillingCountry,
    BillingGeocodeAccuracy,
    ShippingStreet,
    ShippingCity,
    ShippingState,
    ShippingPostalCode,
    ShippingCountry,
    ShippingGeocodeAccuracy,
    Phone,
    Fax,
    AccountNumber,
    Website,
    Sic,
    Industry,
    AnnualRevenue,
    NumberOfEmployees,
    Ownership,
    TickerSymbol,
    Description,
    Rating,
    Site,
    AccountSource,
    DunsNumber,
    Tradestyle,
    NaicsCode,
    NaicsDesc,
    YearStarted,
    SicDesc,
    CustomerPriority__c,
    SLA__c,
    Active__c,
    NumberofLocations__c,
    UpsellOpportunity__c,
    SLASerialNumber__c,
    SLAExpirationDate__c
FROM "dbo"."Account_Mock";

ALTER TABLE "dbo"."Account_Load" ADD "Id" TEXT NULL;
ALTER TABLE "dbo"."Account_Load" ADD "Error" TEXT NULL;
