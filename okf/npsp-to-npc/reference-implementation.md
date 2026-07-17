---
type: MigrationPattern
title: NPSP-to-NPC reference implementation (this repo's own PoC)
description: The concrete, live-verified artifacts this repo's own
  NPSP-to-Nonprofit-Cloud proof-of-concept produced -- sql/transformations
  scripts, mapping workbooks, and a Migration Run Book tab -- and how a
  future real engagement should (and shouldn't) reuse them.
tags: [npsp, npc, afnp, reference-implementation, reusable, migration-pattern]
timestamp: "2026-07-17"
---
# NPSP-to-NPC reference implementation

This repo ran a real, live, two-org NPSP-to-Nonprofit-Cloud migration as a
proof-of-concept (postmortem: `postmortems/2026-07-17-npsp-to-npc-poc.md`).
Every artifact it produced is kept in this repo deliberately, as a real
starting point for the *next* NPSP→NPC engagement — not a throwaway demo.

# What's here

| Artifact | Location | Covers |
|---|---|---|
| Transform scripts | `sql/transformations/090-220_npc_*.sql` | All 14 object families in dependency order — Household/Person Account, AccountContactRelation, PartyRelationshipGroup, Campaign/CampaignMember, GiftDesignation, GiftCommitment/Schedule (both the Recurring-Donation and multi-Payment-Opportunity routing branches), GiftTransaction (both branches), GiftTransactionDesignation. |
| Mapping workbooks | `mapping/npc_*.xlsx` | One workbook per (source table, target object) routing branch — `auto-map`'s real suggestions, not hand-typed. |
| Migration Run Book tab | `migration_run_book.xlsx`, tab `NPSP_to_NPC_PoC` | Real load-order/dependency data (including the confirmed circular dependency among the four Gift* objects) and every real `bulkops` result from the live loads. |
| Migration-key metadata | `force-app/main/default/objects/*/fields/MigrationID__c.field-meta.xml`, `force-app/main/default/permissionsets/MigrationFieldAccess.permissionset-meta.xml` | The `MigrationID__c` custom field + FLS grant on every target object this migration writes to. |

# What transfers directly to a new NPSP→NPC engagement

- **The routing logic itself** — the three-way Opportunity split (zero/one
  Payment → Gift Transaction; more than one → Gift Commitment; open stage
  → stays an Opportunity, not exercised in this PoC since no seed data
  needed it), the Recurring-Donation-to-Gift-Commitment-and-Schedule
  conversion, the Household-Account-to-Party-Relationship-Group pairing.
  See [opportunity-routing.md](opportunity-routing.md) and
  [households-to-party-relationship-groups.md](households-to-party-relationship-groups.md)
  for the guide-level rules these scripts implement.
- **The RecordType/picklist choices already discovered and confirmed
  live** — `Household`/`PersonAccount` RecordTypes, `PartyRelationshipGroup.Category
  = 'Staying under same roof'` as the closest household fit,
  `GiftCommitment.ScheduleType`/`GiftCommitmentSchedule.TransactionPeriod`
  cross-validation, the `Percent`+`Amount` pairing requirement on
  `GiftTransactionDesignation`.
- **The `MigrationID__c` migration-key convention and its FLS grant
  pattern** (Hard Rule 8) — deploy the same custom field + permission set
  shape to a new target org, don't reinvent the field name or the
  "assign directly, not via Profile" lesson already captured in
  `force-app/main/default/permissionsets/MigrationFieldAccess.permissionset-meta.xml`'s
  own description.
- **The Allocation-to-Gift-Transaction-Designation proportional-split
  pattern** when a source Opportunity fans out into multiple Gift
  Transactions — see
  [allocation-to-gift-transaction-designation.md](allocation-to-gift-transaction-designation.md).

# What must be redone per client — never reused verbatim

- **Every `MigrationID__c` value and every real Salesforce Id** in the
  scripts' own `JOIN`/`WHERE` clauses is specific to this proof-of-concept's
  seeded dev-org data. A real client's source records need their own
  `replicate` pass and their own routing-branch record counts (this PoC's
  "4 single-Payment, 2 multi-Payment" split was this project's own data,
  not a rule).
- **Field-level mapping decisions** beyond what's platform-structural — a
  real client's own custom fields, their own `PaymentMethod`/`Status`
  picklist customizations, their own address/State-Country picklist
  configuration, all need a fresh `generate-mapping-doc`/`auto-map` pass
  against that client's real profiled source tables (Hard Rule 11 — this
  PoC's own mapping docs were carried to completion only because the
  source was this framework's own seeded mock data, an explicit exception
  that does **not** apply to a real client's real data).
- **Batch sizing** — this PoC's volumes (single digits to low tens of
  rows per object) never exercised `batch_advisor.py`'s real heuristics
  at any meaningful scale; a real client's volumes need their own
  `recommend-batch-size` pass, not this project's `auto` defaults assumed
  correct.
- **Email Deliverability attestation** (Hard Rule 9) — always a fresh,
  explicit human check per org, never carried forward from this PoC's own
  dev-org `system-email-only` setting.

# Citations

1. `postmortems/2026-07-17-npsp-to-npc-poc.md` — the full narrative
   account of this proof-of-concept, including what went well/poorly.
2. `ROADMAP.md` #77 — the technical summary and real findings.
