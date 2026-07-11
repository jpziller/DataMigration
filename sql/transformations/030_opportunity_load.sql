/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Builds Opportunity_Load from Opportunity_Mock joined
   to Contact_Load (primary parent, via LoadId) and Account_Load
   (secondary/direct parent reference, via LoadId) -- both ContactId and
   AccountId are resolved to REAL Salesforce Ids written back by their
   own bulkops loads. Run this script a second time (rebuild) after the
   Contact load completes, so ContactId/AccountId are populated instead
   of NULL.

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   Account_Load/Contact_Load -- see 010_account_load.sql's header. */

DROP TABLE IF EXISTS "dbo"."Opportunity_Load";

CREATE TABLE "dbo"."Opportunity_Load" AS
SELECT
    m._MockRowId AS LoadId,
    CAST(m._MockRowId AS TEXT) AS MigrationID__c,
    c."Id" AS ContactId,
    acc."Id" AS AccountId,
    m.IsPrivate,
    m.Name,
    m.Description,
    m.StageName,
    m.Amount,
    m.Probability,
    m.TotalOpportunityQuantity,
    m.CloseDate,
    m.Type,
    m.NextStep,
    m.LeadSource,
    m.ForecastCategoryName,
    m.DeliveryInstallationStatus__c,
    m.TrackingNumber__c,
    m.OrderNumber__c,
    m.CurrentGenerators__c,
    m.MainCompetitors__c
FROM "dbo"."Opportunity_Mock" m
JOIN "dbo"."Contact_Load" c ON c.LoadId = m._ParentMockRef
JOIN "dbo"."Account_Load" acc ON acc.LoadId = m."_SecondaryParentRef_Account";

ALTER TABLE "dbo"."Opportunity_Load" ADD "Id" TEXT NULL;
ALTER TABLE "dbo"."Opportunity_Load" ADD "Error" TEXT NULL;
