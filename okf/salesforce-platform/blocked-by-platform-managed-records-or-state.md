---
type: MigrationPattern
title: Blocked by platform-managed records or state -- when your migration key doesn't cover what's really there
description: A cross-cloud pattern. An operation (usually a delete during a
  reset, sometimes an update) fails even though your migration-key-scoped
  query says the data is gone or clean -- because the platform created or
  manages records and state that carry NO migration key of their own.
  Two shapes -- auto-generated child records (created by a schedule/job/
  automation over time, or on insert), and state locks (an operation is
  forbidden until a field/status changes). The migration-key filter is
  blind to both. Recognize it from the error naming records you can't
  find by key, confirm it by querying the real relationship or state (not
  your key), and fix it by scoping to the real relationship, hard-deleting
  residue, or changing the blocking state first.
tags: [salesforce-platform, cross-cloud, reset, delete, locked, blocked, auto-generated-records, migration-key, state-lock, diagnosis, migration-pattern, gift-commitment, gift-transaction, gift-designation]
timestamp: "2026-07-26"
---
# Blocked by platform-managed records or state

A migration scopes its own operations by its own **migration key** (e.g.
`MigrationID__c`) -- it loads, validates, and resets the records *it*
created. But the target platform creates and manages records and state
that **don't carry that key**. When one of those blocks an operation, a
migration-key-scoped query will insist everything is fine while the
operation keeps failing. This pattern is how to recognize, confirm, and
fix that class of problem -- on any cloud.

## The two shapes

**1. Auto-generated child records (no migration key).** The platform
creates real, live child records you didn't insert -- either **on insert**
of a parent, or **over time** via a schedule/batch/Flow. They reference
your parent, so they block the parent's deletion, but they have no
`MigrationID__c`, so a `WHERE MigrationID__c != null` delete never touches
them.

* Confirmed live, Nonprofit Cloud: a **recurring `GiftCommitment`'s
  schedule** (`Type = CreateTransactions`) auto-generates `GiftTransaction`
  records across the schedule's whole date range -- past and future. A
  reset that deleted transactions by `MigrationID__c != null` left
  thousands of these behind, and they blocked every `GiftCommitment`
  delete. See
  [okf/nonprofit-cloud/full-org-reset-between-build-attempts.md](../nonprofit-cloud/full-org-reset-between-build-attempts.md)
  and [okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md](../nonprofit-cloud/gift-commitment-schedule-auto-creation.md).
* Same family, created **on insert** rather than over time:
  `AccountContactRelation`, `GiftDefaultDesignation`,
  `GiftCommitmentSchedule` -- see
  [okf/nonprofit-cloud/never-update-auto-created-records.md](../nonprofit-cloud/never-update-auto-created-records.md).

**2. State locks.** The platform forbids the operation until a field or
status changes first -- the record isn't referenced by anything, it's just
in the wrong state.

* Nonprofit Cloud: **can't delete an active `GiftDesignation`**
  (`UNKNOWN_EXCEPTION: You can't delete an active gift designation`) --
  set `IsActive = false` first. A field can also lock *after* a status
  change (e.g. `GiftTransactionDesignation.Amount` once its parent
  transaction is posted) -- see
  [okf/nonprofit-cloud/gift-transaction-validations.md](../nonprofit-cloud/gift-transaction-validations.md).

## How to recognize it

Any of these is a tell that you're in this pattern, not looking at your
own data:

* A delete fails with **"...is associated with the following \<children\>..."**
  naming records, or **"can't delete an active \<X\>"**, or **"\<field\>
  can't be changed."**
* Your **migration-key-scoped `COUNT()` says 0 remaining**, yet the
  operation still fails. (The strongest signal -- your key is blind to
  what's blocking you.)
* The error names **records or values you didn't create and can't find by
  your migration key** -- and, tellingly, child records spanning dates
  outside your load (a schedule generating past *and* future rows).

## How to look for it (diagnosis)

**Don't trust the migration-key filter -- query the real relationship or
state directly.**

1. **Query the actual relationship, including deleted rows and the key**:
   `SELECT Id, Name, IsDeleted, <YourKey__c> FROM <Child> WHERE
   <ParentField> = '<parentId>'` via the `queryAll` endpoint. A
   **live child (`IsDeleted = false`) with a NULL migration key** is a
   platform-generated record your reset missed -- the smoking gun.
2. **Distinguish live vs. recycle-bin residue.** A separate trap: records
   *you* soft-deleted linger in the Recycle Bin / an async physical-purge
   limbo and can also block a parent, but those show `IsDeleted = true`.
   The fix for those is different (hard delete -- see below); don't
   conflate the two. (This repo initially misdiagnosed the NPC case as
   pure recycle-bin residue; the real cause was live auto-generated
   children. Query `IsDeleted` to tell them apart -- the error text names
   the records but not their live/deleted status.)
3. **Read the error text as a lead, not the whole answer.** It names the
   blocking records (often with amount/date), which is enough to find the
   relationship to query -- but it's name-based, not Id/status-based, so
   confirm by querying, don't conclude from the message alone.
4. **Proactively, before you ever load**: `analyze-org-risk` runs
   `child_record_risk.py`, which empirically diffs real reference records
   to flag auto-generated child relationships up front -- the "look for it
   before it bites" version of this whole pattern. Run it for a target
   object family you don't know yet.

## How to fix it

* **Scope resets/cleanup by the real relationship, not just your key.**
  Delete the children by `WHERE <ParentField> IN (SELECT Id FROM <Parent>
  WHERE MigrationID__c != null)` so keyless auto-generated children are
  caught too. **Keep it scoped to your parents** so you never touch the
  org's own reference/demo data.
* **Hard-delete where soft-delete residue blocks a parent.** `bulkops
  <Object> delete --where "..." --hard-delete` (Bulk API 2.0 hardDelete)
  removes records permanently, bypassing the Recycle Bin, so nothing
  lingers to block the parent -- and it's the only way to clear residue
  that's already past the Recycle Bin (`emptyRecycleBin`/`undelete` both
  fail with "not in recycle bin"). See ROADMAP #84.
* **Change the blocking state first** for state locks -- deactivate,
  re-open status, or clear the field -- then retry.
* **Never insert/update a platform-auto-created record** just because it's
  in your way on the load side -- that's a different rule (the platform's
  own record already matches reality); see
  [never-update-auto-created-records.md](../nonprofit-cloud/never-update-auto-created-records.md).

## Why this also matters on the LOAD side, not just reset

If the platform auto-generates children from a record you load (e.g. a
`CreateTransactions` schedule), then **migrating those children yourself
too will duplicate them.** The same auto-generation that blocks a reset
can silently double your data on a load. When a target object triggers
auto-generation, decide deliberately whether to migrate the children or
let the platform create them -- don't do both by accident.

# Citations

1. Live-confirmed 2026-07-26, `NPC_TARGET_v2`, during a full sample-data
   reset+reload test. The GiftCommitment/GiftTransaction instance was
   found the hard way (initially misdiagnosed as recycle-bin residue;
   corrected when a live `queryAll ... WHERE GiftCommitmentId = ...`
   showed live, keyless, auto-generated children).
2. `child_record_risk.py` / `analyze-org-risk` -- this repo's existing
   empirical detector for the auto-generated-child shape of this pattern.
