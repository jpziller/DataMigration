/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 4 of
   11. Builds PersonAccount_Load from dbo.Contact_Mock (10 fresh
   standalone Contact rows -- `generate-related-mock-data Contact
   --count Contact=10` -- deliberately generated as Contact shapes, then
   mapped onto Account's own Person*-prefixed fields, since a Person
   Account IS an Account row with RecordType = PersonAccount, no separate
   Contact record).

   RecordTypeId resolved via dbo.RecordTypeMap (DeveloperName =
   'PersonAccount', confirmed live). Name is deliberately never sent --
   the platform composes it itself from FirstName/LastName on a Person
   Account, same precedent as the earlier NPSP-to-NPC PoC's own
   100_npc_person_account_load.sql. Contact.Name isn't createable either
   way (compound field) -- see
   okf/nonprofit-cloud/name-field-createable-flag-quirk.md. "Snowfake-"
   prefix goes on LastName, the closest analog to a prefixed visible
   identity for a Person Account. */

DROP TABLE IF EXISTS [dbo].[PersonAccount_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-PA-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    rt.Id AS RecordTypeId,
    m.FirstName,
    'Snowfake-' + m.LastName AS LastName,
    m.Salutation,
    m.Phone,
    m.MailingStreet AS PersonMailingStreet,
    m.MailingCity AS PersonMailingCity,
    m.MailingState AS PersonMailingState,
    m.MailingPostalCode AS PersonMailingPostalCode,
    m.MailingCountry AS PersonMailingCountry,
    m.Email AS PersonEmail,
    m.MobilePhone AS PersonMobilePhone,
    m.HomePhone AS PersonHomePhone,
    m.Birthdate AS PersonBirthdate,
    m.Title AS PersonTitle,
    m.Department AS PersonDepartment,
    m.Description
INTO [dbo].[PersonAccount_Load]
FROM [dbo].[Contact_Mock] m
CROSS JOIN (
    SELECT Id FROM [dbo].[RecordTypeMap]
    WHERE SobjectType = 'Account' AND DeveloperName = 'PersonAccount'
) rt;
