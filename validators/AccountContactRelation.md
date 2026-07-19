---
type: ObjectValidator
title: AccountContactRelation validator
description: Object-specific findings for AccountContactRelation
  (Nonprofit Cloud/AFNP) -- IsIncludedInGroup/IsPrimaryMember are the real
  household-membership signal a migration must set, not just AccountId/
  ContactId; the platform auto-creates this row itself on Contact insert,
  so it must be updated, never inserted.
tags: [object-validator, account-contact-relation, nonprofit-cloud, afnp, npsp-to-npc, household, auto-created-child-record]
timestamp: "2026-07-19"
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

## Salesforce auto-creates the row itself -- never insert, always update
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build -- an explicit `insert` of AccountContactRelation collided
with a real, already-existing row (submitted 16, succeeded 0, failed 0,
no error). The platform auto-creates an AccountContactRelation
(`IsDirect = true`) the instant a Contact is inserted with a real
`AccountId` -- the same auto-creation pattern already known for
`GiftCommitmentSchedule` (see [GiftCommitmentSchedule.md](GiftCommitmentSchedule.md)).
**What to do:** never insert this object explicitly when its Account and
Contact were both just loaded by this same migration. Replicate the real
row first (`replicate AccountContactRelation --where "IsDirect = true"`),
join it back by (AccountId, ContactId), and `update` it with only the
fields the auto-creation doesn't set (IsIncludedInGroup/IsPrimaryMember
above). Don't send `MigrationID__c` on this update -- the row wasn't
created by this migration, so stamping a migration key on it falsely
claims it was; Hard Rules 7/12 don't apply here either, since matching is
by the real Id (already known), not a fingerprint/external-id lookup.

## Update calls need `--fingerprint-columns Id`, or a boolean field can silently corrupt the Load table's own Id column
**Found:** same session. `bulk_op()`'s default result-matching
fingerprints every sent column -- including the boolean
IsIncludedInGroup/IsPrimaryMember fields here. Salesforce can echo a sent
boolean back in a different string representation than pandas' own CSV
export used, silently breaking the fingerprint match for the whole row
(reported succeeded=0/failed=0 even though the real DML fully succeeded,
confirmed via direct query). Worse: this also surfaced a real bug in
`bulk_op()`'s in-place writeback (`_writeback_inplace()` in
`bulkops.py`, fixed this session) -- on a failed fingerprint match, it
unconditionally overwrote `id_column` with NULL, even when the caller
had supplied a real, correct Id going in (exactly this case, since the
Id was already known via the replicate + join above). Fixed to
`COALESCE` instead of overwrite, so a failed match no longer destroys a
pre-existing Id. **What to do:** always pass `--fingerprint-columns Id`
for an update where Id is already known ahead of time, rather than
relying on the default (every sent column).

## Clearing a field via Bulk API 2.0 CSV needs the literal `#N/A`, not a blank cell
**Found:** same session, correcting the MigrationID__c mistake above. An
empty CSV cell on an update is a no-op in Bulk API 2.0 -- it does NOT set
the field to null. Only the literal string `#N/A` in that cell does.
