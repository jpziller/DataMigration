---
type: MigrationPattern
title: Name field createable-flag quirk (Nonprofit Cloud/AFNP)
description: describe()'s createable flag reports false for Name on
  several Nonprofit Cloud fundraising/CRM objects, but Name is genuinely
  required and acceptable to send on insert -- confirmed independently
  on 3 separate objects, a real platform characteristic worth checking
  on any new AFNP object, not a one-off.
tags: [npc, afnp, name-field, describe, createable, nonprofit-cloud, data-quality]
timestamp: "2026-07-17"
---
# Name field createable-flag quirk (Nonprofit Cloud/AFNP)

**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept, across
three separate objects independently — `GiftCommitment`, `GiftTransaction`,
`PartyRelationshipGroup` (full object-level detail in each object's own
validator: [validators/GiftCommitment.md](../../validators/GiftCommitment.md),
[validators/GiftTransaction.md](../../validators/GiftTransaction.md),
[validators/PartyRelationshipGroup.md](../../validators/PartyRelationshipGroup.md)).

**What happens:** `describe(<Object>)` reports `Name` as
`createable: False`. This framework's own pre-flight check
(`bulkops.py`'s `_preflight_check()`) treats a required-but-not-sent
field on insert as a warning, not a hard stop, since automation could
still default it — but on these objects nothing does, and the real Bulk
API 2.0 call fails with `REQUIRED_FIELD_MISSING: Required fields are
missing: [Name]`.

**Why this is a platform-level finding, not three unrelated bugs:** the
same exact signature recurred on three structurally different objects in
one migration pass. `describe()`'s `createable` flag can't be trusted at
face value for `Name` on this object family — and critically, it gives
**no way to distinguish** a truly read-only, auto-generated `Name` (e.g.
`GiftCommitmentSchedule.Name`, confirmed genuinely safe to omit — never
hit this failure) from a required-but-mislabeled one, from the describe()
metadata alone. Both report the identical `createable: False`.

**What to do on any new AFNP object this framework hasn't loaded data
into yet:** don't trust the pre-flight warning as evidence the load will
succeed. Either send a real `Name` value defensively (reuse a natural
source field — this migration reused the source record's own `Name` in
every case it hit this) or do a small live test insert first to confirm
whether this particular object's `Name` is really optional. A field
`describe()` marks required (independent of the `createable` flag) is
the more reliable signal to watch — cross-reference that rather than
`createable` alone.

**Not yet built:** an automated pre-flight enhancement that escalates
specifically this ambiguity (a field independently confirmed `required`
*and* `createable: False`) to a louder, harder-to-miss warning than the
current generic wording. Worth considering if this recurs on a 4th
object in a future engagement.
