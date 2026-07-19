---
okf_version: "0.1"
---
# Validators bundle

A git-tracked knowledge base of things to check before building a
transform for a given Salesforce object — an Open Knowledge Format (OKF)
v0.1 bundle. See [README.md](README.md) for the full convention (when to
check one, when to write one, the entry format).

# Guides

* [Validators library — how-to](README.md) - the practical convention
  guide for this bundle.

# System validators

Apply to every object, no exceptions — each formalizes one of CLAUDE.md's
numbered Hard Rules that's also an executable check.

* [Parent-Batch Sort Rule](system/parent-batch-sort.md) - Hard Rule 6:
  sort Load-table rows by parent key so same-parent children never split
  across concurrent Bulk API batches.
* [Migration Key Integrity Rule](system/migration-key-integrity.md) -
  Hard Rule 7: check the migration key for duplicates/NULLs before any
  load.
* [Live Migration Key Validation Rule](system/external-id-validation.md) -
  Hard Rule 12: confirm the migration-key field is genuinely External
  ID + Unique in the live org's describe().
* [RecordType Resolution Rule](system/record-type-resolution.md) - Hard
  Rule 15: resolve RecordTypeId via DeveloperName, never a hand-copied
  org-specific Id.

# Object validators

Findings specific to one object, created the first time something is
discovered the hard way — nothing exists preemptively.

* [Task validator](Task.md) - Activity-level field deployment, WhatId
  polymorphism, the Recurrence* interdependent cluster, Subject's
  combobox type.
* [GiftCommitment validator](GiftCommitment.md) - Name required despite
  createable=false, ScheduleType must match its Schedule's TransactionPeriod.
* [GiftTransaction validator](GiftTransaction.md) - Name required despite
  createable=false, GiftCommitmentId links back to an originating commitment,
  GiftCommitmentScheduleId gated by the Single-Transaction-for-Custom-Schedule rule.
* [PartyRelationshipGroup validator](PartyRelationshipGroup.md) - Name
  required despite createable=false, no exact "Household" Category value
  and real data mostly leaves it unset entirely.
* [AccountContactRelation validator](AccountContactRelation.md) -
  IsIncludedInGroup/IsPrimaryMember are the real household-membership
  signal, not just AccountId/ContactId.
* [GiftCommitmentSchedule validator](GiftCommitmentSchedule.md) - never
  explicitly insert a schedule for a Recurring-type parent GiftCommitment;
  the platform auto-creates one and rejects a second, explicit insert.
* [Contact Point (Address/Phone/Email) validator](ContactPointAddress.md) -
  ParentId is polymorphic Account/Individual (scope to Account only);
  real ContactPointAddress data is sparser than describe() suggests;
  boolean fields can break bulk_op()'s default result matching.
