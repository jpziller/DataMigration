# Post-Mortem: NPSP-to-NPC Migration Proof-of-Concept

**Date:** 2026-07-17
**Scope:** Full pipeline — discovery → migration-key deployment →
replicate → mapping docs → transform → sort/dedup → load → verify —
against a real seeded NPSP source org (`NPSP_SOURCE`) and a real
Nonprofit Cloud target org (`NPC_TARGET_v2`), following Salesforce's
official NPSP-to-AFNP migration guide. 14 object families, ~90 real
records, all loaded and verified live.

## What went well

- **The two-org config mechanism (roadmap #75), built earlier the same
  session specifically to remove source/target-switching friction, held
  up under real, sustained use** — every command in this migration used
  `--org source`/`--org target` with no further friction. Built exactly
  when needed, not speculatively ahead of time.
- **`replicate-subset`'s underlying philosophy (scope by real, known Ids
  rather than re-deriving from scratch) generalized correctly** even
  though this migration used plain `replicate --where "Id IN (...)"`
  rather than the dedicated tool — the pattern of trusting a real,
  already-known Id set over a guessed `WHERE` clause was the right
  instinct throughout.
- **`auto-map`'s Hard-Rule-11 exception for framework-generated data**
  worked as designed — 11 real routing branches auto-mapped in minutes,
  giving a genuinely useful first pass despite most Nonprofit Cloud
  fields having no NPSP source analog (confirmed: most auto-map
  suggestions were correctly "No").
- **The dry-run-then-real pattern for the `sf project deploy start`
  metadata deploy** (Phase 1) caught two real problems — a permission-set
  description exceeding Salesforce's 255-char limit, and a stale
  unrelated Layout file referencing a field that doesn't exist in this
  fresh org — before either touched the live org.
- **Verifying every load's real record count via direct SOQL query**
  (never trusting `bulk_op()`'s own summary alone) caught the writeback-
  race false negatives immediately, every time, rather than after the
  fact.

## What went poorly (and what was fixed)

- **`Name` required on insert despite `describe()` reporting
  `createable: False`** — hit independently on `PartyRelationshipGroup`,
  `GiftCommitment`, `GiftTransaction`. Fixed live each time by sending a
  real `Name` value; written up as
  [okf/nonprofit-cloud/name-field-createable-flag-quirk.md](../okf/nonprofit-cloud/name-field-createable-flag-quirk.md)
  and three object validators once the pattern repeated a third time.
- **The roadmap #74 writeback-race fix's retry budget (~15s) wasn't
  generous enough for this target org's real propagation tail** — hit on
  3 of 9 loads in the Account/relationship/Campaign phase alone, each
  confirmed genuinely successful via a direct, much-later
  `successfulResults` API call. Extended to ~61s (`bulkops.py`); full
  suite stayed green.
- **`CampaignMember.MigrationID__c` was missing entirely from the Phase 1
  metadata deploy** — only caught live when that load's own pre-flight
  check failed with "not a real field." A completeness cross-check
  against the full planned object list, done once before the first load
  rather than discovered load-by-load, would have caught this in seconds.
- **`script_numbering.matches_token()`'s whole-token filename matching
  silently mis-resolved compound object names** — adding
  `account_contact_relation_load.sql`/`campaign_member_load.sql` broke
  `migration_run_book.py`'s Object-cell resolution for `Account`,
  `Contact`, and `Campaign` simultaneously. Caught only by the
  pre-existing test suite failing, not by reasoning about the new files.
  Worked around by removing internal delimiters from the compound names;
  the underlying matcher ambiguity is not yet fixed — see `ROADMAP.md`
  #76.
- **A real cross-object validation** (`GiftCommitmentSchedule.TransactionPeriod
  = 'Custom'` requires its parent `GiftCommitment.ScheduleType` to also
  be `'Custom'`) and **a real cross-field validation**
  (`GiftTransactionDesignation` requires `Percent` whenever `Amount` is
  sent) were both found only by a live `FIELD_INTEGRITY_EXCEPTION`/
  `INVALID_INPUT` failure — neither was documented in the Appendix B
  validation tables reviewed beforehand. Both fixed live; the schedule/
  commitment one is now written up in
  [validators/GiftCommitment.md](../validators/GiftCommitment.md).
- **Allocation's Opportunity-level granularity doesn't map cleanly onto
  Gift Transaction Designation's per-transaction granularity** whenever
  an Opportunity fans out into more than one Gift Transaction. Resolved
  by a proportional split (see
  [okf/npsp-to-npc/allocation-to-gift-transaction-designation.md](../okf/npsp-to-npc/allocation-to-gift-transaction-designation.md))
  — a defensible default, not necessarily the only correct one (see
  Open Questions below).
- **A hand-maintained seed-tracking table
  (`NPSPSeed_Payment_Load`) silently undercounted real Payment
  records** once NPSP's own automation was accounted for — 3 of 6
  Opportunities carry an auto-generated Payment never present in that
  table. Caught only by re-`replicate`-ing fresh immediately before
  building the routing transform, not by trusting the older table.

## Reusable artifacts produced

- `sql/transformations/090-220_npc_*.sql` — all 14 object-family
  transforms, in real dependency order.
- `mapping/npc_*.xlsx` — 14 mapping workbooks, one per routing branch,
  committed deliberately (a targeted `.gitignore` exception) rather than
  left disposable.
- `migration_run_book.xlsx`, tab `NPSP_to_NPC_PoC` — real load-order data
  (including the confirmed circular dependency among the four Gift*
  objects) and every real `bulkops` result.
- `force-app/main/default/objects/*/fields/MigrationID__c.field-meta.xml` ×
  10 objects + the `MigrationFieldAccess` permission set grant.

Full account of what transfers directly to a future engagement vs. what
must be redone per client:
[okf/npsp-to-npc/reference-implementation.md](../okf/npsp-to-npc/reference-implementation.md).

## Target-platform-only knowledge extracted

Split into a new, source-agnostic OKF subject area,
[okf/nonprofit-cloud/](../okf/nonprofit-cloud/index.md) — Person Accounts
as a mandatory org-level prerequisite, the real 4-RecordType taxonomy a
fresh AFNP org ships with, and the `Name`-field `createable` quirk above.
The 3 official Appendix B validation-rule docs (previously inside
`okf/npsp-to-npc/`, zero NPSP-specific content) moved there too.

## Process and tooling gaps found

- `ROADMAP.md` #76 — the `matches_token()`/`script_filename_for()`
  compound-name collision (see above). Documented, workaround applied,
  real fix deferred (needs the full object-name set as context, a
  signature change to two call sites).
- `ROADMAP.md` #74 (follow-up) — the writeback-race retry budget
  extension.
- `_ctx()` unconditionally connects to Salesforce even for commands with
  no Salesforce work to do (e.g. `profile-sql-table`) — surfaced once
  `SF_ORG_ALIAS` became legitimately unset-by-default under the new
  two-org config. Not fixed this pass; low urgency, easy workaround
  (`--org` on any command).

## Open questions for next time

- **The Allocation proportional-split default** (this project's own
  choice) should be confirmed explicitly with a real client rather than
  assumed correct — a client whose own reporting treats a multi-payment
  gift's fund designation as one upfront commitment, not a per-installment
  split, would want a different rule. See
  `okf/npsp-to-npc/allocation-to-gift-transaction-designation.md`'s own
  closing note.
- **`PartyRelationshipGroup.Category = 'Staying under same roof'`** was
  this project's own default for a migrated NPSP household — not a
  perfect semantic match (no exact "Household" `Category` value exists).
  Worth a real client conversation, not an assumed default, on a real
  engagement.
- **The `matches_token()` fix itself** (ROADMAP #76) is scoped but not
  built — worth doing before a third compound-object-name collision
  happens on some future project that doesn't have this post-mortem's
  context to fall back on.
