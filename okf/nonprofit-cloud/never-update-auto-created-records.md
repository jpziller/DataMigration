---
type: MigrationPattern
title: Never insert or update a platform auto-created record without real, filtered evidence
description: A migration must not insert OR update a record the target
  platform auto-creates on its own (AccountContactRelation,
  GiftCommitmentSchedule, GiftDefaultDesignation confirmed so far) --
  even a seemingly minor, functionally-motivated field update is out of
  bounds unless real, narrowly-filtered reference data proves a human
  genuinely changes that field. A broad/unfiltered sample can look like
  evidence for a change that real, correctly-scoped data contradicts.
tags: [npc, afnp, auto-created-child-record, methodology, process, hard-rule-11, migration-pattern]
timestamp: "2026-07-21"
---
# Never insert or update a platform auto-created record without real, filtered evidence

## The pattern, confirmed on three objects so far
Nonprofit Cloud auto-creates several child records the instant their
parent is inserted, with no explicit action from the loading migration:

| Auto-created object | Trigger | Real shape confirmed live |
|---|---|---|
| `AccountContactRelation` (IsDirect=true) | Contact insert with a real AccountId | `IsIncludedInGroup=False`, `IsPrimaryMember=False` -- 5/5 real rows |
| `GiftCommitmentSchedule` | GiftCommitment insert with ScheduleType='Recurring' ("regular" cadence) | Real schedule, created via the "Manage Recurring Gift Commitment Schedule" Invocable Action or the nightly NextGen batch |
| `GiftDefaultDesignation` | GiftCommitment insert (any type) | `AllocatedPercentage=100`, `GiftDesignationId` = the org's own real default GiftDesignation |

An explicit `insert` against any of these collides with the real,
already-existing row -- either a silent `succeeded=0/failed=0` (when the
sent columns happen to fingerprint-match badly, see
`okf/nonprofit-cloud/bulk-api-2-csv-semantics.md`) or a hard
`FIELD_INTEGRITY_EXCEPTION`/`"doesn't overlap"`/`"can't exceed 100%"`
rejection, depending on the object.

## The mistake this project made once, and corrected
The first fix built for this pattern (`AccountContactRelation`, NPC
fundraising dogfood build, 2026-07-19) was: don't insert, but DO
replicate the real row and UPDATE it with fields the auto-creation
doesn't set (`IsIncludedInGroup`/`IsPrimaryMember`) -- reasoning that
these were genuinely necessary household-membership signals with no
other way to populate them.

**This was wrong**, caught directly by the user on the very next rebuild
attempt (2026-07-21), not independently discovered: *"you shouldn't be
updating auto created records. not even to add a migration id to it...
the rule to not update the created records is all created records and
not just one object."* Investigated live rather than taken on faith
either direction (per this project's own standing "test and ask
questions, don't brute-force" principle) -- queried every real,
non-migrated, `IsDirect=true` `AccountContactRelation` row in
`NPC_TARGET_v2`:

    IsIncludedInGroup = False, IsPrimaryMember = False -- 5 of 5, zero
    exceptions.

The *original* evidence that justified the update ("IsIncludedInGroup
populated 10/10, mixed True/False") came from an **unfiltered** sample
that, on closer inspection, was actually picking up organization-style
business relationships (`Roles` = Influencer/Decision Maker/Evaluator/
Other) rather than genuine household `IsDirect=true` rows -- a
materially different population. Filtering to the exact real shape this
migration actually produces showed the opposite of what was assumed.

The same day, `GiftDefaultDesignation` hit the identical family of
mistake in its first (insert, not update) form -- 15 of 15 explicit
inserts failed live once the real auto-created row was found via direct
query, and the correct fix (per the now-corrected rule) was to skip the
object entirely, not replicate-and-update it either.

## The rule, generalized
1. Before building a transform for any object that a load-order
   dependency analysis or prior finding suggests might be
   platform-managed, check empirically whether the org already creates
   one automatically (direct query against a few real, already-inserted
   parent Ids -- cheap, and the only reliable signal; the Tooling API
   can't see this kind of managed-package-internal automation, the same
   blind spot `child_record_risk.py` exists to work around).
2. If it does: **never insert.** That's the easy, already-established
   half of this rule.
3. **Also never update it** -- even for a field that seems obviously
   necessary, even for something as minimal as a migration key -- unless
   real, narrowly-filtered reference data (matching the *exact* shape
   this migration's own auto-created rows will have, e.g. `IsDirect =
   true` specifically, not "any row on this object") shows a human
   genuinely changes that field in normal use. A plausible-sounding
   field name and a broad sample showing "some rows have this set" is
   not evidence -- filter to the real matching population first, the
   same lesson `validators/PartyRelationshipGroup.md`'s own `Category`
   correction already established once, now confirmed on a second,
   independent object.
4. When in doubt, the default is silence: leave the auto-created row
   exactly as the platform made it. This mirrors Hard Rule 11's own
   "don't invent a value just because a field exists and the platform
   would accept one" -- extended here to updates, not just inserts.

# Citations
1. Live-confirmed, 2026-07-21, `NPC_TARGET_v2` -- both the
   `AccountContactRelation` correction and the `GiftDefaultDesignation`
   finding, second NPC fundraising dogfood rebuild attempt
   (`attempts/2026-07-21-npc-dogfood-v2/`).
2. User correction, same session, relayed directly.
