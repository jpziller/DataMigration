---
type: PlatformFinding
title: GiftCommitmentSchedule is auto-created for "regular" Recurring-type GiftCommitments
description: Nonprofit Cloud (AFNP) creates a GiftCommitmentSchedule for
  a "regular" recurring GiftCommitment (e.g. Monthly) -- confirmed by
  both a live 6/6 pattern and a human Nonprofit Cloud architect (Ali).
  "Irregular" pledge-type commitments don't get this, or only get the
  first commitment covered. The real trigger is either the "Manage
  Recurring Gift Commitment Schedule" Invocable Action or the nightly
  "NextGen commitment processing job" -- exact mechanism still open.
tags: [npsp, npc, afnp, gift-commitment, gift-commitment-schedule, automation, platform-finding, nextgen]
timestamp: "2026-07-19"
---
# GiftCommitmentSchedule is auto-created for Recurring-type GiftCommitments

**Found:** 2026-07-18, tracing a second architect's live-review finding (a
migrated `GiftTransaction` missing its `GiftCommitmentScheduleId`) back to
its actual root cause. This project's own `170_npc_giftcommitmentschedule_from_rd_load.sql`
originally tried to explicitly insert a `GiftCommitmentSchedule` for all 4
Recurring-Donation-derived `GiftCommitment` records. 3 of the 4 inserts
failed live with:

```
FIELD_INTEGRITY_EXCEPTION: You can create the gift commitment schedule
only when it doesn't overlap with an existing schedule.
```

This was recorded in the Load table's own `Error` writeback column at the
time but never investigated until this pass.

**Root cause, confirmed live:** querying the target org directly for every
`GiftCommitmentSchedule` tied to this project's 6 real `GiftCommitment`
records (4 Recurring-Donation-derived, 2 multi-Payment-Opportunity-derived)
showed all 6 already have a real, live schedule:

| GiftCommitment ScheduleType | TransactionPeriod on its real schedule | Who created it |
|---|---|---|
| Recurring (Monthly) | Monthly | **Auto-created by the platform** |
| Recurring (Yearly) | Yearly | **Auto-created by the platform** |
| Recurring (Monthly) | Monthly | **Auto-created by the platform** |
| Custom | Custom | This migration's own explicit insert (170) |
| Custom | Custom | This migration's own explicit insert (190) |
| Custom | Custom | This migration's own explicit insert (190) |

6 of 6 real records are consistent with one rule: **when a `GiftCommitment`
is inserted with `ScheduleType = 'Recurring'`, Nonprofit Cloud automatically
creates its own matching `GiftCommitmentSchedule` immediately** -- an
explicit second insert for that same commitment is redundant and is
rejected by the platform's own "doesn't overlap" validation.
`ScheduleType = 'Custom'` does **not** trigger this auto-creation; those
commitments genuinely need an explicit `GiftCommitmentSchedule` insert.

**What to do:**
- A transform building `GiftCommitmentSchedule` rows for a `Recurring`-type
  commitment should **not** attempt to insert one at all -- filter those
  rows out before the insert, the way
  `170_npc_giftcommitmentschedule_from_rd_load.sql` now does (`WHERE`
  clause restricting to non-Recurring periods only).
- To learn the real (auto-created) schedule's Id for a `Recurring`-type
  commitment -- needed anywhere downstream that wants to reference it (e.g.
  `GiftTransaction.GiftCommitmentScheduleId`) -- **replicate
  `GiftCommitmentSchedule` from the target org** after the parent
  `GiftCommitment` insert has actually run, then join by the real
  `GiftCommitmentId` (a Salesforce relationship, reliable regardless of
  which side created the schedule) rather than by any local Load table's
  own `LoadId`/`MigrationID__c` bookkeeping, which only ever reflects what
  *this migration* explicitly tried to insert.
- This is the same "two-pass requery" shape already established for
  `dbo.Account`/`PersonContactId` in
  `sql/transformations/110_npc_accountcontactrelation_load.sql`'s own
  header comment -- a general pattern, not a one-off: some target objects
  get real child records the platform creates on its own, and a migration
  that only ever inserts and never reads back will silently miss them.

**Executable check:** built 2026-07-18, same day this was found —
`child_record_risk.py`'s `detect_auto_generated_children()`, run
automatically by `analyze-org-risk` (`--skip-child-shape-check` to opt
out). Since this behavior genuinely isn't visible via the Tooling API (no
matching Flow/trigger found against `GiftCommitment`, confirmed live —
this is core managed-package platform behavior, not client-configured
automation), the check infers it empirically instead: sample real,
non-migrated `GiftCommitment` records and see what fraction already have a
real `GiftCommitmentSchedule`.
Live dogfooding this against `NPC_TARGET_v2` found a real calibration gap
before it found the right answer: this org's broader real `GiftCommitment`
population mixes `Recurring`/`Custom` types together, so only 6 of 10
sampled real records showed a real schedule (60%) — below the tool's
original 80% default threshold, which missed this exact relationship on
the first live run (it caught a different real one instead,
`GiftCommitmentSchedule -> GiftTransaction`, 100%). Recalibrated the
default to 50% based on this real evidence; re-running the same live
command now correctly flags `GiftCommitment -> GiftCommitmentSchedule` at
60% — confirmed directly, not assumed. See `ROADMAP.md` #79 for the full
account.

**CORRECTION (2026-07-19):** this "always auto-creates" rule does not
hold universally. A later session's NPC fundraising/donor-management
Snowfakery dogfood build inserted 12 fresh Recurring-type
`GiftCommitment` records into the same org and got ZERO auto-created
schedules -- verified from both directions, confirmed stable over an
extended period (not an async delay), and confirmed that updating an
already-inserted commitment's fields afterward does not retroactively
trigger it. The root platform cause remains genuinely unclear (still a
Tooling-API-invisible blind spot) -- a plausible but unconfirmed guess is
a Bulk-API-2.0-vs-UI-single-record-insert context difference. **The safe
pattern going forward is defensive, not predictive:** after inserting a
`GiftCommitment`, replicate `GiftCommitmentSchedule` for its Id and check
what's actually there before deciding whether an explicit insert is
needed -- never assume "always" or "never" from a prior session's
finding, even a well-confirmed one like this one originally was. See
[validators/GiftCommitmentSchedule.md](../../validators/GiftCommitmentSchedule.md)'s
own correction entry and
`sql/transformations/370_giftcommitmentschedule_load.sql` for the
corrected implementation.

**UPDATE (2026-07-19, later same day): real mechanism identified via
official docs + a human SME, resolving most of the correction above.**
Two real, documented mechanisms exist, and the dogfood build's own
inserts went through neither before this project's own workaround
inserted a competing schedule:

1. **[Manage Recurring Gift Commitment Schedule Action](https://developer.salesforce.com/docs/atlas.en-us.nonprofit_cloud.meta/nonprofit_cloud/actions_obj_manage_recurring_gift_cmt_schedule.htm)**
   — an explicit Invocable Action (REST endpoint
   `/services/data/vXX.X/actions/standard/manageRcrGiftCmtSchd`),
   confirmed via the official Nonprofit Cloud Developer Guide to NOT be
   triggered by a plain DML/Bulk API insert of a `GiftCommitment`. This
   is what the real "Schedule a Gift Commitment" UI flow calls.
2. **"The scheduled NextGen commitment processing job"** — that phrase
   is Salesforce's own literal field-help text for
   `GiftCommitment.LastNextGenCmtProcError`. Per Salesforce's Summer '26
   (this org's actual release, API v67.0) release-note coverage, this is
   a real nightly batch: "processes commitments concurrently in
   batches... has them ready by the next business day." Confirmed live:
   `LastNextGenCmtProcError`/`LastNextGenCmtProcDtTm` are both blank on
   all 12 of this build's own Recurring commitments, even hours after
   insert and after this project's own workaround — i.e. the job
   genuinely had not touched them yet, not that it ran and found nothing
   to do.

**Human SME confirmation (2026-07-19, via the user asking a real
Nonprofit Cloud architect, "Ali"):** yes, a schedule does get created —
**for a "regular" type (e.g. Monthly)**. "Irregular" commitments, aka
pledges, either never get one auto-created, or only get the *first*
commitment/installment covered, not an ongoing series. This validates
the original 2026-07-18 finding's core claim (auto-creation is real) and
narrows the 2026-07-19 correction above (it's not "sometimes,
unexplained" — it depends on the commitment being a genuine "regular"
recurring type). Ali herself was not certain of the exact mechanical
trigger (explicit action call vs. the nightly batch vs. some combination),
so **the precise trigger condition remains an open question** — see below.

**What "regular" vs. "irregular" most likely maps to, not yet
confirmed**: `GiftCommitmentSchedule.TransactionPeriod`'s real picklist
values are `Monthly`/`Daily`/`Weekly`/`Yearly`/`Custom` — a "regular"
cadence is plausibly any of the first four, "irregular"/pledge plausibly
`Custom`. This lines up with this project's own existing `ScheduleType`
split (`Recurring`/`Custom` on the parent `GiftCommitment`) and with the
PoC's original 6-of-6 evidence table above (every Recurring-type
commitment's real schedule had `TransactionPeriod` = `Monthly` or
`Yearly`, never `Custom`). Not yet confirmed: whether simply setting
`GiftCommitment.ScheduleType = 'Recurring'` on insert is *sufficient* on
its own (with the nightly NextGen job eventually generating the
schedule, given enough real time), or whether a real `GiftCommitmentSchedule`
with an actual `TransactionPeriod` must be explicitly created first
(via the Action above) before anything else manages it going forward.

**What to do on the next rebuild pass**: don't repeat this build's own
mistake (setting `ScheduleType = 'Recurring'` with no schedule at all,
checking same-day, then explicitly inserting a competing schedule when
none appeared). Instead: (a) try calling the "Manage Recurring Gift
Commitment Schedule" action explicitly for a Recurring-type commitment
with a real `TransactionPeriod` (e.g. `Monthly`) at insert time, OR
(b) insert the commitment, then genuinely wait — check again the next
day, not the same session — before assuming nothing will happen. Never
explicitly `INSERT` a competing `GiftCommitmentSchedule` for a
Recurring-type commitment without first confirming, live, that this
specific org/pass didn't already get one through path (a) or (b).

**UPDATE (2026-07-21, second NPC fundraising dogfood rebuild attempt):
the Action was actually tried live for the first time, not just
researched.** Called `POST
/services/data/v67.0/actions/standard/manageRcrGiftCmtSchd` for all 12
of this build's own Recurring-type `GiftCommitment` records, one real
`giftCommitmentSchedule` payload per call (`GiftCommitmentId`,
`TransactionPeriod='Monthly'`, `TransactionDay='1'`,
`TransactionInterval=1`, `TransactionAmount`, `StartDate`,
`Type='CreateTransactions'`). **Result: 12 of 12 succeeded, zero
collisions, zero `FIELD_INTEGRITY_EXCEPTION`s** -- each call returned a
real `GiftCommitmentSchedule` Id in `giftCommitmentScheduleIdsList`,
confirmed by direct query. This fully resolves the "on the next rebuild,
prefer calling the real Action" guidance from the correction above --
the resulting `GiftCommitmentSchedule_Load` transform's own check-first
`LEFT JOIN` (see `sql/transformations/370_giftcommitmentschedule_load.sql`)
then correctly found only the 3 genuinely `Custom`-type commitments still
needing an explicit insert, exactly matching the real 12-Recurring/
3-Custom split.

**Two new mechanical findings from actually calling it:**
1. **One record per call, strictly.** Batching all 12 payloads into a
   single POST's `inputs` array failed every one of them with
   `MAX_LIMIT_EXCEEDED: "This action can process no more than 1 request
   at a time."` -- unlike a normal Bulk API 2.0 job, this Invocable
   Action has no batch mode; call it once per commitment, in a loop.
2. **The first GiftTransaction and `GiftCommitment.CurrentGiftCmtScheduleId`
   do NOT get created/populated synchronously.** The Action's own
   description promises "creates the first upcoming gift commitment
   transaction record," but a same-session query immediately after a
   successful call showed no matching `GiftTransaction` yet, and
   `CurrentGiftCmtScheduleId` still blank on the parent commitment --
   both likely deferred to the nightly NextGen batch (see this doc's own
   citation 2) rather than happening inline with the Action call. Not
   chased further this pass since it didn't block the schedule itself
   from being usable (this build's own `390_snowfake_gifttransaction_load.sql`
   still builds its GiftTransactions explicitly either way) -- worth
   re-checking a day later on a future pass if the auto-created first
   transaction specifically matters.

**Also learned, unrelated to the Action itself but found the same
session:** `GET`ting the action's own metadata first
(`sf.restful("actions/standard/manageRcrGiftCmtSchd", method="GET")`,
read-only) is the reliable way to learn an Invocable Action's exact
required inputs before ever attempting a live call -- confirms the
required `giftCommitmentSchedule` SObject-shaped input and its real
field names directly from the org, rather than guessing from
documentation prose alone.

# Citations

1. Live-confirmed, 2026-07-18, `NPC_TARGET_v2` -- not documented in the
   migration guide's own Appendix B validation tables (see
   `okf/nonprofit-cloud/gift-commitment-schedule-validations.md`,
   `gift-commitment-validations.md`) as of this writing.
2. Correction live-confirmed, 2026-07-19, same org -- see the correction
   note above.
3. [Manage Recurring Gift Commitment Schedule Action](https://developer.salesforce.com/docs/atlas.en-us.nonprofit_cloud.meta/nonprofit_cloud/actions_obj_manage_recurring_gift_cmt_schedule.htm) —
   Nonprofit Cloud Developer Guide.
4. [GiftCommitment object reference](https://developer.salesforce.com/docs/atlas.en-us.nonprofit_cloud.meta/nonprofit_cloud/npc_fundraising_api_objects_giftcommitment.htm) —
   `LastNextGenCmtProcError`/`LastNextGenCmtProcDtTm` field descriptions.
5. Salesforce Summer '26 (Agentforce Nonprofit) release-note coverage of
   NextGen Commitment Processing, via
   [Galvin Tech's summary](https://galvintech.com/salesforce-summer-26-release/).
6. Human SME confirmation, 2026-07-19 — the user's own real-time
   conversation with a Nonprofit Cloud architect ("Ali"), relayed
   directly, not independently re-verified by this framework.
