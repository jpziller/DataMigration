# NPSP to Nonprofit Cloud (AFNP)

Reference knowledge for migrating from Salesforce Nonprofit Success Pack
(NPSP) to Nonprofit Cloud — Salesforce's own documentation calls the
target "Agentforce Nonprofit" (AFNP). Sourced from Salesforce's official
migration guide and its companion field-mapping workbook, described and
linked here rather than duplicated. Pass 1: the guide's own map, the
official fundraising validation rules, and two of the most structurally
significant conceptual changes. Deeper content (the full ~35-step
migration sequence, the three sibling workbooks for other legacy managed
packages) is deliberately deferred until a real project needs that
specific piece — see [migration-guide.md](migration-guide.md)'s own
outline for what's already mapped out but not yet written up in full.

# Reference

* [Migration guide](migration-guide.md) - the official guide's own table
  of contents and migration-sequence outline, pointing back to the real
  document for full detail.
* [Mapping spreadsheets](mapping-spreadsheets.md) - index of all 4
  companion field-mapping workbooks; only one reviewed so far.
* [NPSP to AFNP field mapping](npsp-to-afnp-field-mapping.md) - the
  reviewed workbook's real structure, taxonomy, and a worked example.

# Platform validations

Official, target-platform-enforced business rules on the fundraising
objects. Moved to [okf/nonprofit-cloud/](../nonprofit-cloud/index.md) —
these are pure Nonprofit Cloud platform facts, true regardless of
migration source, not NPSP-specific — see that bundle's own index for
the Gift Transaction/Commitment/Commitment Schedule validation docs and
other target-platform-only findings (Person Accounts, RecordTypes, the
`Name`-field `createable` quirk).

# Migration patterns

* [New org, not an in-place upgrade](new-org-vs-in-place.md) - Salesforce
  strongly recommends a brand-new target org, never an in-place NPSP
  upgrade.
* [Households to Party Relationship Groups](households-to-party-relationship-groups.md)
* [Opportunity routing](opportunity-routing.md) - the Gift
  Transaction / Gift Commitment / Opportunity three-way split.
* [Allocation vs. Gift Transaction Designation granularity](allocation-to-gift-transaction-designation.md) -
  an Opportunity-level Allocation has no single correct Gift Transaction
  to attach to once its Opportunity fans out into more than one (the
  multi-Payment routing branch) -- confirmed live, not addressed
  explicitly in the official guide.

# This repo's own reference implementation

* [NPSP-to-NPC reference implementation](reference-implementation.md) -
  this repo ran the full sequence above as a real, live proof-of-concept
  (`sql/transformations/090-220`, `mapping/npc_*.xlsx`, a Migration Run
  Book tab) — what a future real engagement can reuse directly vs. what
  must be redone per client. Full narrative account:
  `postmortems/2026-07-17-npsp-to-npc-poc.md`.
