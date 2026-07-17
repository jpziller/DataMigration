---
type: MigrationPattern
title: Person Accounts and RecordTypes (Nonprofit Cloud/AFNP)
description: Person Accounts are a mandatory, org-level prerequisite for
  Nonprofit Cloud, and a fresh AFNP org ships with a specific real
  RecordType taxonomy on Account -- both confirmed live against a real
  target org, not assumed from documentation alone.
tags: [npc, afnp, person-accounts, record-types, account-model, nonprofit-cloud]
timestamp: "2026-07-17"
---
# Person Accounts and RecordTypes (Nonprofit Cloud/AFNP)

## Person Accounts must already be enabled at the org level
Confirmed live, not assumed: a target org ready for Nonprofit Cloud data
has Person Accounts turned on — `describe('Account')` carries
`IsPersonAccount`/`PersonContactId` and related `Person*` fields
(`PersonEmail`, `PersonMailingStreet`, etc.) only when this is the case.
This is consistent with the official migration guide's own framing (see
[okf/npsp-to-npc/new-org-vs-in-place.md](../npsp-to-npc/new-org-vs-in-place.md))
that Person Accounts are mandatory in AFNP, not optional — NPSP represents
people as plain Contacts, AFNP requires Person Accounts, which merge
Account and Contact attributes into one record.

**What to do:** before building any Account-writing transform, confirm
live via `describe Account` (or a quick Python check for
`PersonContactId` in the field list) rather than assuming a target
sandbox/dev org already has this enabled — it's an org-level Setup
toggle a project's own tooling can't turn on remotely, and (per Setup's
own behavior) generally can't be un-done once enabled.

## The real RecordType taxonomy on a fresh AFNP org's Account
Confirmed live via `resolve-record-types Account` against a real target
org: exactly 4 RecordTypes ship on `Account` —

| DeveloperName | Name |
|---|---|
| `Household` | Household Business Account |
| `PersonAccount` | Person Account |
| `Business_Account` | Organization Business Account |
| `Org_Business_Account` | Business Account |

**What to do:** resolve these by `DeveloperName` via
`dbo.RecordTypeMap` (Hard Rule 15/the RecordType Resolution Rule), never
hand-copy a raw RecordTypeId — the same convention this framework already
enforces everywhere else. `Household` is the target for a migrated NPSP
Household Account; `PersonAccount` is the target for a migrated
individual Contact (see
[okf/npsp-to-npc/households-to-party-relationship-groups.md](../npsp-to-npc/households-to-party-relationship-groups.md)
for the full household-migration pattern this pairs with). The naming is
slightly confusing on first read — `Business_Account` (Organization
Business Account) and `Org_Business_Account` (plain Business Account) are
two *different* RecordTypes with similarly-worded labels; verify the
`DeveloperName`, not just the human-readable `Name`, before choosing one.
