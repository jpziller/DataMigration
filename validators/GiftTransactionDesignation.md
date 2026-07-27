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
  transaction's OriginalAmount (rounding-safety), and the total designation
  Amount is capped at CurrentAmount (OriginalAmount minus RefundedAmount),
  which refunds reduce asynchronously -- so designations must load BEFORE
  refunds (resolved 2026-07-26, correcting an earlier wrong "standalone"
  theory).
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

## RESOLVED (2026-07-26): the real cause is CurrentAmount, and it's a refund-vs-designation LOAD-ORDER race -- load designations BEFORE refunds
**This supersedes the earlier "standalone vs. commitment-linked" theory,
which was wrong** -- it was an n=1-vs-n=1 coincidence. Nailed down live on
the 2026-07-26 reload test, which reproduced the same
`FIELD_INTEGRITY_EXCEPTION: "Adjust the designations so that the total
designation amount doesn't exceed the transaction amount"` and let it be
diagnosed properly against a full set of refunded transactions.

**The mechanism.** `GiftTransaction.CurrentAmount` is a calculated field
equal to `OriginalAmount - RefundedAmount` (confirmed live: a partial
refund of 59099.30 on a 78022.75 gift left `CurrentAmount = 18923.45`).
The platform caps a transaction's **total designation Amount at
CurrentAmount**, not at OriginalAmount -- the error text says "transaction
amount" but it means the *current* (post-refund) amount. So a
fully-refunded transaction has `CurrentAmount = 0` and rejects **any**
designation Amount > 0.

**Why it's intermittent (the actual "standalone" red herring).** A
`GiftRefund` reduces `CurrentAmount` **asynchronously**. When the load
inserts refunds (`400`) before designations (`430`), it's a race: for one
fully-refunded transaction the refund had already dropped `CurrentAmount`
to 0 when the designation inserted (**fails**), while for another
identically fully-refunded transaction the designation inserted *first*
and persists fine afterward even though `CurrentAmount` later goes to 0
(**succeeds**). Both live cases confirmed on 2026-07-26: `SNOWFAKE-GT-21`
(`CurrentAmount=0`, designation failed, 0 loaded) vs. `SNOWFAKE-GT-26`
(also `CurrentAmount=0`, but its 46267.65 designation was created before
the refund landed and coexists with `CurrentAmount=0`). The old
`GiftCommitmentId`-blank correlation was pure coincidence.

**The fix (deterministic).** **Load `GiftTransactionDesignation` (`430`)
BEFORE `GiftRefund` (`400`)**, right after the transactions themselves.
Then every designation is created against the full, pre-refund
`CurrentAmount`, and the refund reduces it afterward -- exactly the order
`SNOWFAKE-GT-26` demonstrated works and persists. No transform change is
needed; this is a load-ordering rule (the numbering `400 < 430` reflects
dependency-build order, not load order -- both only depend on the
transaction). `sample_data/README.md`'s sequence is updated accordingly.

**Residual caveat.** This only helps a *fresh* load. A transaction that is
**already** fully refunded in the org when you go to designate it
(`CurrentAmount = 0`) genuinely cannot take a designation after the fact --
that's a real platform limit, not a bug. If a source system has a
designation on a gift that was later fully refunded, preserve it by
loading the designation before applying the refund, per the fix above.
