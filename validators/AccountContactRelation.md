---
type: ObjectValidator
title: AccountContactRelation validator
description: Object-specific findings for AccountContactRelation
  (Nonprofit Cloud/AFNP) -- IsIncludedInGroup/IsPrimaryMember are the real
  household-membership signal a migration must set, not just AccountId/
  ContactId; discovered as the likely root cause of migrated household
  data appearing to have no visible grouping.
tags: [object-validator, account-contact-relation, nonprofit-cloud, afnp, npsp-to-npc, household]
timestamp: "2026-07-18"
---
# AccountContactRelation validator

## IsIncludedInGroup/IsPrimaryMember are the real membership signal, not just AccountId/ContactId
**Found:** 2026-07-18, NPSP-to-NPC migration proof-of-concept -- a second
architect reviewing the live `NPC_TARGET_v2` org reported not seeing any
household grouping ("PartyRelationshipGroup") for data that came from an
NPSP household, and suspected something was wrong. Direct query confirmed
all 8 migrated `PartyRelationshipGroup` records genuinely exist, correctly
linked via `AccountId` to their household Accounts -- so the record
existence itself wasn't the problem. Using `sample-reference-records`
against 10 real, non-migrated `AccountContactRelation` records in the same
org showed `IsIncludedInGroup` populated 10/10 (mixed True/False) and
`IsPrimaryMember` populated 10/10 -- neither of which this migration's own
`110_npc_accountcontactrelation_load.sql` originally set (it only sent
`AccountId`/`ContactId`/`IsActive`).
**Why this matters:** `Account` itself has no direct lookup field back to
`PartyRelationshipGroup` (confirmed via `describe()` -- grepped every field
name for "group"/"party"/"household", found nothing). The relationship is
one-directional (`PartyRelationshipGroup.AccountId` -> `Account`), so a
household's members are surfaced through `AccountContactRelation`, not
through the group record itself. Without `IsIncludedInGroup = true`, the
standard household UI grouping has no signal that a given Contact is
actually "in" the Account's group -- so even with a perfectly valid
`PartyRelationshipGroup` record on file, the migrated household wouldn't
visually group its members the way a real, human-created household does.
**What to do:** set `IsIncludedInGroup = true` for every row a household
migration synthesizes (every such row genuinely represents a real member).
Set `IsPrimaryMember = true` for exactly one member per household, chosen
by NPSP's own `npo02__Household_Naming_Order__c` (lower value = named
first/more senior in the household) with a deterministic `Contact.Id`
tiebreak when the naming order is null or tied across all members of one
household.
**What was deliberately left unset:** `IsPrimaryGroup` (the sample showed
only `False` across all 10 rows -- no confident evidence either way for
what a "primary group" designation should be here) and `Roles` (a
free-form multipicklist with no natural source value on this migration's
own data). Per Hard Rule 11, don't invent a value just because a field
exists and the platform would accept one -- leave it for a real client
conversation instead.
**Executable check:** none yet -- this is a migration-design decision
(which fields to derive and how), not a pre-load consistency check the
way Hard Rules 6/7/12/15 are.
