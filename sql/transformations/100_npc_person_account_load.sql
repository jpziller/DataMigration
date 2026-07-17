/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 2 of ~14.

   Builds PersonAccount_Load from dbo.Contact -- the 8 seeded Contacts.
   Person Accounts are mandatory in AFNP (migration guide sec 2.3.1 --
   see okf/npsp-to-npc/new-org-vs-in-place.md); confirmed live this org
   has Person Accounts enabled (Account.IsPersonAccount/PersonContactId
   exist) and a real PersonAccount RecordType. A Contact's individual
   fields map onto the Person* fields exposed directly on Account when
   RecordTypeId is the PersonAccount type -- there is no separate target
   Contact insert for this step; Salesforce auto-creates the paired
   "shadow" Contact record itself once this Account row lands.

   This Person Account is NOT linked to its household Account via any
   field on Account itself -- that relationship is expressed via
   AccountContactRelation (step 110), which needs this load's real,
   written-back Account Ids AND each new person account's own
   auto-generated PersonContactId (not available until after this load
   actually runs against the target org -- see 110's own header for the
   two-pass requery this implies).

   RecordTypeId resolved by DeveloperName via dbo.RecordTypeMap (hard rule
   15). Migration key MigrationID__c is the source Contact's real
   Salesforce Id, same convention as 090. */

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
