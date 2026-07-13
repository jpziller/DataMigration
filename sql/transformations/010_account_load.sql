/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Builds Account_Load from the Snowfakery-generated
   Account_Mock table. Migration key MigrationID__c is regenerated from
   _MockRowId (guaranteed unique), NOT copied from Account_Mock's own
   Snowfakery-generated value for that field.

   FLS for MigrationID__c on Account/Contact/Opportunity/Task is granted
   via the MigrationFieldAccess permission set (force-app/main/default/
   permissionsets/MigrationFieldAccess.permissionset-meta.xml), not the
   Admin profile -- see CLAUDE.md hard rule 8.

   Ported to real T-SQL from an earlier SQLite-flavored draft (this
   project is configured for the mssql backend) -- CREATE TABLE ... AS
   SELECT isn't valid T-SQL syntax at all; SELECT ... INTO is the
   equivalent. Id/Error columns are no longer added here -- bulk_op()'s
   own writeback already adds them automatically when missing (see
   bulkops.py's _writeback_inplace), so doing it here too was always
   redundant. */

DROP TABLE IF EXISTS [dbo].[Account_Load];

SELECT
    _MockRowId AS LoadId,
    CAST(_MockRowId AS NVARCHAR(50)) AS MigrationID__c,
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
INTO [dbo].[Account_Load]
FROM [dbo].[Account_Mock];
