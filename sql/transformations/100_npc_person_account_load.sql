/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md).

   Builds PersonAccount_Load from dbo.Contact. Person Accounts are
   mandatory in AFNP (migration guide sec 2.3.1). A Contact's individual
   fields map onto the Person* fields exposed on Account when RecordTypeId
   is the PersonAccount type -- there is NO separate target Contact insert:
   Salesforce auto-creates the paired "shadow" Contact itself once this
   Account row lands (the Account<->Contact shadow is now recorded in the
   committed cloud data-shape profiles for Account and Contact).

   This Person Account is NOT linked to its household Account via any field
   on Account itself -- that relationship is the household-membership
   AccountContactRelation (110), which needs this load's real, written-back
   Account Ids AND each new person account's own auto-generated
   PersonContactId (only available after this load actually runs against
   the target org -- see 110's own header). RecordTypeId resolved by
   DeveloperName via dbo.RecordTypeMap (hard rule 15). */

DROP TABLE IF EXISTS [dbo].[PersonAccount_Load];

SELECT
    c.Id AS LoadId,
    c.Id AS MigrationID__c,
    rt.Id AS RecordTypeId,
    c.FirstName,
    c.LastName,
    c.Salutation,
    c.MailingStreet AS PersonMailingStreet,
    c.MailingCity AS PersonMailingCity,
    c.MailingState AS PersonMailingState,
    c.MailingPostalCode AS PersonMailingPostalCode,
    c.MailingCountry AS PersonMailingCountry,
    c.Phone AS PersonHomePhone,
    c.MobilePhone AS PersonMobilePhone,
    c.Email AS PersonEmail,
    c.Birthdate AS PersonBirthdate
INTO [dbo].[PersonAccount_Load]
FROM [dbo].[Contact] c
CROSS JOIN (
    SELECT Id FROM [dbo].[RecordTypeMap]
    WHERE SobjectType = 'Account' AND DeveloperName = 'PersonAccount'
) rt;
