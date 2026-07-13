/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Builds Task_Load from Task_Mock -- the interesting case
   here is WhatId, a genuinely polymorphic Salesforce lookup (confirmed
   live via describe(): ~90 possible target types, including both Account
   and Opportunity -- see validators/Task.md). generate-related-mock-data
   split Task generation into two independent cohorts (one nested under
   Account, one under Opportunity), tagging each row with a literal
   _ParentType discriminator -- this transform resolves WhatId with a
   CASE on that discriminator, joining whichever Load table's real Id
   actually applies per row. A plain single JOIN can't express this: a
   given Task row's WhatId is either an Account Id or an Opportunity Id,
   never both, and never resolvable without knowing which cohort
   produced it.

   Run this script a second time (rebuild) after BOTH the Account and
   Opportunity loads have completed, so WhatId is populated instead of
   NULL either way.

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   the other Load tables -- see 010_account_load.sql's header.

   IsRecurrence/Recurrence* deliberately excluded: confirmed live that
   Salesforce cross-validates this whole field cluster as one interdependent
   unit (e.g. "ActivityDate for a recurring task", "Day of week must be
   blank for type Recurs Monthly", "Choose a type of date for repeating
   this task") -- independently-random mock values for each field can't
   satisfy that, so mock_data.py/snowfakery_data.py now skip generating
   them at all (see _is_interdependent_field()); Task_Mock still carries
   them from before that fix, so this transform explicitly leaves them out
   of the SELECT list rather than sending Salesforce values it will
   reject.

   Ported to real T-SQL -- see 010_account_load.sql's header for why. */

DROP TABLE IF EXISTS [dbo].[Task_Load];

SELECT
    m._MockRowId AS LoadId,
    CAST(m._MockRowId AS NVARCHAR(50)) AS MigrationID__c,
    CASE m._ParentType
        WHEN 'Account' THEN acc_direct.Id
        WHEN 'Opportunity' THEN opp.Id
    END AS WhatId,
    CASE
        WHEN m._SecondaryParentRef_Contact IS NOT NULL THEN con.Id
    END AS WhoId,
    CASE
        WHEN m._SecondaryParentRef_Account IS NOT NULL THEN acc_secondary.Id
    END AS REF_AccountId,
    m.Subject,
    m.ActivityDate,
    m.Status,
    m.Priority,
    m.Description,
    m.CallDurationInSeconds,
    m.CallType,
    m.CallDisposition,
    m.CallObject,
    m.ReminderDateTime,
    m.IsReminderSet
INTO [dbo].[Task_Load]
FROM [dbo].[Task_Mock] m
LEFT JOIN [dbo].[Account_Load] acc_direct
    ON m._ParentType = 'Account' AND acc_direct.LoadId = m._ParentMockRef
LEFT JOIN [dbo].[Opportunity_Load] opp
    ON m._ParentType = 'Opportunity' AND opp.LoadId = m._ParentMockRef
LEFT JOIN [dbo].[Contact_Load] con
    ON con.LoadId = m._SecondaryParentRef_Contact
LEFT JOIN [dbo].[Account_Load] acc_secondary
    ON acc_secondary.LoadId = m._SecondaryParentRef_Account;

/* REF_AccountId is a human-only, SQL-side audit column (hard rule 13,
   REF_ prefix) recording Task's own separate AccountId field's intended
   value for review -- NOT sent to Salesforce or flagged by bulkops'
   pre-flight check, since it's redundant with WhatId whenever _ParentType
   = 'Account' and only genuinely different (a real cross-reference) when
   _ParentType = 'Opportunity'. */
