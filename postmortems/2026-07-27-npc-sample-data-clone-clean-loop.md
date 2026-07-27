# Post-Mortem: NPC Sample-Data — polishing the reset+reload loop to clone-clean

**Date:** 2026-07-27
**Scope:** Not a client migration — a deliberate, iterated polish of this
repo's own Nonprofit Cloud sample-data pipeline (`sql/transformations/230-430`,
`sample_data/`) until a **fresh clone** can generate its own Snowfakery
data and load → unload it against a real target org (`NPC_TARGET_v2`) with
**zero errors, no manual intervention**, following only the committed docs.
Multiple full reset+reload cycles; the final one run from a wiped mirror DB
as a from-scratch clone. ~320 records across 16 objects each cycle.

## What went well

- **The "fix the class, not the instance" loop worked.** The governing
  instruction each iteration was to fix the *class* of a failure, not the
  one object that hit it. Every fix below generalized: the date-ordering
  fix landed in mock generation for *all* objects, not just GiftCommitment;
  the auto-generated-children and date-range findings became cross-cloud
  `okf/salesforce-platform/` patterns, not NPC footnotes.
- **The from-scratch clone dry-run as the final gate.** Wiping the mirror
  DB (dropping every `_Mock`/`_Load`/snapshot/`RecordTypeMap` table),
  discovering the org's prior attempt by querying rather than assuming, and
  reloading following *only* committed docs — this is the truest test of
  clone-readiness, and it found a real gap (RecordType prerequisite) a
  memory-driven run would have silently papered over.
- **`--hard-delete` (once built) made resets clean and repeatable.** After
  it landed, every subsequent reset ran start-to-finish with no
  recycle-bin-residue blocking and no manual intervention — a stark
  contrast to the first reset of this loop.
- **`--fingerprint-columns MigrationID__c` as the universal insert
  practice** eliminated a whole class of silent `succeeded=0/failed=0`
  boolean-echo mismatches (and the parent-Id-writeback failures they cause)
  in one move.
- **Active knowledge surfacing paid off.** `gather-okf` + the data-shape
  profile put the auto-generated-children behavior in front of the operator
  *before* the load — the exact behavior that had caused the reset pain.

## What went poorly (and what was fixed)

- **Reset blocked: GiftCommitment wouldn't delete — and I misdiagnosed it
  twice.** Symptom: `DELETE_FAILED: ...associated with the following gift
  transactions`, while a migration-key-scoped count said 0 transactions
  remained. First wrong theory: recycle-bin/async-purge residue. Real root
  cause (found only by querying the relationship with `queryAll` +
  `IsDeleted` + the key): a recurring `GiftCommitment`'s `CreateTransactions`
  schedule **auto-generates live `GiftTransaction`s with no `MigrationID__c`**,
  which the key-scoped delete never touched. Fix: `--hard-delete` (new
  capability) + scope the transaction delete by `GiftCommitmentId`, not the
  key. Durable: `okf/salesforce-platform/blocked-by-platform-managed-records-or-state.md`,
  `validators/GiftCommitment.md`, ROADMAP #84.
- **GiftTransactionDesignation failed on fully-refunded transactions — also
  mis-theorized.** Symptom: `FIELD_INTEGRITY_EXCEPTION: ...doesn't exceed
  the transaction amount` on some refunded transactions but not others.
  Long-standing wrong theory: "standalone vs commitment-linked" (an
  n=1-vs-n=1 coincidence). Real root cause: the total designation Amount is
  capped at `CurrentAmount` (`OriginalAmount − RefundedAmount`), which a
  refund reduces *asynchronously* — so loading refunds before designations
  is a race. Fix: **load designations (`430`) before refunds (`400`).**
  Durable: `validators/GiftTransactionDesignation.md` (wrong theory replaced
  with the resolution), ROADMAP #86.
- **Backwards date windows from independent mock date generation.** Symptom:
  1/40 GiftTransactions failed `INVALID_INPUT` on a due date outside its
  schedule window; root of it, a schedule window generated end-before-start.
  Root cause: `snowfakery_data._snowfakery_field()` mapped every date to an
  *independent* `DateBetween`. Fix (two layers): a `370` SQL guard for the
  NPC instance, and — the generalization — same-object start/end date pairs
  are now ordered *by construction* in mock generation for **any** object.
  Durable: `okf/salesforce-platform/date-range-fields-must-be-ordered.md`,
  ROADMAP #87/#88.
- **Boolean-field result-match + parent Id writeback (Campaign `0/0`).**
  Symptom: Campaign reported `succeeded=0/failed=0` and its real Id never
  wrote back, breaking CampaignMember. Fix: `--fingerprint-columns
  MigrationID__c`. Durable: `validators/CampaignMember.md`, `sample_data/README.md`,
  ROADMAP #85.
- **Stale replicated snapshot for platform-derived Ids.** Symptom: ~10
  CampaignMembers failed `INVALID_CROSS_REFERENCE_KEY` (Person Account
  shadow `PersonContactId` read from a pre-load `dbo.Account` snapshot).
  Fix: re-replicate the parent after it loads (`Account` after Person
  Accounts, `GiftCommitmentSchedule` after `370`). Durable:
  `validators/CampaignMember.md`, `sample_data/README.md`, ROADMAP #85.
- **Runbook missing the `resolve-record-types` prerequisite** (found in the
  clone dry-run): the account transforms join `dbo.RecordTypeMap`, a cache a
  fresh clone doesn't have. Fix: added it as the first load-sequence step.
  Durable: `sample_data/README.md`, PR #37.

## Reusable artifacts produced

- **The clone-clean `sample_data/` bundle** — 10 committed Snowfakery
  recipes + the ordered generate/load/reset runbook (`sample_data/README.md`).
  A fresh clone runs it end-to-end clean; that's the whole deliverable of
  this loop. *Transfers as a pattern* to any NPC fundraising build; the real
  Ids/counts are per-run.
- **Generic start/end date ordering in mock generation** (`snowfakery_data.py`,
  ROADMAP #88) — benefits **every** object on **every** cloud, not just NPC.
- **`bulkops delete --hard-delete` + the `MigrationHardDelete` permission
  set** (`force-app/`) — the reusable "reset an object family the platform
  auto-populates" capability.
- **The data-shape profile** (`data_shape.py`, `build-data-shape-profile` /
  `show-data-shape`) + its surfacing in `assess-migration-readiness` /
  `orchestrator-assess` — machine-readable behavioral shape per object.
- **`gather-okf`** + the `okf/synthetic-data-recipes/` external-recipe
  catalog — active knowledge retrieval so a clone consults before mistakes.
- **The corrected `230-430` transforms** — the auto-created-record handling
  (250/420 doc-only), inherited GiftTransactionDesignations (430), the
  designations-before-refunds ordering, the two-sided due-date clamp.

## Target-platform-only knowledge extracted

Nonprofit Cloud facts, true regardless of migration source, now in
`okf/nonprofit-cloud/` and `validators/`:
- A recurring `GiftCommitment`'s `CreateTransactions` schedule auto-generates
  keyless `GiftTransaction`s (`validators/GiftCommitment.md`).
- A transaction's total designation Amount is capped at `CurrentAmount`
  (`OriginalAmount − RefundedAmount`); refunds reduce it asynchronously
  (`validators/GiftTransactionDesignation.md`).

And two genuinely **cross-cloud** patterns lifted out of the NPC instances
into `okf/salesforce-platform/` (the source-agnostic subject area created
earlier this session):
- Blocked by platform-managed records or state (auto-generated keyless
  children, or a state-lock) — recognize/diagnose/fix.
- Date-range fields must be ordered — same-object pairs → order in
  generation; cross-object date-in-window → transform clamp.

## Process and tooling gaps found

All written into `ROADMAP.md` with full root-cause/fix accounts:
- #84 `--hard-delete` for reset; #85 the reload-sequence fixes (stale
  snapshot, boolean fingerprint, one-sided clamp, orphan row); #86 the
  GiftTransactionDesignation `CurrentAmount` race; #87/#88 date-range
  ordering (NPC + generic); #83 the data-shape profile + consumer.
- The runbook's missing `resolve-record-types` step (PR #37) — a real "the
  docs assumed a cache a clone doesn't have" gap, the kind only a
  from-scratch clone run surfaces.

## Open questions for next time

- **Cloud-level data-shape generalization (deferred).** An org-derived
  profile (`data_shapes/<Object>.json`) still carries org-specifics; turning
  it into reusable `okf/<cloud>/` machine-readable IP (a "promote a profile
  to OKF" step) is designed but unbuilt — the loop's remaining thread.
- **A harder data-shape *scoring* step.** The profile is surfaced as
  advisory today; turning a specific signal into an actual readiness/tier
  *gate* needs deciding which signals should block.
- **datetime date-range pairs aren't auto-ordered** — the generic fix covers
  `date`-typed pairs only (Faker rejects a substituted datetime); datetime
  ranges still rely on the transform layer.
- **Orchestrator Phase 2** (the coarse-approval mechanism) remains unbuilt —
  the assessment commands still only observe and surface, never gate.
