/* No ticket -- no ticket system in use for this project (hard rule 10).

   Canonical NPSP-to-NPC starter kit (real-data-validated 2026-07-27 --
   see okf/npsp-to-npc/reference-implementation.md). The occasion for a
   CORRECTION to the rebuild plan
   (okf/npsp-to-npc/sample-data-learnings-for-migration.md, finding 1).

   The rebuild plan initially said "make ACR doc-only (mirror 250)". That
   is WRONG for the NPSP household case, and reconciling it is exactly why
   a fresh build beats blind reuse. There are TWO different
   AccountContactRelation records here:

   1. The IsDirect = true SELF-relationship (Person Account <-> its own
      auto-created shadow Contact). The platform auto-creates this the
      instant the Person Account (100) is inserted; the sample-data build
      correctly leaves it untouched (sql/transformations/250 is doc-only),
      and real IsDirect=true rows are IsIncludedInGroup=False /
      IsPrimaryMember=False. THIS build never inserts or updates it either.

   2. The IsDirect = false HOUSEHOLD-MEMBERSHIP relationship (household
      Account -> each member's shadow Contact). This is NOT auto-created --
      it is the mechanism that makes the standard household grouping
      actually show (2026-07-18 architect-review finding: without
      IsIncludedInGroup=true there is no signal a person is "in" the
      household group; Account has no direct lookup back to
      PartyRelationshipGroup). The sample-data build never exercised this
      because its synthetic data had no shared multi-member households --
      so its "doc-only" conclusion does NOT transfer here.

   This script inserts ONLY record type 2 (household membership). It joins
   the source household (Contact.AccountId -> HouseholdAccount_Load.LoadId)
   to each person account's own PersonContactId (target-side replicate of
   the 020 load; dbo.Account here holds the freshly re-pulled Person
   Accounts, NOT the source households 010 consumed).

   OPEN QUESTION (README): IsIncludedInGroup=true + one IsPrimaryMember per
   household is the PoC's validated logic, but confirm the IsDirect=false
   membership field shape against a real org with genuine multi-member
   households before promotion. IsPrimaryMember picks one per household by
   NPSP's own npo02__Household_Naming_Order__c (lower = named first),
   falling back to Contact.Id for a deterministic single primary.
   IsPrimaryGroup and Roles left unset (no confident evidence -- hard rule
   11, validators/AccountContactRelation.md). */

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
