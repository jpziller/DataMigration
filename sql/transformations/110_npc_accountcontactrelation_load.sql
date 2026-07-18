/* No ticket -- no ticket system in use for this project (hard rule 10).

   NPSP-to-NPC migration proof-of-concept, step 3 of ~14. "New Data" per
   the official field-mapping workbook's own taxonomy (no direct NPSP
   source field correspondence -- auto-map was skipped for this object,
   see PR discussion) -- this is a synthesized relationship record, not a
   1:1 field carry-over.

   Links each household Account (090, already loaded) to its person
   account's own auto-generated "shadow" Contact (100, already loaded --
   PersonContactId only exists on the target org's Account row AFTER that
   insert actually ran, hence this being its own later step rather than
   folded into 090/100). dbo.Account currently holds a fresh, target-side
   replicate of the 8 just-created Person Accounts (re-pulled specifically
   for PersonContactId) -- NOT the original source household Accounts
   090 already consumed; re-running 090 after this point would need a
   fresh source-side Account replicate first.

   dbo.Contact (source-side, untouched since Phase 2) is the join spine:
   Contact.AccountId is the NPSP household Account's own source Id,
   matching HouseholdAccount_Load.LoadId; Contact.Id is the source Contact
   Id, matching the target Person Account's MigrationID__c (set in 100).

   IsIncludedInGroup/IsPrimaryMember (added 2026-07-18, architect review
   finding -- likely root cause of "no household grouping visible" on the
   live org): sample-reference-records against 10 real, non-migrated
   AccountContactRelation records showed IsIncludedInGroup populated 10/10
   and IsPrimaryMember populated 10/10, neither of which this script
   originally set at all. Without IsIncludedInGroup = true, the standard
   household UI grouping has no signal that a person is actually "in" the
   Account's group, even though the AccountContactRelation and
   PartyRelationshipGroup (120) records both genuinely exist -- Account
   itself has no direct lookup field back to PartyRelationshipGroup
   (confirmed via describe()), so this membership flag is the real
   mechanism, not a page-layout/related-list issue.
   IsIncludedInGroup = true for every row here: every one of these rows IS
   a real household member, by construction.
   IsPrimaryMember: exactly one true per household, chosen by NPSP's own
   npo02__Household_Naming_Order__c (lower = named first/more senior),
   falling back to Contact.Id when the naming order is null/tied, for a
   deterministic single primary per household.
   IsPrimaryGroup and Roles are deliberately left unset -- the same sample
   didn't give confident evidence for either (IsPrimaryGroup showed only
   False across the sample; Roles is a free-form multipicklist with no
   natural source value) -- see Hard Rule 11 and
   validators/AccountContactRelation.md. */

DROP TABLE IF EXISTS [dbo].[AccountContactRelation_Load];

SELECT
    c.Id AS LoadId,
    c.Id AS MigrationID__c,
    ha.Id AS AccountId,
    pa.PersonContactId AS ContactId,
    1 AS IsActive,
    1 AS IsIncludedInGroup,
    CASE WHEN ROW_NUMBER() OVER (
        PARTITION BY ha.LoadId
        ORDER BY CASE WHEN c.npo02__Household_Naming_Order__c IS NULL THEN 1 ELSE 0 END,
                 c.npo02__Household_Naming_Order__c,
                 c.Id
    ) = 1 THEN 1 ELSE 0 END AS IsPrimaryMember
INTO [dbo].[AccountContactRelation_Load]
FROM [dbo].[Contact] c
JOIN [dbo].[HouseholdAccount_Load] ha ON ha.LoadId = c.AccountId
JOIN [dbo].[Account] pa ON pa.MigrationID__c = c.Id;
