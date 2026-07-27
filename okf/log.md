# okf bundle update log

## 2026-07-27
* **New (machine-readable IP)**: cloud-level data-shape profiles under
  [nonprofit-cloud/data-shapes/](nonprofit-cloud/index.md) — `GiftCommitment`,
  `GiftCommitmentSchedule`, `GiftTransaction` (ROADMAP #83). Committed JSON
  produced by generalizing a live org profile with every org-specific detail
  stripped (org custom fields, automation counts, field population,
  auto-generation rates), keeping only cloud-true structure, auto-generated-child
  relationships, and date-range pairs. New commands `generalize-data-shape`
  (producer) and `show-data-shape --cloud` (consumer); `gather-okf` now
  surfaces them alongside the prose docs, so a fresh clone consults an
  object's platform behavior before ever profiling its own org.
* **New**: [Date-range fields (start/end) must be ordered](salesforce-platform/date-range-fields-must-be-ordered.md)
  -- generalizes the Nonprofit Cloud backwards-schedule-window finding
  (ROADMAP #85/#87) into a cross-cloud pattern. Any object with a
  start/end date pair needs end >= start; mock generators produce each
  date independently and can make it backwards. Same-object pairs are now
  ordered generically at generation time (`snowfakery_data.py`, ROADMAP
  #88) and surfaced in `build-data-shape-profile`; a cross-object
  date-in-window constraint stays a transform-layer clamp. Answers "do we
  have any generic validation that start/end dates won't have issues on
  ANY object" -- now yes.

## 2026-07-26
* **New subject area**: [Salesforce platform (cross-cloud) patterns](salesforce-platform/index.md)
  with its first pattern, [Blocked by platform-managed records or
  state](salesforce-platform/blocked-by-platform-managed-records-or-state.md)
  -- the generic, cross-cloud shape behind a class of resets/updates that
  fail even though a migration-key-scoped query says the data is clean
  (auto-generated child records with no migration key, or a state lock).
  How to recognize, diagnose (query the real relationship, not your key),
  and fix it. Found live during the NPC sample-data reset test (ROADMAP
  #84); this generalizes it so the next cloud's version is recognized
  before it bites.
* **Correction**: [full-org-reset-between-build-attempts.md](nonprofit-cloud/full-org-reset-between-build-attempts.md)
  -- the GiftCommitment delete block was misdiagnosed as recycle-bin/async-
  purge residue; the real cause is live, auto-generated GiftTransactions
  from recurring schedules (no MigrationID__c). Corrected the reset to
  scope the GiftTransaction delete by GiftCommitmentId, plus --hard-delete.

## 2026-07-25
* **New subject area**: [Synthetic-data recipes (external sources +
  coverage)](synthetic-data-recipes/index.md) with its first reference,
  [external-recipe-sources.md](synthetic-data-recipes/external-recipe-sources.md)
  -- a describe-and-link catalog of the shared Snowfakery recipe libraries
  that already exist (SFDO community, CumulusCI, Snowfakery), per-cloud
  coverage + gaps (Consumer Goods/Sales/Service largely uncovered), and
  the limit that upstream recipes give structure, not the auto-creation
  behavior this repo learns empirically. Researched live 2026-07-25. See
  ROADMAP.md #83.
* **Fix**: root [index.md](index.md) now lists the `nonprofit-cloud`
  subject area (it existed but had never been added to the root listing).
* **Tie-in**: this bundle is now actively surfaced, not just present --
  the new `gather-okf` command and CLAUDE.md's Standard Workflow make
  consulting relevant OKF a required step before building, so a clone
  doesn't rediscover this knowledge after a mistake (ROADMAP.md #83).

## 2026-07-16
* **Update**: Added
  [New org, not an in-place upgrade](npsp-to-npc/new-org-vs-in-place.md)
  -- Salesforce's own §2.3.1 recommendation, surfaced by a direct
  question about whether a real migration needs one org or two.
* **Initialization**: Created the bundle root and its first subject area,
  [NPSP to Nonprofit Cloud (AFNP)](npsp-to-npc/index.md), from a full
  review of Salesforce's official migration guide and companion mapping
  workbook. See ROADMAP.md #72.
