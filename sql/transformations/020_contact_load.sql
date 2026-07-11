/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Builds Contact_Load from Contact_Mock joined to
   Account_Load on the Snowfakery bookkeeping key LoadId -- AccountId is
   resolved to the REAL Salesforce Id written back onto Account_Load by
   the Account bulkops load, not a synthetic mock reference. Run this
   script a second time (rebuild) after the Account load completes, so
   AccountId is populated instead of NULL.

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   Account_Load -- see 010_account_load.sql's header. */

DROP TABLE IF EXISTS "dbo"."Contact_Load";

CREATE TABLE "dbo"."Contact_Load" AS
SELECT
    m._MockRowId AS LoadId,
    CAST(m._MockRowId AS TEXT) AS MigrationID__c,
    a."Id" AS AccountId,
    m.LastName,
    m.FirstName,
    m.Salutation,
    m.OtherStreet,
    m.OtherCity,
    m.OtherState,
    m.OtherPostalCode,
    m.OtherCountry,
    m.OtherGeocodeAccuracy,
    m.MailingStreet,
    m.MailingCity,
    m.MailingState,
    m.MailingPostalCode,
    m.MailingCountry,
    m.MailingGeocodeAccuracy,
    m.Phone,
    m.Fax,
    m.MobilePhone,
    m.HomePhone,
    m.OtherPhone,
    m.AssistantPhone,
    m.Email,
    m.Title,
    m.Department,
    m.AssistantName,
    m.LeadSource,
    m.Birthdate,
    m.Description,
    m.EmailBouncedReason,
    m.EmailBouncedDate,
    m.ContactSource,
    m.Level__c,
    m.Languages__c
FROM "dbo"."Contact_Mock" m
JOIN "dbo"."Account_Load" a ON a.LoadId = m._ParentMockRef;

ALTER TABLE "dbo"."Contact_Load" ADD "Id" TEXT NULL;
ALTER TABLE "dbo"."Contact_Load" ADD "Error" TEXT NULL;
