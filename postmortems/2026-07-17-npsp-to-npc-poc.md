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

- **`Name` required on insert, no platform default** — hit independently
  on `PartyRelationshipGroup`, `GiftCommitment`, `GiftTransaction`. Fixed
  live each time by sending a real `Name` value; written up as
  [okf/nonprofit-cloud/name-field-createable-flag-quirk.md](../okf/nonprofit-cloud/name-field-createable-flag-quirk.md)
  and three object validators once the pattern repeated a third time.
  **Correction added 2026-07-18**: the original write-up here and in
  those docs claimed `describe()` reported `createable: False` for these
  fields while they were actually required — a genuine mismatch. That was
  wrong: the real flags are `createable: True, nillable: False,
  defaultedOnCreate: False`, an ordinary required field.
  `bulk_op()`'s own pre-flight check already warned correctly before each
  failure; the actual mistake was proceeding past the warning instead of
  treating it as a hard stop. Caught while planning a pre-flight-check
  enhancement for the (nonexistent) mismatch and re-verifying against the
  live org first — all affected docs corrected in place.
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

## Follow-up: architect review of the live migrated data (2026-07-18)

A second architect (not this framework) reviewed the real migrated data in
`NPC_TARGET_v2` and flagged two concerns: a specific `GiftTransaction` not
connected to its `GiftCommitmentSchedule`, and no visible household
grouping ("PartyRelationshipGroup") for data that came from an NPSP
household. Per explicit instruction, diagnosed using `sample-reference-records`
(built earlier the same session) against real, non-migrated reference
records in the same org — comparing what a genuine, human-created record
looks like against what this migration produced, rather than guessing.

**Confirmed findings:**
- `GiftTransaction.GiftCommitmentScheduleId` was genuinely never populated
  by either routing branch (`200`/`210`) — a real gap, not a deliberate
  omission. Fixed for the Recurring-Donation branch (`200`) only; the
  multi-Payment-Opportunity branch (`210`) can't get the same fix without
  violating AFNP's own "Single Transaction for Custom Schedule" validation
  (discovered while designing the fix, not previously surfaced by this
  project even though it was already sitting in the extracted Appendix B
  table).
- The 8 migrated `PartyRelationshipGroup` records do genuinely exist,
  correctly linked — the "no PRGs" claim wasn't about record existence.
  But `PartyRelationshipGroup.Category` was invented
  (`'Staying under same roof'`) on every one of them, when real reference
  data in the same org leaves it unset 0 of 10 sampled times — exactly the
  kind of self-inflicted shape defect this project's own postmortem
  (below) had already flagged as an open question worth revisiting, now
  confirmed with real evidence and fixed (left unset).
- **The real likely root cause**: `AccountContactRelation` — the object
  that actually flags a person as "in" a household group for UI purposes —
  only ever set `AccountId`/`ContactId`/`IsActive`. Real reference data
  populates `IsIncludedInGroup`/`IsPrimaryMember` consistently; without
  them, a migrated household can have a perfectly valid Account and
  PartyRelationshipGroup and still not visually group its members the way
  a real household does. `Account` has no direct lookup back to
  `PartyRelationshipGroup` at all, confirming the grouping signal lives on
  `AccountContactRelation`, not the group record itself.

**What this confirms about the methodology**: this is the second time this
project's own tooling (built specifically because of the CPQ-migration
lesson about `describe()`/page-layouts not showing a working record's real
shape) caught a real defect that structural correctness checks alone
missed — every affected record loaded successfully and passed every hard
rule; the gap was in field-level shape, only visible by comparing against
real reference records.

**Deeper root cause found while designing the GiftCommitmentScheduleId
fix**: fixing `200`'s missing field turned up something bigger than a
missing column. Querying the live org for the schedule tied to the
architect-flagged record's own `GiftCommitment` found a real schedule
Id (`6csfn000000E5MSAA0`) that had never been captured anywhere in the
local mirror DB. Tracing why led to `GiftCommitmentSchedule_Load`'s own
`Error` column — 3 of this project's 4 original Recurring-Donation-derived
schedule inserts had actually **failed live** with
`FIELD_INTEGRITY_EXCEPTION: ...doesn't overlap with an existing schedule`,
silently, since the original migration pass, never investigated until now.
Root cause, confirmed on 6 of 6 real records: Nonprofit Cloud auto-creates
a `GiftCommitmentSchedule` the moment a `GiftCommitment` is inserted with
`ScheduleType = 'Recurring'` — this project's own explicit insert for
those 3 was redundant and rejected by the platform's own validation. Fixed
by (a) `170` no longer attempting an explicit insert for Recurring-type
commitments at all, and (b) `200` deriving `GiftCommitmentScheduleId` from
a fresh, live replicate of `GiftCommitmentSchedule` joined by the real
`GiftCommitmentId`, not from the local Load table's own bookkeeping (which
only ever reflects what this migration explicitly tried to insert). See
`okf/nonprofit-cloud/gift-commitment-schedule-auto-creation.md` and
`validators/GiftCommitmentSchedule.md`.

**Process lesson, captured for the next corrective pass**: this also
surfaced a gap in how a corrective reload should work. A cleanup filtered
only on `MigrationID__c != null` would silently miss any auto-generated
child record like this — it carries no migration key of its own, only a
real relationship back to a migration-key-tagged parent. Written up as a
general, reusable pattern (the `<Object>_Delete` staging-table technique,
built from both migration-key-tagged records **and** relationship-traced
child records, unioned) in `docs/MIGRATION_PLAYBOOK.md`'s new "Corrective
reload" section — not NPSP/NPC-specific, since any migration doing a
second pass over an org that already has data can hit this same gap.

See `validators/GiftTransaction.md`, `validators/PartyRelationshipGroup.md`,
`validators/GiftCommitmentSchedule.md`, and the new
`validators/AccountContactRelation.md` for the full technical write-ups,
and `ROADMAP.md` #77 for the tracking entry.

## Open questions for next time

- **The Allocation proportional-split default** (this project's own
  choice) should be confirmed explicitly with a real client rather than
  assumed correct — a client whose own reporting treats a multi-payment
  gift's fund designation as one upfront commitment, not a per-installment
  split, would want a different rule. See
  `okf/npsp-to-npc/allocation-to-gift-transaction-designation.md`'s own
  closing note.
- **`PartyRelationshipGroup.Category`** — resolved 2026-07-18 (see the
  follow-up above): real reference-record evidence showed the
  `'Staying under same roof'` default didn't match actual usage at all
  (0/10 real records populate `Category`), so it's now left unset by
  default. Still worth a real client conversation on a real engagement if
  there's a specific reason to populate it — just not an assumed default
  anymore.
- **The `matches_token()` fix itself** (ROADMAP #76) is scoped but not
  built — worth doing before a third compound-object-name collision
  happens on some future project that doesn't have this post-mortem's
  context to fall back on.
