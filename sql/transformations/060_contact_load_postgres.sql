/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Postgres-flavored sibling of 020_contact_load.sql --
   same logic, ported to Postgres syntax, part of the Postgres methodology
   pass (roadmap #69). NOT a replacement for 020_contact_load.sql -- see
   050_account_load_postgres.sql's header for the full explanation of why
   this sibling script exists and the quoting requirement it follows.

   Builds Contact_Load from Contact_Mock joined to Account_Load on the
   Snowfakery bookkeeping key LoadId -- AccountId is resolved to the REAL
   Salesforce Id written back onto Account_Load by the Account bulkops
   load, not a synthetic mock reference. This script can only be built
   (the JOIN needs a real "Id" column on Account_Load, added by
   bulk_op()'s own writeback -- see 010_account_load.sql's header) AFTER
   the Account_Load table has been loaded via a live bulkops insert at
   least once.

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   Account_Load -- see 050_account_load_postgres.sql's header. */

DROP TABLE IF EXISTS dbo."Contact_Load";

CREATE TABLE dbo."Contact_Load" AS
SELECT
    m."_MockRowId" AS "LoadId",
    CAST(m."_MockRowId" AS VARCHAR(50)) AS "MigrationID__c",
    a."Id" AS "AccountId",
    m."LastName",
    m."FirstName",
    m."Salutation",
    m."OtherStreet",
    m."OtherCity",
    m."OtherState",
    m."OtherPostalCode",
    m."OtherCountry",
    m."OtherGeocodeAccuracy",
    m."MailingStreet",
    m."MailingCity",
    m."MailingState",
    m."MailingPostalCode",
    m."MailingCountry",
    m."MailingGeocodeAccuracy",
    m."Phone",
    m."Fax",
    m."MobilePhone",
    m."HomePhone",
    m."OtherPhone",
    m."AssistantPhone",
    m."Email",
    m."Title",
    m."Department",
    m."AssistantName",
    m."LeadSource",
    m."Birthdate",
    m."Description",
    m."EmailBouncedReason",
    m."EmailBouncedDate",
    m."ContactSource",
    m."Level__c",
    m."Languages__c"
FROM dbo."Contact_Mock" m
JOIN dbo."Account_Load" a ON a."LoadId" = m."_ParentMockRef";
