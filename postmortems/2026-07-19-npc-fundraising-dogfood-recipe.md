# Post-Mortem: NPC Fundraising/Donor-Management Snowfakery Dogfood Recipe

**Date:** 2026-07-19
**Scope:** Ignore NPSP entirely — use this framework's own
`generate-related-mock-data` (Snowfakery) engine to build a "perfect,"
human-shaped practice dataset across the **full** NPC fundraising/donor-
management object surface (20 objects, the official migration guide's
own §5/§7 list — not just the 11 objects the earlier PoC's NPSP-sourced
data happened to route through), prefixed `Snowfake-`, loaded all the
way to a real completion in `NPC_TARGET_v2` per Hard Rule 11's explicit
exception for framework-generated data. PR #20
(`feature/npc-fundraising-dogfood-recipe`).

## What went well

- **Hard Rule 11's framework-generated-data exception again earned its
  keep**, this time at a much larger scope than the PoC (20 objects vs.
  11, zero real source system at all vs. a real NPSP org) — no field-
  mapping-completeness ceiling was hit anywhere in this build.
- **`sample-reference-records` reconnaissance before generating anything
  (Phase 0) paid for itself repeatedly**: it caught the
  `ContactContactRelation.PartyRoleRelationId` gap (100% real population,
  would have shipped null), confirmed the `ContactPointAddress`
  Account-vs-Individual scoping and its real, sparser-than-`describe()`
  field shape, and confirmed `GiftSoftCredit.RecipientId`/
  `GiftDefaultDesignation.ParentRecordId`'s real target types — all
  *before* a single row was generated, not discovered after a failed
  load.
- **Verifying every load's real record count via direct SOQL query**
  (never trusting `bulk_op()`'s own summary alone) remained essential —
  it caught two *new* false-negative classes this pass (see below), on
  top of the writeback-race class the PoC already knew about.
- **The dry-run-then-real pattern for the `sf project deploy start`
  metadata deploy** (extending `MigrationID__c` to 7 new objects) stayed
  clean on the first try — no surprises, unlike the PoC's Phase 1 deploy.
- **The corrective-reload playbook** (`docs/MIGRATION_PLAYBOOK.md`'s
  `<Object>_Delete` pattern) generalized correctly to a genuinely new
  situation it wasn't originally written for: not a bug-fix reload of an
  already-migrated object, but clearing an *incorrect field value* on a
  handful of already-loaded records mid-build (the `GiftCommitmentSchedule`
  ExpectedEndDate correction, the `GiftTransaction`
  `GiftCommitmentScheduleId` corrections) via the same delete-and-reinsert
  technique the playbook already named for the "Status locks the field"
  case.
- **User's live mid-build correction** (don't stamp `MigrationID__c` on
  a platform auto-created row) was right and led directly to finding a
  real framework bug (`_writeback_inplace()`'s destructive Id-nulling) —
  a good example of a correction paying for itself beyond the immediate
  fix.

## What went poorly (and what was fixed)

- **`snowfakery_data.py`'s `build_recipe()` computed circular-dependency
  detection from every reference-field edge, including non-createable
  ones.** `Account.PersonContactId` (the reverse of `Contact.AccountId`,
  present on `describe()` but never sendable) wrongly triggered
  "Unresolved circular dependencies" for `Account`+`Contact` — the single
  most common parent+child pairing this command exists for. **Fix**:
  filter edges to createable fields only before cycle detection, matching
  what the recipe's own fields actually end up containing.
- **Salesforce auto-creates `AccountContactRelation` (`IsDirect=true`)
  the instant a Contact is inserted with a real `AccountId`** — the same
  auto-creation family as `GiftCommitmentSchedule`, not previously known
  to apply here. An explicit insert collided silently (submitted 16,
  succeeded 0, failed 0 — no error at all, since the fingerprint match
  never found anything real to correlate). **Fix**: replicate the real
  auto-created rows and `update` them with only the fields the
  auto-creation doesn't set.
- **A boolean sent column can silently break `bulk_op()`'s default
  result-matching fingerprint, with zero error surfaced.** Hit
  repeatedly (`AccountContactRelation`, `ContactPointAddress`) — real DML
  fully succeeded, `bulk_op()` reported `succeeded=0, failed=0`.
  Salesforce echoes a sent boolean back in a different string
  representation than pandas' CSV export used. **Fix (workaround)**:
  always pass `--fingerprint-columns` (the real Id when already known, or
  the migration key) for any object whose Load table sends a boolean
  column, proactively rather than reactively.
- **A real bug in `bulk_op()`'s own writeback, found while fixing the
  above**: `_writeback_inplace()` unconditionally overwrote `id_column`
  with `NULL` on a failed fingerprint match — destructive when the caller
  had supplied a real, correct Id going in (exactly the
  `AccountContactRelation` correction case). **Fixed**: `COALESCE`
  instead of overwrite; no behavior change for the ordinary insert case.
- **A second real framework bug, found fixing `GiftRefund`**: pyodbc's
  `fast_executemany` (enabled globally) infers a bound string parameter's
  buffer size from an early row in a writeback batch, then truncates a
  later, longer one (`String data, right truncation`), crashing the whole
  writeback instead of recording per-row errors. Triggered by real,
  widely-variable-length Salesforce validation messages. **Fixed**: one
  `execute()` per row in `_writeback_inplace()` instead of a single
  executemany-style call.
- **Clearing a field via Bulk API 2.0 CSV needs the literal `#N/A`, not
  a blank cell** — a blank cell on an update is a no-op, not "set to
  null." Hit twice: correcting the wrongly-set `MigrationID__c` on
  `AccountContactRelation`, and clearing a duplicate
  `GiftCommitmentScheduleId` on `GiftTransaction`.
- **`GiftCommitmentScheduleId` becomes fully immutable once
  `GiftTransaction.Status` leaves `Unpaid`/`Pending`** — even a correctly-
  sent `#N/A` is rejected. A delete-and-reinsert was required, same
  pattern as the PoC's own corrective-reload precedent.
- **A previously-"confirmed" finding did not hold up a second time.**
  The PoC's own `GiftCommitmentSchedule` auto-creation finding (3/3, then
  6/6 confirmed live) predicted every one of this build's 12 Recurring-
  type `GiftCommitment`s would get an auto-created schedule. Zero did —
  verified from both directions, confirmed stable over an extended
  period (not an async delay), confirmed that updating an already-inserted
  commitment's fields afterward does not retroactively trigger it (a
  delete-and-reinsert experiment was needed to confirm this cleanly).
  Root platform cause remains genuinely unclear. **Fix**: rewrote the
  schedule transform to a defensive check-first pattern — replicate,
  then only explicitly insert whatever's actually missing — safe under
  either platform behavior, instead of assuming one from a prior
  session's result.
- **Several independently-generated Snowfakery fields collided with
  real cross-field or cross-object constraints**, none anticipated by
  the plan: `Campaign.EndDate` before `StartDate`; `GiftCommitment`'s
  `ExpectedEndDate` conflicting with its auto-defaulted
  `RecurrenceType='OpenEnded'`; `GiftTransaction.TransactionDueDate`
  missing/preceding its linked schedule's `StartDate`; a Custom-type
  `GiftCommitmentSchedule` accepting only one linked `GiftTransaction`
  (with a real Bulk API batch race letting 3 briefly violate this before
  platform revalidation caught it); `GiftRefund` requiring its parent
  transaction to be `Paid` with `Amount`/`Date` bounded by it;
  `GiftSoftCredit.PartialAmount`/`PartialPercent` being mutually
  exclusive; a `GiftTransactionDesignation` split's two `Amount`s needing
  to sum to an *exact* remainder, not two independently-rounded shares.
  All fixed except one (see below). **General lesson**: Snowfakery
  generates every field independently, with zero awareness of sibling
  fields, parent objects, or objects assigned later in the same SQL —
  every cross-field/cross-object business rule has to be enforced
  explicitly in the transform layer, never assumed satisfied by chance.
- **One known, accepted gap**: correcting a `GiftTransactionDesignation`
  row's already-loaded `Amount` (to fix the remainder-rounding issue
  above) hit what looks like the same "field locked after Status change"
  pattern found twice elsewhere this session, but wasn't chased to a
  confirmed root cause or a working fix — 1 of 60 rows is missing its
  second (40%) split allocation. See
  [validators/GiftTransactionDesignation.md](../validators/GiftTransactionDesignation.md).

## Reusable artifacts produced

- `sql/transformations/230-430_*.sql` — 21 scripts across 11 build
  groups, in real dependency order, covering all 20 objects. Every
  script already holds its final, live-corrected logic (fixes were
  applied in place during the build, not left as separate patch scripts)
  — a fresh run from an empty org should reproduce the corrected
  behavior directly, without repeating this session's own trial-and-error.
- `force-app/main/default/objects/{ContactContactRelation,ContactPointAddress,ContactPointPhone,ContactPointEmail,GiftRefund,GiftSoftCredit,GiftDefaultDesignation}/fields/MigrationID__c.field-meta.xml`
  + the extended `MigrationFieldAccess` permission set — 7 new objects,
  joining the PoC's original 13.
- `migration_run_book.xlsx`, tab `NPC_Fundraising_Dogfood`.
- Two real `bulkops.py` fixes (`_writeback_inplace()`'s `COALESCE` and
  per-row `execute()`) and one `snowfakery_data.py` fix (createable-only
  edge filtering) — these benefit every future user of
  `generate-related-mock-data`/`bulkops`, not just this project.

Full account of what transfers directly to the next rebuild pass vs. what
would need redoing for a real client's own data:
[okf/nonprofit-cloud/fundraising-dogfood-reference-implementation.md](../okf/nonprofit-cloud/fundraising-dogfood-reference-implementation.md).

## Target-platform-only knowledge extracted

All source-agnostic (true of NPC/AFNP regardless of migration source),
written into `okf/nonprofit-cloud/`:
- `account-contact-relation-auto-creation.md` — new.
- `contact-points.md` — new (ParentId polymorphism, real field shape).
- `bulk-api-2-csv-semantics.md` — new (`#N/A` null-clearing, boolean
  fingerprint-matching risk — general Bulk API 2.0 behavior, not
  NPC-specific, but discovered here and directly relevant to any future
  NPC migration using this framework's own tooling).
- `gift-commitment-schedule-auto-creation.md` — corrected in place (the
  "always auto-creates" claim downgraded to "sometimes, check first").
- `gift-transaction-validations.md` — extended with the
  `TransactionDueDate`/single-transaction-for-Custom-schedule findings.

## Process and tooling gaps found

- `snowfakery_data.py`'s `build_recipe()` edge-filtering bug (see above)
  — fixed this pass, benefits every future `generate-related-mock-data`
  call.
- `bulkops.py`'s `_writeback_inplace()` — two real bugs (destructive
  Id-nulling, fast_executemany truncation crash), both fixed this pass.
- No CLI-level guard nudges a caller toward `--fingerprint-columns` when
  a Load table's own columns include a boolean or long-text field — this
  is still a manual judgment call the caller has to remember to make.
  Worth a future `bulkops` pre-flight advisory (not a hard block, since
  the default fingerprint is still correct for plenty of objects).
- The `GiftTransactionDesignation.Amount`-locked-after-Status-change
  question (see the accepted gap above) is a real open tooling/process
  gap, not just a data-shape one — a future session should try the same
  delete-and-reinsert approach already proven twice this session before
  assuming it's a genuinely different root cause.

## Open questions for next time

- **The `GiftTransactionDesignation` Amount-lock gap** (1 of 60 rows) —
  worth a focused follow-up before the next rebuild, since the fix
  pattern (delete + reinsert) is already known and just wasn't applied
  here.
- **The `GiftCommitmentSchedule` auto-creation root cause remains
  unconfirmed** — two sessions have now observed opposite behavior (3/3
  auto-created vs. 12/12 not) against the same org, and the difference
  wasn't isolated. If a third data point ever surfaces (a client
  engagement, another dogfood pass), compare Bulk-API-batch-size,
  Bulk-API-vs-UI-insert-context, and exact field population against both
  prior sessions' own data rather than starting from scratch again.
- **Volumes were a judgment call, not evidenced** — 8 households, 5
  organizations, 10 person accounts, 40 gift transactions, etc. A next
  rebuild pass could reasonably scale these up or down; nothing in this
  pass's own design locks the volumes in as "correct."
- **The next planned step** (per the user, 2026-07-19): purge every
  migrated record from `NPC_TARGET_v2` and rebuild from a blank slate,
  keeping only the Migration Run Book, mapping docs, and these now-
  cleaned transform scripts. This post-mortem, the OKF updates, and the
  mapping docs it produced are explicitly meant to make that rebuild
  faster and cleaner than this one was — not just a retrospective record.
