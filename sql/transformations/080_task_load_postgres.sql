/* No ticket -- test/mock run, no ticket system in use for this exercise
   (hard rule 10). Postgres-flavored sibling of 040_task_load.sql -- same
   logic, ported to Postgres syntax, part of the Postgres methodology pass
   (roadmap #69). NOT a replacement for 040_task_load.sql -- see
   050_account_load_postgres.sql's header for the full explanation of why
   this sibling script exists and the quoting requirement it follows.

   WhatId is a genuinely polymorphic Salesforce lookup (confirmed live via
   describe(): ~90 possible target types, including both Account and
   Opportunity -- see validators/Task.md). generate-related-mock-data
   split Task generation into two independent cohorts (one nested under
   Account, one under Opportunity), tagging each row with a literal
   _ParentType discriminator -- this transform resolves WhatId with a CASE
   on that discriminator, same structure as the original (a plain single
   JOIN can't express this).

   This script can only be built AFTER Account_Load, Opportunity_Load,
   AND Contact_Load have each been loaded via a live bulkops insert at
   least once (same "Id" column dependency as 060/070's headers explain).

   Migration key MigrationID__c is regenerated from _MockRowId, same as
   the other Load tables. IsRecurrence/Recurrence* deliberately excluded
   -- see 040_task_load.sql's header; mock_data.py/snowfakery_data.py
   already skip generating them (_is_interdependent_field()), so
   Task_Mock never carries them in the first place here, unlike the
   original SQL Server pass's Task_Mock (built before that fix existed) --
   nothing to explicitly exclude in this SELECT list.

   SAMPLED to 27 rows (14 Account-cohort + 13 Opportunity-cohort), not the
   full Task_Mock table -- a real, confirmed tool limitation found live
   during this pass: generate-related-mock-data's --count for a nested/
   cohort child (Snowfakery's own count: field) is always PER-PARENT-
   INSTANCE, with no way to request a flat/absolute total for a
   polymorphic cohort child. --count Task=27 against 5 Accounts + 520
   Opportunities produced 14,175 rows (27 x 525), not 27 total -- far
   larger than this comparison pass intended. Sampling here (rather than
   regenerating) keeps genuine coverage of BOTH _ParentType cohorts, since
   the whole point of this script is the polymorphic WhatId CASE. */

DROP TABLE IF EXISTS dbo."Task_Load";

CREATE TABLE dbo."Task_Load" AS
SELECT
    m."_MockRowId" AS "LoadId",
    CAST(m."_MockRowId" AS VARCHAR(50)) AS "MigrationID__c",
    CASE m."_ParentType"
        WHEN 'Account' THEN acc_direct."Id"
        WHEN 'Opportunity' THEN opp."Id"
    END AS "WhatId",
    CASE
        WHEN m."_SecondaryParentRef_Contact" IS NOT NULL THEN con."Id"
    END AS "WhoId",
    CASE
        WHEN m."_SecondaryParentRef_Account" IS NOT NULL THEN acc_secondary."Id"
    END AS "REF_AccountId",
    m."Subject",
    m."ActivityDate",
    m."Status",
    m."Priority",
    m."Description",
    m."CallDurationInSeconds",
    m."CallType",
    m."CallDisposition",
    m."CallObject",
    m."ReminderDateTime",
    m."IsReminderSet"
FROM (
    (SELECT * FROM dbo."Task_Mock" WHERE "_ParentType" = 'Account' LIMIT 14)
    UNION ALL
    -- Excludes the 13 Opportunity LoadIds that failed earlier (pre-existing
    -- MigrationID__c collision with the original SQL Server dogfood pass,
    -- see this pass's own findings) -- otherwise an unlucky unordered LIMIT
    -- could sample only Tasks whose parent Opportunity never got a real Id,
    -- leaving WhatId NULL for the whole Opportunity-cohort half of the
    -- sample and defeating the point of exercising both CASE branches.
    (SELECT * FROM dbo."Task_Mock" WHERE "_ParentType" = 'Opportunity'
        AND "_ParentMockRef" NOT IN (SELECT "LoadId" FROM dbo."Opportunity_Load" WHERE "Id" IS NULL)
        LIMIT 13)
) m
LEFT JOIN dbo."Account_Load" acc_direct
    ON m."_ParentType" = 'Account' AND acc_direct."LoadId" = m."_ParentMockRef"
LEFT JOIN dbo."Opportunity_Load" opp
    ON m."_ParentType" = 'Opportunity' AND opp."LoadId" = m."_ParentMockRef"
LEFT JOIN dbo."Contact_Load" con
    ON con."LoadId" = m."_SecondaryParentRef_Contact"
LEFT JOIN dbo."Account_Load" acc_secondary
    ON acc_secondary."LoadId" = m."_SecondaryParentRef_Account";

/* REF_AccountId is a human-only, SQL-side audit column (hard rule 13,
   REF_ prefix) recording Task's own separate AccountId field's intended
   value for review -- NOT sent to Salesforce or flagged by bulkops'
   pre-flight check, since it's redundant with WhatId whenever
   _ParentType = 'Account' and only genuinely different (a real
   cross-reference) when _ParentType = 'Opportunity'. */
