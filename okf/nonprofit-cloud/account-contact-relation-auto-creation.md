---
type: PlatformFinding
title: AccountContactRelation is auto-created when a Contact is inserted with a real AccountId
description: Nonprofit Cloud (AFNP) automatically creates an
  AccountContactRelation (IsDirect=true) the instant a Contact is
  inserted with a real AccountId -- an explicit insert for the same pair
  fails silently (no error surfaced, since the fingerprint-based result
  match never finds anything to correlate). The same auto-creation
  family as GiftCommitmentSchedule.
tags: [npc, afnp, account-contact-relation, automation, platform-finding, household]
timestamp: "2026-07-19"
---
# AccountContactRelation is auto-created on Contact insert

**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build. An explicit `insert` of 16 `AccountContactRelation` rows
(Account/Contact pairs both already loaded earlier in the same build)
reported `submitted: 16, succeeded: 0, failed: 0` — no error at all, a
result that initially looked like a tooling problem rather than a
platform behavior.

**Root cause, confirmed live:** querying the target org directly for
`AccountContactRelation WHERE IsDirect = true` against those same 16
Account/Contact pairs found all 16 already existed, created by the
platform itself the moment each Contact was inserted with a real
`AccountId` — no separate action by this migration ever created them.
The explicit insert attempt collided with the real, already-existing
row on the object's own (Account, Contact) uniqueness, and
`bulk_op()`'s fingerprint-based result matching (built for the normal
"this row either succeeded or failed" case) had nothing to correlate a
result against, since Salesforce's own response didn't map cleanly onto
an insert that was really a silent no-op collision.

This is the same auto-creation family already confirmed for
`GiftCommitmentSchedule` (see
[gift-commitment-schedule-auto-creation.md](gift-commitment-schedule-auto-creation.md))
— Nonprofit Cloud's own automation creates certain child records as a
side effect of a parent/sibling insert, invisible to the Tooling API the
same way (no matching Flow/trigger found against `Contact`, confirmed
live).

**What to do:**
- Never explicitly insert `AccountContactRelation` for an Account/Contact
  pair this same migration is also loading — replicate the real,
  auto-created row first
  (`replicate AccountContactRelation --where "IsDirect = true"`), then
  `update` it with whatever real business fields the auto-creation
  doesn't set (see
  [validators/AccountContactRelation.md](../../validators/AccountContactRelation.md)
  for `IsIncludedInGroup`/`IsPrimaryMember`, the real household-membership
  signal).
- Don't stamp a migration key (e.g. `MigrationID__c`) onto the
  auto-created row — it wasn't created by this migration, so a migration
  key falsely claims ownership; only touch the specific business fields
  that genuinely need a value.
- Match by `AccountId`+`ContactId` (both already known once the parent
  Account/Contact insert has run), not by any local Load table's own
  bookkeeping.

**Executable check:** none yet — this is the same category as
`GiftCommitmentSchedule`'s own auto-generation risk;
`child_record_risk.py`'s empirical diff (run by default from
`analyze-org-risk`) could in principle be extended to check this
relationship too, not yet confirmed live for this specific pair.

# Citations

1. Live-confirmed, 2026-07-19, `NPC_TARGET_v2` — not documented in the
   migration guide's own Appendix B validation tables as of this writing.
