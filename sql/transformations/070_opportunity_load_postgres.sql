/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Postgres-flavored sibling of 030_opportunity_load.sql --
   same logic, ported to Postgres syntax, part of the Postgres methodology
   pass (roadmap #69). NOT a replacement for 030_opportunity_load.sql --
   see 050_account_load_postgres.sql's header for the full explanation of
   why this sibling script exists and the quoting requirement it follows.

   Builds Opportunity_Load from Opportunity_Mock joined to Contact_Load
   (primary parent, via LoadId) and Account_Load (secondary/direct parent
   reference, via LoadId) -- both ContactId and AccountId are resolved to
   REAL Salesforce Ids written back by their own bulkops loads. This
   script can only be built AFTER both Account_Load and Contact_Load have
   each been loaded via a live bulkops insert at least once (same "Id"
   column dependency as 060_contact_load_postgres.sql's header explains).

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   Account_Load/Contact_Load. Opportunity is deliberately a child of
   Contact (primary parent) with Account as a secondary parent here --
   preserved unchanged from the original brief's structure, not a
   standard Account-first hierarchy. */

DROP TABLE IF EXISTS dbo."Opportunity_Load";

CREATE TABLE dbo."Opportunity_Load" AS
SELECT
    m."_MockRowId" AS "LoadId",
    CAST(m."_MockRowId" AS VARCHAR(50)) AS "MigrationID__c",
    c."Id" AS "ContactId",
    acc."Id" AS "AccountId",
    m."IsPrivate",
    m."Name",
    m."Description",
    m."StageName",
    m."Amount",
    m."Probability",
    m."TotalOpportunityQuantity",
    m."CloseDate",
    m."Type",
    m."NextStep",
    m."LeadSource",
    m."ForecastCategoryName",
    m."DeliveryInstallationStatus__c",
    m."TrackingNumber__c",
    m."OrderNumber__c",
    m."CurrentGenerators__c",
    m."MainCompetitors__c"
FROM dbo."Opportunity_Mock" m
JOIN dbo."Contact_Load" c ON c."LoadId" = m."_ParentMockRef"
JOIN dbo."Account_Load" acc ON acc."LoadId" = m."_SecondaryParentRef_Account";
