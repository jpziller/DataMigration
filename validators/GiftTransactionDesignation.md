---
type: ObjectValidator
title: GiftTransactionDesignation validator
description: Object-specific findings for GiftTransactionDesignation
  (Nonprofit Cloud/AFNP) -- CONFIRMED by a real Nonprofit Cloud architect
  (Ali) on 2026-07-24 -- a transaction's designations must be INHERITED from
  its parent's real Gift Default Designation(s) (GiftCommitment, else
  Opportunity, else Campaign, else the org-wide default), mirroring the
  same designation(s) and split percentages -- not independently chosen.
  The earlier round-robin-across-fabricated-designations approach in this
  build's own 430 script was fundamentally the wrong mechanism, not a
  minor miss. Also -- a split's two Amounts must sum to exactly the
  transaction's OriginalAmount (rounding-safety), and a standalone,
  fully-refunded transaction's first-insert failure remains genuinely
  unresolved.
tags: [object-validator, gift-transaction-designation, nonprofit-cloud, afnp, gift-transaction, gift-default-designation]
timestamp: "2026-07-24"
---
# GiftTransactionDesignation validator

## Designations must be INHERITED from the parent's real Gift Default Designation(s) -- confirmed by a real Nonprofit Cloud architect
**Found:** 2026-07-24, a Nonprofit Cloud architect (Ali) reviewed a real
build's live output and flagged that its GiftTransactionDesignation rows
existed but didn't match the GiftDefaultDesignation on their parent
records -- this build's own `430_gifttransactiondesignation_load.sql`
was picking designations via round-robin across a fabricated pool of
`GiftDesignation` records, entirely independent of
`GiftDefaultDesignation`. That's the wrong mechanism, not a minor
inaccuracy -- see [GiftDefaultDesignation.md](GiftDefaultDesignation.md)
for why: this project's own build never inserts/updates
`GiftDefaultDesignation` (a platform auto-created record, per that same
doc), so every commitment's real default was always going to be the SAME
org-wide default designation, not one of this build's own 6 fabricated
`GiftDesignation` rows -- the round-robin logic was fabricating a pattern
with no real basis at all.

**The real rule, confirmed directly:** "The idea is that the GDD
represents the donor's intent, so should almost always be written onto
the GTD." A transaction's GiftTransactionDesignation(s) should mirror its
parent's GiftDefaultDesignation(s) exactly -- same designation(s), same
split. **GDDs can be multiple**: "you might have a Gift Commitment with 3
equal split GDDs; you'd expect the associated gift transactions to each
have 3 equal split GTDs." A transaction split across designations that
DON'T match anything on the parent, or a manual override replacing the
inherited default entirely, is possible but "pretty rare" -- not the
default case to design for.

**Parent hierarchy, confirmed directly:** GiftCommitment, if there is
one; if not, Opportunity; if not, Campaign; if none of those, the
org-wide default designation ("usually something like General Fund or
Unrestricted or Annual Fund"). "Gift Commitment inherits from Opportunity
so those will mostly match (although it's not required)."

## The org-wide default designation is identifiable dynamically, not by hardcoding an Id
**Found:** same session, confirmed live in `NPC_TARGET_v2`: the real
org-wide default designation ("General fund", Id starting `6gdfn...`) has
`GiftDesignation.IsDefault = true` -- the correct way to find it in any
org, never a hardcoded Id. It's the same designation every auto-created
`GiftDefaultDesignation` in this org already points to (see
[GiftDefaultDesignation.md](GiftDefaultDesignation.md)).

## GiftDefaultDesignation auto-creation ALSO correlates with ScheduleType='Recurring' -- the same "regular vs. irregular" pattern as GiftCommitmentSchedule
**Found:** same session, checking all 15 real `GiftCommitment` records in
this build for an auto-created `GiftDefaultDesignation`: **all 12
Recurring-type commitments have one** (100%, pointing at the org-wide
default); **none of the 3 Custom-type commitments do**. This is the exact
same "regular (Recurring) gets platform automation, irregular (Custom/
pledge) doesn't" split already confirmed for `GiftCommitmentSchedule`
auto-creation (see [GiftCommitmentSchedule.md](GiftCommitmentSchedule.md))
-- strongly suggesting the same underlying platform mechanism (the
NextGen commitment processing job, or the "Manage Recurring Gift
Commitment Schedule" action) creates both as a side effect for regular
commitments, not two independent behaviors. **Also confirmed live:
Campaign never gets an auto-created GiftDefaultDesignation** in this org
(checked 3 real Campaign records, zero GDD rows) -- so a Campaign-linked
(not commitment-linked) transaction in this build's own data always falls
through to the org-wide default in practice, since there's no
Opportunity object in this build's scope and Campaign itself never has
one to inherit from.

**What to do:** replicate `GiftDefaultDesignation` (read-only -- never
insert/update it, per [GiftDefaultDesignation.md](GiftDefaultDesignation.md))
and replicate `GiftDesignation` (needs `--raw` -- see the real
`replicate.py` decimal-precision bug noted in the script header) filtered
to `IsDefault = true` for the fallback. For each `GiftTransaction`: use
its `GiftCommitmentId`'s real GDD(s) if any exist; else its `CampaignId`'s
real GDD(s) if any exist; else the org-wide default at 100%. Test each
stage with `NOT EXISTS`, not a bare `IS NULL` on the FK column -- a
commitment CAN be linked but still have no GDD (the Custom-type gap
above), and that case must still fall through the chain instead of
silently producing zero designation rows. Mirror each GDD's own
`AllocatedPercentage` onto the corresponding `GiftTransactionDesignation`
row (see the rounding rule below for multi-way splits). Implementation:
`sql/transformations/430_gifttransactiondesignation_load.sql` --
**PROMOTED 2026-07-24** from `attempts/2026-07-21-npc-sample-v2/` once
proven live (see `CLAUDE.md`'s "Library vs. attempts workspace" section);
this is now the one canonical copy, the attempts-workspace copy was
removed per the Replace-model convention.

**RESOLVED live, 2026-07-24:** the corrected transform ran against
`NPC_TARGET_v2` -- the 59 wrong (round-robin) rows were deleted and 40
correct rows built; 39 of 40 loaded cleanly, each one now genuinely
mirroring its parent's real GDD (all 40 resolved to the same real
org-wide default, "General fund", since every GDD in this org --
auto-created or fallback -- points at it). The 1 failure was the
already-documented, pre-existing "standalone + fully-refunded" gap below
(`GiftTransactionId 6trfn000000s0cnAAA`, `GiftCommitmentId` NULL,
`OriginalAmount` 78364.80 -- the same transaction as the original P9
finding). Hitting the identical failure again with a completely different
designation/Id assigned to it is itself useful evidence: it rules out
"wrong designation" as a contributing factor and narrows the open gap
below to genuinely being about the standalone+fully-refunded combination
alone, independent of which `GiftDesignationId` is sent.

## A split's two Amounts must sum to exactly the transaction's OriginalAmount

## A split's two Amounts must sum to exactly the transaction's OriginalAmount
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
sample data build -- 1 of 60 generated rows (a 60/40 split across two
designations) failed `FIELD_INTEGRITY_EXCEPTION: "Adjust the designations
so that the total designation amount doesn't exceed the transaction
amount."` Root cause: computing each share independently as
`ROUND(pct * OriginalAmount, 2)` can round BOTH shares up on an odd-cent
amount, overshooting the true total by a cent.
**What to do:** compute the primary share as a real rounded value, and
the secondary share as the exact remainder (`OriginalAmount -
PrimaryAmount`), never as its own independently-rounded percentage --
the two always sum to exactly the original amount this way. See
`sql/transformations/430_gifttransactiondesignation_load.sql`.

## Amount may be locked once the parent GiftTransaction reaches a certain state -- unresolved
**Found:** same session, while correcting the one already-failed row
above. The first (pre-fix) load already created a `P38` row with the old,
unrounded `Amount` (7405.518); once the fix computed a clean 7405.52/
4937.01 split, the plan was to correct `P38`'s `Amount` via a plain
`update` (not touching the non-updateable `GiftTransactionId`) and then
insert the now-correctly-summing `S38`. **The `update` itself failed**
with the identical `FIELD_INTEGRITY_EXCEPTION`, even though 7405.52 alone
is well under the transaction's 12342.53 total and no sibling `S38` row
existed yet to conflict with. This strongly resembles the same "field
locked after Status change" pattern already confirmed for
`GiftCommitment.CurrentGiftCmtScheduleId` and
`GiftTransaction.GiftCommitmentScheduleId` (both in
[GiftCommitmentSchedule.md](GiftCommitmentSchedule.md)/
[GiftTransaction.md](GiftTransaction.md)) -- but this specific instance
was not chased to a confirmed root cause or a working fix; the
delete-and-reinsert pattern that resolved the other two cases was not
attempted here. **Left as a known, accepted gap** in this practice
build -- 59 of 60 GiftTransactionDesignation rows loaded correctly (1
transaction, LoadId 38, has only its 60% primary allocation, no 40%
secondary). A real client engagement hitting this should try the same
delete-and-reinsert approach documented for the other two cases before
assuming it's a different root cause.

## SECOND, SEPARATE occurrence (2026-07-21) -- corrects the "locked after Status change" theory above, still unresolved
**Found:** second NPC fundraising sample data rebuild attempt, a completely
fresh insert this time (not a follow-up correction like LoadId 38
above) -- `P9`, a standalone (no split, no `S9` counterpart) 100%
designation, failed on its very first insert attempt with the identical
`FIELD_INTEGRITY_EXCEPTION: "Adjust the designations so that the total
designation amount doesn't exceed the transaction amount."` This alone
already narrows the picture: since this was a first-ever insert, not an
update against an already-loaded row, the original "field locked after
Status change" theory (which specifically explains why an *update*
would fail) doesn't fit this occurrence -- something about this specific
transaction rejects a fresh insert outright.

**Investigated live, two hypotheses tested and ruled out:**
1. **Rounding/precision mismatch** -- checked the sent `Amount` against
   the org's live `OriginalAmount` at 10 decimal places: both exactly
   `78364.8000000000`. Not a rounding issue this time (unlike LoadId 38
   above, which genuinely was one).
2. **Fully-refunded transactions can't accept a 100% designation** -- the
   failed transaction is `IsFullyRefunded = true`
   (`RefundedAmount = OriginalAmount = 78364.8`). But this build's
   *other* refunded transaction (`P30`/`S30`, a 60/40 split) is **also**
   `IsFullyRefunded = true` with `RefundedAmount` exactly equal to its
   own `OriginalAmount` too -- and it succeeded cleanly. Refund status
   alone does not explain the difference.

**The one real, remaining difference found:** the failed transaction
(`P9`) is **standalone** -- `GiftCommitmentId` is blank. The succeeded
one (`P30`) is **commitment-linked** (`GiftCommitmentId`/
`GiftCommitmentScheduleId` both populated). No pre-existing/auto-created
`GiftTransactionDesignation` row was found on the failed transaction
either (queried directly, zero rows), ruling out an auto-created-row
collision the same family as
[AccountContactRelation](AccountContactRelation.md)/
[GiftDefaultDesignation](GiftDefaultDesignation.md).

**Why this is not being chased further right now:** this build only
produced 2 refunded transactions total -- one of each shape (standalone
vs. commitment-linked). "Standalone + fully-refunded fails, commitment-
linked + fully-refunded succeeds" is an n=1-vs-n=1 comparison, not a
confirmed rule -- a real, concrete lead, not proven causation.
Confirming it needs one of: (a) a real migration with enough refunded,
standalone transactions to test the pattern at real scale, (b) more
real, human-created reference data in `NPC_TARGET_v2` covering this
combination (a task for Ali, not something this framework can generate
meaningfully), or (c) official Nonprofit Cloud documentation on how
refunds interact with designation validation, not yet found. Per this
project's own "test and ask questions, don't brute-force" principle,
guessing further from a 2-example sample isn't worth it -- this stays a
documented, open gap until one of those three becomes available.
**What to do in the meantime:** treat "standalone + fully-refunded"
GiftTransactionDesignation inserts as a known risk; a real client
engagement hitting this should check `GiftCommitmentId`/refund status
before assuming the earlier rounding-based explanation applies.
