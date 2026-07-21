---
type: MigrationPattern
title: NPC fundraising/donor-management Snowfakery dogfood -- reference implementation
description: The concrete, live-verified artifacts this repo's own
  Snowfakery-driven dogfood build produced across NPC's full
  fundraising/donor-management object surface (20 objects, no NPSP
  source at all) -- transform scripts, the recipe-generation sequence,
  and every real fix baked in -- and how the next rebuild pass (a
  planned clean-org reload) should reuse them.
tags: [npc, afnp, fundraising, snowfakery, reference-implementation, reusable, dogfood]
timestamp: "2026-07-19"
---
# NPC fundraising/donor-management Snowfakery dogfood -- reference implementation

This repo ran a full, live, Snowfakery-driven build across NPC's entire
fundraising/donor-management object surface — not sourced from NPSP or
any real client system, generated fresh via `generate-related-mock-data`
per Hard Rule 11's explicit exception for framework-generated data
(CLAUDE.md), loaded all the way to a real completion in `NPC_TARGET_v2`.
Postmortem: `postmortems/2026-07-19-npc-fundraising-dogfood-recipe.md`.
PR #20 (`feature/npc-fundraising-dogfood-recipe`).

**A second pass is already planned** (per the user, 2026-07-19): purge
every migrated record from `NPC_TARGET_v2` and rebuild from a blank
slate, keeping only the Migration Run Book, mapping docs, and these
transform scripts. This doc's whole purpose is to make that second pass
faster and cleaner than this one — every fix below is already baked
into the numbered scripts themselves, not left as something to
rediscover.

# What's here

| Artifact | Location | Covers |
|---|---|---|
| Transform scripts | `sql/transformations/230-430_*.sql` | 20 scripts, 11 build groups, all 20 objects, real dependency order (`380` deliberately skipped — see the numbering note below). |
| Mapping workbook | `mapping/npc_dogfood_mapping.xlsx` | One tab per object with a real Mock source table (Hard Rule 11 — carried to completion, not a first-draft). |
| Migration Run Book tab | `migration_run_book.xlsx`, tab `NPC_Fundraising_Dogfood` | Real load-order data and every real `bulkops` result from this pass. |
| Migration-key metadata | `force-app/main/default/objects/*/fields/MigrationID__c.field-meta.xml` (20 objects total, 13 from the earlier PoC + 7 new this pass) + the extended `MigrationFieldAccess` permission set | The migration-key field + FLS grant on every object this build writes to. |
| Framework fixes | `snowfakery_data.py` (createable-edge filtering), `bulkops.py` (`_writeback_inplace()`'s `COALESCE` + per-row `execute()`) | Benefit every future `generate-related-mock-data`/`bulkops` call, not just this build. |

# Object list and build-group sequence

The full 20-object list, in the 11 build-group order the scripts follow
(each group's Snowfakery generation call, if any, then its transform
script(s)):

1. **Household Account + Contact** (`230`, `240`) —
   `generate-related-mock-data Account Contact --count Account=8
   --count Contact=1-3`.
2. **AccountContactRelation, PartyRelationshipGroup, ContactContactRelation**
   (`250`, `260`, `270`) — pure SQL, no new generation; replicates
   `PartyRoleRelation` (a small, fixed 7-row reference set) first.
3. **Organization Account** (`280`) —
   `generate-related-mock-data Account --count Account=5`.
4. **Person Account** (`290`) —
   `generate-related-mock-data Contact --count Contact=10` (generated as
   Contact shapes, mapped onto Account's own `Person*`-prefixed fields).
5. **ContactPointAddress/Phone/Email** (`300`, `310`, `320`) — three
   separate standalone `generate-related-mock-data` calls, `--count
   <Object>=35` each; `ParentId` SQL-assigned across the combined
   23-Account pool afterward.
6. **Campaign + CampaignMember** (`330`, `340`) —
   `generate-related-mock-data Campaign CampaignMember --count
   Campaign=4 --count CampaignMember=3-8`.
7. **GiftDesignation** (`350`) —
   `generate-related-mock-data GiftDesignation --count
   GiftDesignation=6`.
8-9. **GiftCommitment + GiftCommitmentSchedule** (`360`, `370`) —
   `generate-related-mock-data GiftCommitment --count
   GiftCommitment=15` (standalone — `GiftCommitmentSchedule` is
   deliberately NEVER generated through Snowfakery at all, see below);
   `370` replicates real schedules and only explicitly inserts whatever
   is genuinely missing.
10. **GiftTransaction + GiftRefund + GiftSoftCredit** (`390`, `400`,
    `410`) — `generate-related-mock-data GiftTransaction GiftRefund
    GiftSoftCredit --count GiftTransaction=40 --count GiftRefund=0-1
    --count GiftSoftCredit=0-1`.
11. **GiftDefaultDesignation + GiftTransactionDesignation** (`420`,
    `430`) — pure SQL, no new generation.

**Numbering note**: `380` is a deliberate gap, not a missing file. It was
originally planned as a separate "replicate the real, auto-created
Recurring schedules" reference step, but `370`'s own corrected check-first
design (see below) absorbed that logic directly — `370` already replicates
real state before deciding what to insert, so a second, standalone
replicate step was redundant and was removed rather than kept as an
empty placeholder. `next-script-number` will offer `380` again for a
genuinely new script inserted between `370` and `390` in a future pass.

# What transfers directly to a next pass — reuse verbatim

- **Every script's own corrected logic.** Every fix found live during
  this build (see the postmortem's "What went poorly" section for the
  full list — Campaign date ordering, GiftCommitment `ExpectedEndDate`
  for Recurring rows, `GiftTransaction.TransactionDueDate` requirements,
  the Custom-schedule single-transaction rule, `GiftRefund`'s three
  constraints, `GiftSoftCredit`'s mutual-exclusivity rule, the
  `GiftTransactionDesignation` remainder-based split) is already baked
  into the numbered script itself, not left as a separate patch. A fresh
  run against an empty org should reproduce the corrected behavior
  directly.
- **The `generate-related-mock-data` call sequence and grouping.** The
  "generate → build Load table → bulkops-load → build next dependent
  object" interleaving is required, not optional — a real Salesforce Id
  is often needed by the very next group's own SQL joins (see the
  postmortem's "GiftCommitment must load before Contact_Load can be
  built" style findings). Don't try to batch every group's generation
  up front.
- **The `--fingerprint-columns` discipline.** Every `bulkops` call in
  this recipe's own run history that sends a boolean column passes
  `--fingerprint-columns` proactively (the real `Id` when already known,
  the migration key otherwise) — see
  [bulk-api-2-csv-semantics.md](bulk-api-2-csv-semantics.md). Carry this
  forward for every call in a rebuild, not just the ones that failed
  last time.
- **The `AccountContactRelation`/`GiftCommitmentSchedule` check-first
  pattern.** Never assume either object auto-creates or doesn't —
  replicate real state first, act only on what's genuinely missing. See
  [account-contact-relation-auto-creation.md](account-contact-relation-auto-creation.md)
  and
  [gift-commitment-schedule-auto-creation.md](gift-commitment-schedule-auto-creation.md).
- **The RecordType resolution** (`Household`/`Business_Account`/
  `PersonAccount` DeveloperNames, confirmed live, including the
  `Business_Account`-vs-`Org_Business_Account` naming trap — see
  [person-accounts-and-record-types.md](person-accounts-and-record-types.md)).

# What must be redone or reconsidered per pass — never assumed identical

- **Every `MigrationID__c` value is a synthetic key tied to this
  specific run's own `_MockRowId` numbering** (`'SNOWFAKE-HH-1'`,
  `'SNOWFAKE-GC-7'`, etc.) — a fresh Snowfakery generation call produces
  a NEW, unrelated set of Mock rows with its own fresh `_MockRowId`
  sequence starting over. A second pass's real Salesforce Ids and
  `MigrationID__c` values will not match this pass's — that's expected,
  not a regression, as long as the *old* records were actually purged
  first (the user's own planned next step).
- **The one known, accepted gap**
  (`GiftTransactionDesignation`, 1 of 60 rows, see
  [gift-refund-and-soft-credit-validations.md](gift-refund-and-soft-credit-validations.md))
  is NOT yet fixed in `430` — a rebuild will hit it again unless it's
  resolved first. Try the delete-and-reinsert approach already proven
  twice this session before assuming it's a different root cause.
- **UPDATE (2026-07-19, later): the `GiftCommitmentSchedule` auto-creation
  root cause is mostly resolved, not still open.** Official docs plus a
  real Nonprofit Cloud architect's confirmation (see
  [gift-commitment-schedule-auto-creation.md](gift-commitment-schedule-auto-creation.md)'s
  own later update) found it: auto-creation is real for a "regular"
  recurring type (e.g. Monthly), via either an explicit "Manage Recurring
  Gift Commitment Schedule" Invocable Action call (confirmed NOT fired by
  a plain Bulk API insert) or the nightly "NextGen commitment processing
  job" (a real Salesforce batch). This build's "0/12" result was very
  likely a timing artifact (checked same-day, before the nightly job
  could run) combined with never calling the explicit Action — not
  inconsistent platform behavior. `370`'s check-first pattern remains the
  right defensive design regardless. **What's still genuinely open**: the
  exact mechanical trigger (does `ScheduleType='Recurring'` alone suffice
  given enough time, or is the explicit Action call required first) was
  not independently confirmed even by the architect. On the next rebuild,
  try calling the Action explicitly for Recurring-type commitments (with
  a real `TransactionPeriod` like `Monthly`) rather than repeating this
  pass's same-day check-and-workaround pattern.
- **Volumes were a judgment call** (8 households, 40 gift transactions,
  etc.) — a rebuild pass is free to scale these differently; nothing in
  the current scripts locks a specific volume in as structurally
  required, though the round-robin/modulo assignment logic throughout
  assumes each group's counts stay proportionally similar (e.g.
  `GiftCommitment`'s `--count` relative to the Account pool size).
- **The mapping workbook's own field-level decisions**
  (`mapping/npc_dogfood_mapping.xlsx`) reflect what THIS pass's
  `auto-map`/manual review chose — a rebuild reusing the same scripts
  doesn't need to regenerate these unless the scripts themselves change,
  but any script edit should get a corresponding mapping-doc update via
  `check-mapping-balance` before being trusted.

# Citations

1. `postmortems/2026-07-19-npc-fundraising-dogfood-recipe.md` — the full
   narrative account, including what went well/poorly.
2. Every `okf/nonprofit-cloud/*.md` file dated 2026-07-19 — the
   individual real findings this build produced.
