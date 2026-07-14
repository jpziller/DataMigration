/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Postgres-flavored sibling of 010_account_load.sql --
   same logic, ported to Postgres syntax (CREATE TABLE ... AS SELECT
   instead of SELECT ... INTO; VARCHAR instead of NVARCHAR) to prove the
   migration methodology genuinely is backend-agnostic past the raw SQL
   transform authorship itself (roadmap #69, the Postgres methodology
   pass). NOT a replacement for 010_account_load.sql -- that script
   remains the real SQL Server version; this one exists only for this
   one-off Postgres pass. script_filename_for()'s own "highest-numbered
   match wins" resolution would otherwise present this as canonical for
   Account even when running mssql -- flagging that explicitly here for
   any future reader.

   Builds Account_Load from the Snowfakery-generated Account_Mock table.
   Migration key MigrationID__c is regenerated from _MockRowId (guaranteed
   unique), NOT copied from Account_Mock's own Snowfakery-generated value
   for that field.

   Every column reference is double-quoted here, unlike this framework's
   own internal tables (BulkOpsLog etc., deliberately left bare this
   session to match the codebase's dominant convention for those).
   Postgres folds an unquoted identifier to lowercase both at CREATE
   TABLE time and on read, but Account_Mock's own columns were created
   quoted (mock_data.py/snowfakery_data.py both build DDL via
   d.quote_ident()) and bulk_op()'s own pre-flight check compares this
   table's columns against Salesforce's real, exact-case field API names
   -- so every reference here has to preserve exact case too, on both the
   read (Account_Mock) and write (Account_Load) side.

   FLS for MigrationID__c on Account/Contact/Opportunity/Task is granted
   via the MigrationFieldAccess permission set (force-app/main/default/
   permissionsets/MigrationFieldAccess.permissionset-meta.xml), not the
   Admin profile -- see CLAUDE.md hard rule 8. */

DROP TABLE IF EXISTS dbo."Account_Load";

CREATE TABLE dbo."Account_Load" AS
SELECT
    "_MockRowId" AS "LoadId",
    CAST("_MockRowId" AS VARCHAR(50)) AS "MigrationID__c",
    "Name",
    "Type",
    "BillingStreet",
    "BillingCity",
    "BillingState",
    "BillingPostalCode",
    "BillingCountry",
    "BillingGeocodeAccuracy",
    "ShippingStreet",
    "ShippingCity",
    "ShippingState",
    "ShippingPostalCode",
    "ShippingCountry",
    "ShippingGeocodeAccuracy",
    "Phone",
    "Fax",
    "AccountNumber",
    "Website",
    "Sic",
    "Industry",
    "AnnualRevenue",
    "NumberOfEmployees",
    "Ownership",
    "TickerSymbol",
    "Description",
    "Rating",
    "Site",
    "AccountSource",
    "DunsNumber",
    "Tradestyle",
    "NaicsCode",
    "NaicsDesc",
    "YearStarted",
    "SicDesc",
    "CustomerPriority__c",
    "SLA__c",
    "Active__c",
    "NumberofLocations__c",
    "UpsellOpportunity__c",
    "SLASerialNumber__c",
    "SLAExpirationDate__c"
FROM dbo."Account_Mock";
