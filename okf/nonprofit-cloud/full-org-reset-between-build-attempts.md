---
type: MigrationPattern
title: Full org reset between build attempts (NPC fundraising surface)
description: The real, live-verified sequence for wiping every migrated
  record (plus platform auto-created children with no migration key of
  their own) from a target org across the NPC fundraising/donor-
  management object family, returning it to a clean, human-created-only
  state before a fresh rebuild attempt. Distinct from a corrective
  reload (docs/MIGRATION_PLAYBOOK.md) -- that fixes a bug in
  already-migrated data; this clears everything to start over.
tags: [npc, afnp, purge, delete, reset, methodology, process, fundraising, migration-pattern]
timestamp: "2026-07-20"
---
# Full org reset between build attempts (NPC fundraising surface)

**When to use this, vs. `docs/MIGRATION_PLAYBOOK.md`'s "Corrective
reload" section:** that section covers fixing a specific data-shape bug
in records a migration already loaded (delete and reinsert just the
affected rows). This pattern is for the different, earlier-stage case —
wiping an entire practice/sample-data/PoC pass's worth of migrated data
completely, so the next attempt starts from a genuinely clean org rather
than layering on top of (or half-overwriting) the previous one. Real
use case: the user's own explicit instruction (2026-07-20) after the NPC
fundraising Snowfakery sample data build (PR #20) — "wipe out everything
with a migrated ID in the org... put the org back to the start with just
human created data... any script we have is reference/artifact."

# The real reverse-dependency delete order

Confirmed live, `NPC_TARGET_v2`, 2026-07-20 — deleting in this order
(leaf/child objects first, `Account`/`Contact` last) meant nothing ever
blocked on a still-existing child reference:

```
GiftTransactionDesignation
GiftDefaultDesignation
GiftSoftCredit
GiftRefund
GiftTransaction
GiftCommitmentSchedule
GiftCommitment
GiftDesignation          -- deactivate first, see below
CampaignMember
Campaign
ContactPointEmail / ContactPointPhone / ContactPointAddress
ContactContactRelation
AccountContactRelation   -- no key of its own, traced by relationship; see below
PartyRelationshipGroup
Contact
Account
```

For most objects this is a plain
`bulkops <Object> delete --where "MigrationID__c != null" --hard-delete` —
`--dry-run` first, confirm the matched count, then the real delete. Two
objects need special handling, below (`GiftTransaction` scope, and
`AccountContactRelation` traced by relationship), plus `GiftDesignation`
must be deactivated first.

## `GiftCommitment` is blocked by auto-generated `GiftTransaction`s that carry no migration key — scope the transaction delete by `GiftCommitmentId`
**Found live 2026-07-26** (this is a correction — an earlier version of
this doc misdiagnosed the block as Recycle-Bin/async-purge residue; that
was wrong). A recurring `GiftCommitment`'s schedule (`Type =
CreateTransactions`) **auto-generates real, live `GiftTransaction` records
across the schedule's whole date range** — past *and* future. These are
platform-created, so they carry **no `MigrationID__c`**, and a
`GiftTransaction delete --where "MigrationID__c != null"` never touches
them. They stay live and **block every `GiftCommitment` delete**:

```
DELETE_FAILED: ...could not be completed because it is associated with the
following gift transactions: Snowfake-Underwood LLC - 53296.19 -
2026-08-01, Snowfake-Underwood LLC - 53296.19 - 2024-08-24
```

The tell: a migration-key-scoped `COUNT()` says **0 live GiftTransactions
remain**, yet the delete still fails naming transactions — because your key
is blind to the auto-generated ones. Confirm with
`queryAll ... SELECT Id, IsDeleted, MigrationID__c FROM GiftTransaction
WHERE GiftCommitmentId = '<id>'` — a **live child with a NULL
MigrationID__c** is the smoking gun. This is the general
[Blocked by platform-managed records or state](../salesforce-platform/blocked-by-platform-managed-records-or-state.md)
pattern; NPC is one instance of it.

**Fix — delete the transactions scoped by the real relationship, not by
the key:**
```
bulkops GiftTransaction delete --where \
  "GiftCommitmentId IN (SELECT Id FROM GiftCommitment WHERE MigrationID__c != null)" \
  --hard-delete
```
Scoping to *your* commitments keeps the org's own reference/demo
transactions (there can be thousands) untouched. Then the
`GiftCommitment` delete succeeds.

## `--hard-delete` is required for this family (Recycle-Bin residue also blocks a parent)
**A second, related trap** (ROADMAP #84): a plain (soft) delete leaves
records in the Recycle Bin, and *that* residue can also block a parent
delete — and once soft-deleted via the Bulk API it can't be cleared on
demand (`emptyRecycleBin()` → `no recycle bin entry found`, `undelete()` →
`Entity is not in the recycle bin`; the records sit in an async
physical-purge limbo that only Salesforce's background job clears). Avoid
both traps by hard-deleting from the start: `--hard-delete` uses Bulk API
2.0 `hardDelete` to remove records permanently, bypassing the Recycle Bin.
**Prerequisite:** the load user needs the **"Bulk API Hard Delete"**
system permission — deploy and assign the committed `MigrationHardDelete`
permission set (`sf project deploy start --source-dir
force-app/main/default/permissionsets/MigrationHardDelete.permissionset-meta.xml
--target-org <alias>`, then `sf org assign permset --name
MigrationHardDelete --target-org <alias>`; kept separate from
`MigrationFieldAccess` so this irreversible permission stays opt-in). Hard
delete is irreversible — the Live-Org Write Confirmation Rule (#2) applies
in full.

# Two real platform quirks found live while doing this

## `GiftDesignation` can't be deleted while `IsActive = true`
`UNKNOWN_EXCEPTION: "You can't delete an active gift designation."` —
6 of 8 real rows failed on the first attempt. Fix: `bulkops
GiftDesignation update` setting `IsActive = false` on the affected rows
first (no other fields needed), then retry the delete. See
`validators/GiftDesignation.md`.

## `AccountContactRelation` has no migration key, and a "direct" one can't be deleted independently
This object never gets a migration key stamped on it (see
`account-contact-relation-auto-creation.md` — it's platform auto-created
on Contact insert, and stamping a migration key on a row this migration
didn't create would be a lie). To find it for deletion, trace by
relationship instead of by key:

```
bulkops AccountContactRelation delete --where
  "AccountId IN (SELECT Id FROM Account WHERE MigrationID__c != null)"
bulkops AccountContactRelation delete --where
  "ContactId IN (SELECT Id FROM Contact WHERE MigrationID__c != null)"
```

(Two separate calls, not one combined with `OR` — Salesforce's SOQL
rejects a semi-join sub-select combined with `OR`:
`"Semi join sub-selects are not allowed with the 'OR' operator"`.)

Both calls will report real failures for every row where
`IsDirect = true`:
`INVALID_OPERATION: "A direct relationship can't be deleted. You can
modify the relationship by changing the contact's parent account or
deleting the contact."` This is expected, not a bug in the delete
attempt — a direct relationship is a view onto the Contact's own
`AccountId` field, not an independently deletable junction record.
**Don't try to force it.** Delete the Contact next (the next step in the
sequence above); every remaining direct `AccountContactRelation` row is
removed as an automatic side effect. Confirmed live: the count dropped
from 16 to 0 the moment the 16 owning Contacts were deleted, with no
separate action needed. See `validators/AccountContactRelation.md`.

# General technique this reuses

Both quirks above are instances of a pattern this repo already names in
`docs/MIGRATION_PLAYBOOK.md`'s "Corrective reload" section: **some
target objects have real child records the platform creates on its own,
or real constraints on when they can be removed, that a naive
`WHERE MigrationID__c != null` delete alone won't handle.** The general
principle — trace by real relationship when no migration key exists,
delete in reverse dependency order, verify with a final zero-count sweep
across every object afterward — applies to any future NPC (or other
Salesforce target) full-reset pass, not just this one's specific object
list.

# Verification

After the full sequence, a direct `COUNT()` per object with
`MigrationID__c != null` should return 0 across all 16 objects that
carry the key, and `AccountContactRelation`'s own remaining count should
match genuine pre-existing org data only (traced-by-relationship queries
against the now-empty migrated-Account/Contact set should also return 0,
confirming nothing was missed).

# Citations

1. Live-confirmed, 2026-07-20, `NPC_TARGET_v2` — real purge sequence run
   end to end, not simulated.
2. `docs/MIGRATION_PLAYBOOK.md`'s "Corrective reload" section — the
   general pattern this specializes for a full reset rather than a
   targeted bug fix.
