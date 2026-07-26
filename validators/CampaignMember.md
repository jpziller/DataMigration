---
type: ObjectValidator
title: CampaignMember validator
description: Object-specific findings for CampaignMember (Nonprofit Cloud/
  AFNP and standard). Its transform can reference a Person Account's
  platform-created shadow Contact via PersonContactId read from the
  replicated dbo.Account snapshot -- which must be re-replicated after
  Person Accounts load, or those members fail INVALID_CROSS_REFERENCE_KEY.
  ContactId is create-only (not updateable), so a failed load can't be
  upserted -- delete and re-insert instead.
tags: [object-validator, campaign-member, nonprofit-cloud, afnp, person-account, stale-snapshot, reset]
timestamp: "2026-07-26"
---
# CampaignMember validator

## ContactId can be a Person Account's shadow Contact -- re-replicate Account after Person Accounts load
**Found:** 2026-07-26, sample-data reload test. The `340` transform assigns
`ContactId` from a pool of **both** real Contacts (`Contact_Load`) **and**
each Person Account's platform-created shadow Contact
(`SELECT PersonContactId FROM dbo.Account WHERE PersonContactId IS NOT
NULL`). But `dbo.Account` is a **replicated snapshot** -- if it was
replicated before this run's Person Accounts were loaded, its
`PersonContactId` values are stale (they point at shadow Contacts that were
deleted in the reset), and every CampaignMember referencing one fails
`INVALID_CROSS_REFERENCE_KEY: invalid cross reference id`.
**What to do:** **re-replicate `Account` (`replicate Account --raw`) after
loading Person Accounts**, before running `340`. This is the general
"refresh a replicated snapshot after the record it derives from loads"
lesson -- the same reason `390` needs a fresh `GiftCommitmentSchedule`
replicate after `370`. Verify with a quick join of `CampaignMember_Load.
ContactId` against `Contact_Load.Id UNION Account.PersonContactId` before
loading -- every row should resolve.

## ContactId/CampaignId are create-only -- fix a failed load by delete + re-insert, not upsert
**Found:** same session. After fixing the stale-snapshot issue above, an
attempt to `bulkops CampaignMember upsert` the corrected table failed the
pre-flight check: `not updateable on CampaignMember: ['CampaignId',
'ContactId']`. Those lookups are set-on-create only, so upsert (which may
update an existing row) is rejected outright.
**What to do:** to reload after a partial failure, **hard-delete the
already-loaded rows and re-insert the full set** (`bulkops CampaignMember
delete --where "MigrationID__c != null" --hard-delete`, then
`bulkops CampaignMember insert ... --fingerprint-columns MigrationID__c`).
A plain re-insert alone would collide on the already-loaded rows
(Salesforce rejects a duplicate Campaign+Contact membership).

## Use `--fingerprint-columns MigrationID__c`
CampaignMember carries boolean fields, so `bulk_op()`'s default (every sent
column) result match can silently break (`submitted N, succeeded 0, failed
0`) -- the same boolean-echo issue as
[AccountContactRelation.md](AccountContactRelation.md). Always fingerprint
on the migration key alone for this object.
