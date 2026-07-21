/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPC fundraising/donor-management Snowfakery dogfood recipe, group 1 of
   11 -- companion to 230. Builds Contact_Load from dbo.Contact_Mock,
   resolving the real AccountId via the Mock table's own _ParentMockRef
   bookkeeping column (an integer pointing at HouseholdAccount_Load's
   LoadId, not a real Salesforce Id -- see snowfakery_data.py's own
   module docstring) joined against 230's already-built Load table.

   Contact.Name isn't createable (a compound field composed by the
   platform from FirstName/LastName -- confirmed live, same finding as
   okf/nonprofit-cloud/name-field-createable-flag-quirk.md), so the
   "Snowfake-" prefix goes on LastName instead -- the closest analog to
   prefixing a household member's own visible identity.

   Runs AFTER 230's HouseholdAccount_Load has actually been bulkops-loaded
   to the target org -- ha.Id below is the REAL writeback Salesforce Id
   (bulk_op()'s own in-place writeback, hard rule 4), not a Mock-table
   bookkeeping value. Building this before that load runs fails with
   "Invalid column name 'Id'" since no such column exists yet -- confirmed
   live; every following group in this recipe repeats the same
   build -> bulkops load -> build-next-dependent-object pattern. */

DROP TABLE IF EXISTS [dbo].[Contact_Load];

SELECT
    m._MockRowId AS LoadId,
    'SNOWFAKE-CONTACT-' + CAST(m._MockRowId AS VARCHAR(10)) AS MigrationID__c,
    ha.Id AS AccountId,
    m.FirstName,
    'Snowfake-' + m.LastName AS LastName,
    m.Salutation,
    m.Title,
    m.Department,
    m.Email,
    m.Phone,
    m.MobilePhone,
    m.HomePhone,
    m.Birthdate,
    m.Description,
    m.MailingStreet,
    m.MailingCity,
    m.MailingState,
    m.MailingPostalCode,
    m.MailingCountry
INTO [dbo].[Contact_Load]
FROM [dbo].[Contact_Mock] m
JOIN [dbo].[HouseholdAccount_Load] ha ON ha.LoadId = m._ParentMockRef;
