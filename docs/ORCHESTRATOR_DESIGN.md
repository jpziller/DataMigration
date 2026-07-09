# Supervised End-to-End Load Orchestrator — Safety & Trust Design (ROADMAP #53)

**Status:** Design only. No orchestrator code exists yet; this document is the
spec a future Claude Code session builds from. It does not modify `CLAUDE.md`,
`.claude/settings.json`, or any Python module — those changes are called out
below as implementation steps, not made here.

**Post-review update — §8.1 resolved, §3's mechanism corrected.** The original
`--plan-id`-flag-plus-new-`allow`-entry mechanism proposed below **does not
work**, verified directly against Claude Code's own permission-system
documentation (not assumed): permission rules are evaluated **deny → ask →
allow, in that order, with no specificity tie-breaking** — a broad `ask` rule
always wins over a narrower `allow` rule that also matches the same command
line. Adding a narrower `allow` pattern alongside the existing broad `ask`
pattern for `bulkops` would have changed nothing; every plan-scoped call would
still have prompted individually, exactly like today. §3 below has been
corrected to the mechanism that actually works — a genuinely distinct command
name gated by a PreToolUse hook, not a flag variant added to `allow`. The
original (superseded) proposal is kept inline, struck through in spirit but
not deleted, so the reasoning that led to the correction stays visible — the
same "here's what we assumed, here's what we verified, here's the fix"
discipline this project's own `ROADMAP.md` uses throughout its own history.
One piece of good news from the same verification pass: the shell-
metacharacter-smuggling concern raised during review (`bulkops --plan-id X &&
bulkops Account delete ...`) is **not** a real risk — Claude Code parses shell
operators (`&&`/`;`/`|`/etc.) and validates each subcommand independently, so
that part of the original threat model already held.

**Scope, restated because it constrains every decision below:** this is for
**UAT and PROD passes only**. Dev and earlier test iterations are completely
untouched by this design — they stay exactly as manual and per-step-confirmed
as they are today, forever, regardless of how much the orchestrator is
trusted later. Nothing in this document proposes changing Dev behavior.

**The governing principle, stated once so it doesn't need repeating in every
section:** backing data out of a live org is worse than waiting for a human's
approval. Every threshold, every tier boundary, every ambiguous design choice
below is resolved by rounding toward stopping, not toward convenience.

---

## 1. Foundational architecture choice (open question — see §8.1)

Before the tier taxonomy and approval model can be built, one structural
question has to be answered, because it changes what "pause and ask" even
means mechanically. Two candidate shapes:

**Model A — Python-process orchestrator.** A single new CLI command (e.g.
`cli.py orchestrate-run <plan-id>`) loops through the whole plan inside one
Python process, calling `bulk_op()` directly per object. Pausing mid-run
means the process has to stop, persist enough state to resume later, and
somehow get a question in front of a human outside its own process (a file
flag it polls for? an email? — new plumbing, not something this framework
has today).

**Model B — Claude-driven orchestration (recommended).** The plan is
generated and approved once, then Claude Code itself walks the plan
object-by-object across multiple turns, calling a plan-scoped `bulkops`
variant (§3) as a normal tool call per object, reading back a **deterministic
tier verdict** computed by Python (never freehanded from raw numbers by the
model), and either proceeding to the next object or stopping to talk to the
human — which is just Claude Code doing what it already does. No new
pause/resume plumbing is needed: a pause is simply Claude not making the next
tool call and writing a message instead; resuming is the human replying.

Recommendation: **Model B.** It reuses the entire existing toolchain
(`bulk_op()`, the `ask`-gated Bash permission model, the conversational loop)
instead of building a parallel one, and it keeps every individual load as its
own auditable, individually-logged tool call — which matters directly to
"provably trustworthy before it's trusted." The one piece Model B needs that
doesn't exist today is described in §3: a way for **one** approval to cover
**many** subsequent `bulkops`-shaped tool calls without re-prompting per call.
That mechanism, not the orchestration loop itself, is the actual new
capability this design adds.

A hard design rule regardless of which model is built: **tier assessment is
deterministic Python, not model judgment.** Claude's job is to call an
`assess_tier()`-shaped function (via a small new CLI command, e.g.
`cli.py orchestrator-assess <bulkops-summary-json>`), read the tier it
returns, and act on it — never to eyeball a success-rate number itself and
decide "that looks fine." This keeps the actual stop/go logic in a
git-reviewable, testable, tunable place (§2's threshold file), the same
principle `batch_advisor.py` and `auto_mapper.py` already established for
their own recommendations.

---

## 2. Signal tier taxonomy

Four tiers, in increasing severity. Each threshold below is a **proposed
starting default**, not a scientifically derived number — they're grounded in
this project's own documented history where possible, and otherwise chosen by
deliberately rounding conservative per the governing principle. They belong
in a new git-tracked, human-curated config file —
`reference/orchestrator_thresholds.json` — mirroring the existing
`reference/batch_size_heuristics.json` / `reference/field_synonyms.json`
pattern: a machine reads it, a human tunes it, nothing here is hardcoded in
Python. Thresholds should be **environment-sensitive** (a `uat` profile and a
materially tighter `prod` profile in the same file) — a clean UAT pass at a
looser tier doesn't imply the same object should get the loose PROD tier;
PROD access is separately gated by the graduation ladder in §5 anyway.

Every tier's inputs come from data `bulk_op()` and `batch_advisor.py` already
produce — no new Salesforce calls, no new metadata collection:

- `bulk_op()`'s own return dict: `submitted`, `succeeded`, `failed`,
  `ambiguous`, `external_id_not_found`, `lock_errors`, `preflight_warnings`.
- The failed-records dataframe's `sf__Error` text (already read inside
  `bulk_op()`, just not currently surfaced past the summary dict — surfacing
  the **distinct error messages and their counts** is the one small addition
  needed to `bulk_op()`'s return value for tier assessment to work at all).
- `dbo.BulkOpsLog` history for the same object/schema — the same table
  `batch_advisor._history_adjustment()` already queries — used to build a
  **live baseline** (this object's typical success rate and previously-seen
  error signatures) rather than maintaining a separate baseline table. No new
  table needed for this; it's the same "read history fresh each time" pattern
  `batch_advisor.py` already uses.
- `dbo.ObjectAutomationRisk` (from `analyze-org-risk`) — required as a
  plan-generation prerequisite, not a per-run check (see §6).

### Tier 1 — Continue silently
`failed == 0 AND ambiguous == 0 AND external_id_not_found == 0`.

No ambiguity, nothing to review — identical to what a fully clean `bulkops`
call means today. Still gets a Run Book row via the existing
`sync_run_book_from_log()` path; "silently" means no pause, not no record.

### Tier 2 — Continue, but log a warning
`failed / submitted <= 2%` **and** every distinct error message among the
failures already appears in this object's `BulkOpsLog`/Run-Book history for
this project (a "known, previously-accepted" error signature) **and**
`ambiguous == 0`.

The 2% figure isn't arbitrary: it's grounded in this project's own dogfood
run (ROADMAP #14) — 5 of 100 mock `Account` inserts failed on a known,
understood `DUPLICATE_VALUE:...:Jigsaw` cause. That's exactly the shape tier
2 is meant to cover: a low, already-diagnosed failure class that shouldn't
require re-litigating every time it recurs, but should still be visible in
aggregate. A **new** error message at any noticeable rate skips tier 2
entirely, regardless of the 2% number — see tier 3.

Also tier 2: a `lock_errors > 0` result on an object's *first* run at a given
batch size (the ordinary case `batch_advisor.py` already self-corrects for
next time) — this is expected trial-and-error, not a stop condition, unless
it repeats (tier 3, below).

Writes a `Notes` entry in the Run Book row (`Warning: <n> failures, all
matching known signature <error>`) so a creeping pattern is visible on review
even though it never interrupts the run.

### Tier 3 — Pause and ask the human
Any of:
- `2% < failed / submitted <= 10%`.
- **Any** distinct failure error message not previously seen in this
  project's history for this object — the literal "looking off" signal the
  project owner described. Volume doesn't matter here; novelty does.
- `ambiguous > 0`, at any count. This isn't a data-quality signal — Hard Rule
  4's fingerprint-based result mapping has broken down, meaning some of this
  run's *reported successes* might not be trustworthy either. That's an
  integrity question, not a volume one, so it's never silently tolerated.
- `external_id_not_found` exceeds what this object's prior Dev/UAT pass
  already saw, by any amount — an unexpected new miss suggests source data
  or key mapping shifted since the baseline was established.
- `lock_errors > 0` on a **second consecutive** run against the same object,
  even after `batch_advisor.py` already stepped the batch size down once —
  meaning the standard self-correction was already tried and didn't work.
- The object about to run has no `dbo.ObjectAutomationRisk` rows at all.
  (This should already be blocked at plan-generation time, §6 — reaching it
  at run time means the plan/org state drifted since approval, itself worth
  a pause.)

### Tier 4 — Full stop; nothing proceeds without a fresh, explicit confirmation
Any of:
- `failed / submitted > 10%` on any single object. Double-digit failure is
  much more likely systemic (wrong transform, wrong batch content, an org
  automation blocking a whole class of records) than an isolated
  data-quality tail — this is the "round toward stopping" default, not a
  precisely derived number, and should tighten based on real project history
  the same way `batch_size_heuristics.json` does.
- **Any occurrence of a delete or `purge_by_filter` action**, unconditionally
  — see §4. This is not part of the graduation ladder; it never loosens.
- Any `bulk_op()` pre-flight check failure. Already a hard `raise` inside
  `bulk_op()` before the API is ever touched (Hard Rule 2 territory already)
  — the orchestrator just surfaces this as tier 4 rather than letting an
  exception silently abort the run without the human being told why.
- A missing Email Deliverability attestation on insert/upsert. Already a
  hard `raise` in `bulk_op()` — same treatment as above. The orchestrator
  must never supply a cached attestation value across multiple objects on
  the human's behalf; it has to be part of what was explicitly shown and
  agreed to at plan approval (§3), object by object if the operation varies.
- **A repeated identical error affecting ≥5 rows (or ≥1% of the batch,
  whichever is larger)** in a single run, even if the overall failure rate is
  under the 10% hard floor. Mirrors the intuition `batch_advisor.py` already
  encodes for lock errors: one occurrence might be coincidence, a *repeat*
  is a pattern. A validation rule blocking a whole class of records, or a
  picklist mismatch, reads very differently from N unrelated one-off bad
  rows — and a low overall failure rate could otherwise mask exactly this.
- The object about to run doesn't match the plan's declared next-in-sequence
  object — an integrity check that the run hasn't drifted from what was
  approved (a bug, a race, a stale/reused plan).
- Elapsed time for an object's load exceeds **3x** what `BulkOpsLog` history
  predicts for it. Loose enough not to trip on ordinary variance (network,
  org load), tight enough to catch a stuck, rate-limited, or looping job
  instead of letting it run unattended for hours past its own history.

A tier-4 stop halts **the entire remaining plan**, not just the object that
triggered it — resuming requires a fresh, explicit confirmation of what
happened and why it's safe to continue, the same bar as an initial plan
approval, not a lighter "yes, continue" click.

**No timeouts, ever.** A tier-3 pause with no human response is not a
timeout-to-continue condition — it stays paused indefinitely. Any design that
adds an auto-continue-after-N-minutes fallback violates the governing
principle and must not be built, even as a convenience.

---

## 3. What "approve the whole run once" has to capture

The mechanical crux (from §1): **today, `.claude/settings.json` gates
`Bash(.venv/Scripts/python.exe cli.py bulkops *)` in its `ask` list — every
invocation of that exact command prompts.** That's the literal
implementation of Hard Rule 2. The proposal is **not** to loosen that
pattern.

**Corrected mechanism (§8.1, verified against Claude Code's own permission
docs):** Claude Code evaluates permission rules **deny → ask → allow, in that
order, with no specificity tie-breaking** — a broad `ask` rule always wins
over a narrower `allow` rule that also matches. That rules out the original
idea below of adding a narrower `allow` pattern (e.g. `bulkops --plan-id *`)
alongside the existing broad `ask` pattern for `bulkops` — the `ask` rule
would still fire on every call, unchanged. The mechanism that actually works:

1. A **genuinely distinct command name** — `cli.py bulkops-under-plan
   --plan-id <id> <object> <operation> ...` — not a flag variant of `bulkops`.
   Because it's a different command name, it never matches the existing
   `Bash(...cli.py bulkops *)` pattern at all, so ad hoc `bulkops` (below) is
   provably untouched rather than merely "not intended to be touched."
2. `bulkops-under-plan` is gated entirely by a **PreToolUse hook** (a real,
   documented Claude Code mechanism for exactly this "check external state,
   then decide" case), not a static `allow`/`ask` pattern — the hook queries
   `OrchestratorRunPlan` for the referenced `<plan-id>` and returns "proceed"
   only if it's **Approved**, **unexpired**, and its next unresolved object
   matches what's being requested; otherwise it forces a prompt (or denies
   outright if the plan doesn't exist/was never approved). This is where the
   actual safety logic lives — Python-enforced, git-reviewable, testable —
   not "moved to Python" as a hand-wave, but concretely implemented as the
   hook's own decision function.
3. The **one** moment that stays human-gated in the ordinary sense is plan
   approval itself: `cli.py orchestrator-approve <plan-id>` is a distinct
   command kept in the static `ask` list exactly like any other write today.
4. Ad hoc `cli.py bulkops *` (no plan involved) is **completely unaffected**
   — same command name, same existing `ask` pattern, untouched — because the
   new mechanism lives entirely on a different command name and a hook that
   only ever inspects `bulkops-under-plan` invocations. This is the concrete,
   now mechanically-verified sense in which the loosening is narrow and
   specific, not a blanket change to how `bulkops` behaves.

*(Original proposal, superseded — kept for the record: adding
`cli.py bulkops --plan-id <id> ...` as a flag variant of the same `bulkops`
command, added to `allow` alongside the existing broad `ask` pattern. This
does not work, per the finding above — the `ask` rule wins regardless of the
`allow` rule's specificity.)*

For that one approval to be informed rather than a rubber stamp, the plan it
approves must be a concrete, fully-materialized object — not a live
recomputation each time — and the approval prompt must show, in full:

- **Environment** (`uat` or `prod` — never anything else; the plan-generation
  command should hard-refuse any other value) and the confirmed
  `SF_ORG_ALIAS`/auth mode, per Hard Rule 2.
- **Object list and order**, pulled from `dbo.ObjectLoadOrder` — the same
  source `analyze-load-order` already produces — cross-checked against the
  target Migration Run Book tab's own Load-phase rows so a mismatch between
  the plan and the recipe of record is caught before approval, not after.
- **Per-object operation** (insert/update/upsert/delete — though delete
  should never appear in an orchestrated plan at all, see §4) and, for
  insert/upsert, the **Email Deliverability value** the human is attesting
  for that object, exactly as Hard Rule 9 requires today — shown explicitly,
  never silently inherited from a prior project or a prior object.
- **Batch policy per object** — whether it's `auto` (with
  `recommend_batch_size()`'s current recommendation and rationale, computed
  and shown at plan time, not hidden) or a pinned static value.
- **The tier thresholds this run is agreeing to** (§2's numbers, environment
  profile applied) — printed in full, not just referenced by name, so the
  human is approving actual numbers, not a label.
- **Retry policy**: whether a tier-1/2 object with failures gets
  auto-queued into `bulkops-retry` for a second attempt, or whether every
  retry — even of a low-severity failure — requires its own fresh look. Given
  the governing principle, the default should be **no auto-retry inside an
  orchestrated run**; a failed object's retry is itself a new decision point,
  not an automatic continuation. (Flagged as confirmable — see §8.3.)
- **Expiry**: the approval is valid only for some bounded window (e.g. 2
  hours) or until any file under `sql/transformations/`, the mapping doc, or
  the plan's own object list changes — whichever comes first. An approval
  given today must not silently authorize a run started next week against
  code that's since changed.

This is deliberately more than a single confirm/deny click — it's the
"informed" bar the project owner asked for. New state to hold it:
`dbo.OrchestratorRunPlan` (one row per plan: object list JSON, per-object
policy, threshold snapshot, environment, `ApprovedAt`/`ApprovedBy`,
`ExpiresAt`) and `dbo.OrchestratorRunEvent` (one row per object executed
under a plan: which `BulkOpsLog.LogId` it produced, the tier assessed, and —
if paused — how the human responded). Both are new tables this design
introduces; nothing today tracks a *plan* as a first-class object, only
individual `bulkops` calls after the fact.

---

## 4. Deletes: always a fresh confirmation, no exception, argued explicitly

**Deletes and `purge_by_filter` calls never enter the coarse-approval model,
at any graduation stage, forever.** This is a permanent design decision, not
a "not yet graduated" gap to close later. Reasoning:

- **Asymmetric recoverability.** A failed insert/update is self-healing —
  `bulkops-retry` resubmits exactly the rows that need it. A wrong delete
  removes something that then depends on the Recycle Bin's retention window
  and correct reconstruction of any cascade side effects (master-detail
  children, sharing recalculation, downstream systems that already reacted
  to the deletion event) — Recycle Bin recovery is a mitigant, not a
  full undo.
- **Unbounded blast radius at approval time.** An insert/update/upsert
  operates on a load table whose row count is already known and fixed when
  the plan is approved — the human is approving a specific, countable set of
  rows. `purge_by_filter`'s WHERE clause is resolved **at run time**; a typo
  or a stale assumption about the filter can match a very different, larger
  set of records than whoever approved the plan imagined. A plan approval
  literally cannot be "informed" about a filter delete's actual scope the
  way it can about an insert's.
- **It's already the exact shape Hard Rule 2 exists to catch.** `bulkops
  <Object> delete --where` already routes through the same `ask`-gated
  command as everything else, and already has its own `--dry-run` safety
  step (ROADMAP #32). Nothing about orchestration changes the calculus that
  made that a deliberate, per-call human decision in the first place.

Concretely: the plan-generation command should refuse to include a `delete`
operation in an orchestrated plan at all. If a UAT/PROD pass genuinely needs
a delete/purge step, it stays exactly as manual as it is today — a separate,
individually-confirmed `bulkops ... delete` call, dry-run first, outside the
orchestrator's scope, even in the middle of an otherwise fully-approved run.

---

## 5. Graduation / trust-building path

Framed explicitly as a ladder, not a binary — earned per real project, not
switched on. Promotion is always a **human decision recorded in git**, the
same "the tool proposes, a human commits deliberately" principle
`suggest-batch-heuristics` and the auto-map thesaurus already use. Proposed
home: `reference/orchestrator_trust_ladder.json` — current stage, per-object
track record, promotion/demotion history — human-edited, never
self-advanced by the tool.

- **Stage 0 (today, permanent floor for Dev).** No orchestrator involvement
  at all. Unaffected by everything in this document.
- **Stage 1 — Shadow mode.** For a real UAT pass, the orchestrator generates
  a plan and, for each object, computes and prints what tier it *would*
  assess — but every individual `bulkops` call still goes through the
  ordinary `ask`-gated path exactly as today. Nothing about Hard Rule 2 is
  loosened yet. Purpose: validate the tier logic against real outcomes
  (did it agree with what the human independently chose to do?) with zero
  actual change in blast radius.
- **Stage 2 — Single low-risk object, single pass, real coarse approval.**
  Pick one object with a low `analyze-org-risk` footprint, no delete
  involved, modest volume. Approve that one-object "plan" once; the
  orchestrator proceeds through its own batches without re-confirming. Blast
  radius is contained to one object by construction.
- **Stage 3 — Multi-object sequence, UAT only, still no deletes.** A full
  planned load-order sequence gets one approval. PROD stays fully out of
  reach until this stage has produced enough clean passes (see below).
- **Stage 4 — PROD**, but only for the specific objects that graduated
  cleanly through Stage 3 across enough real projects — not a blanket
  unlock the moment Stage 3 looks good once.

**Promotion criteria:** N consecutive clean passes at a stage — a tier-4 stop
for a *legitimate* reason (the system working as designed) doesn't count
against promotion; a problem the human had to catch that the orchestrator
*missed* counts heavily against it and should reset progress at that stage,
not just pause it. A proposed starting default is **N = 3**, but this is
explicitly flagged as something the project owner should sanity-check (see
§8.2) — three consecutive real UAT passes could span a long calendar time
depending on project cadence, and the right number depends on how much
signal one clean pass actually carries.

**Demotion:** any post-hoc-discovered miss (a tier that should have fired and
didn't) drops the affected object/stage back down, recorded in the same file
with the reason — this is meant to be an honest, visible record across
projects, not just a one-way ratchet.

---

## 6. Integration with what already exists

**Reused as-is, no changes needed:**
- `bulk_op()` — the orchestrator is a caller, never a replacement. Every
  batch/retry/pre-flight/Email-Deliverability/logging behavior it already
  has applies identically whether called ad hoc or under a plan.
- `batch_advisor.recommend_batch_size()` — used both at plan-generation time
  (to show the human what `auto` currently resolves to per object) and at
  run time (`bulk_op(batch_size="auto")` still adapts normally unless the
  plan pins a static value).
- `migration_run_book.sync_run_book_from_log()` — already called via
  `bulk_op(run_book_path=..., run_book_tab=...)`; the orchestrator passes
  these through unchanged, so the Run Book already reflects orchestrated
  activity with zero new Run Book code. Plan generation should additionally
  **read** the target tab's existing Load-phase rows to confirm the plan's
  object list matches the recipe of record (§3) before ever offering it for
  approval.
- `dbo.BulkOpsLog` — read directly (same table, same pattern
  `batch_advisor._history_adjustment()` already uses) to build the live
  per-object baseline tier assessment needs (§2) — no separate baseline
  table required.
- `dbo.ObjectAutomationRisk` (`analyze-org-risk`) — **required, not
  optional, as a plan-generation prerequisite.** Today `batch_advisor.py`
  treats "never scanned" as a soft rationale note; for the orchestrator, an
  object with no automation-risk data on file should **block plan
  generation entirely** for that object — the plan can't be informed about a
  risk it never checked. This is a stricter bar than `batch_advisor.py`
  applies today, deliberately, given the higher stakes.
- `dbo.ObjectLoadOrder` / `dbo.ObjectDependency` (`analyze-load-order`) —
  the sequencing input to a plan, unchanged.

**New state this design introduces (nothing today covers these):**
- `dbo.OrchestratorRunPlan` and `dbo.OrchestratorRunEvent` (§3).
- `reference/orchestrator_thresholds.json` — tier-boundary numbers, per
  environment (§2).
- `reference/orchestrator_trust_ladder.json` — graduation state (§5).
- A small addition to `bulk_op()`'s return dict: distinct failure error
  messages and their counts (currently only the writeback table carries
  this; the summary dict doesn't surface it), needed for tier assessment's
  "seen before vs. novel error" check in §2. This is the one existing-module
  change this design calls for — everything else is additive.

**Implementation checklist for whoever builds this** (not done in this
design pass): add `cli.py orchestrator-approve` to `.claude/settings.json`'s
`ask` list; implement the PreToolUse hook that gates `bulkops-under-plan`
against `OrchestratorRunPlan` state (§3 — this hook *is* the safety
mechanism, not a formality, so it needs its own careful review and tests
before anything trusts it); add a new Hard Rule to `CLAUDE.md` documenting
the exact narrow scope of the Hard-Rule-2 exception (UAT/PROD only,
plan-scoped, deletes excluded, no timeouts, enforced by the hook rather than
a static permission pattern); update `docs/SECURITY_OVERVIEW.md` — a
PreToolUse hook making live allow/deny decisions is itself a new kind of
trust boundary worth documenting there explicitly, not just the new database
tables.

---

## 7. Pause/resume UX under Model B

Because each object's load is its own tool call, pausing needs no special
mechanism: the orchestrator (Claude, walking the plan) simply doesn't make
the next call and instead tells the human what tier fired, why, and what
it's asking about — normal conversation, not a special "resume" command.
Resuming a tier-3 pause means the human responds; there is no default,
timeout-driven "assume yes" path (§2). Resuming a tier-4 stop requires a
fresh confirmation with the same weight as the original plan approval, not
a lighter continue click, and it must explicitly re-state what changed
since the stop.

**Known v1 limitation, not solved here:** tier assessment happens at
**object granularity**, after a `bulk_op()` call for that object completes —
not mid-object, across the Bulk API jobs a large single-object load might
split into. A systemic problem inside one very large object's load is only
caught once that whole object's batches have finished, not partway through.
Splitting a large object's load into orchestrator-visible sub-batches (reusing
the existing batch-size ladder) is a plausible future refinement but is out
of scope for this design pass.

---

## 8. Open questions for the project owner

These are the points this document couldn't resolve without more input —
asked directly rather than guessed at, per this repo's own standing
discipline for exactly this situation.

### 8.1 — RESOLVED. Model A vs. Model B, and the settings.json mechanism
Model B (§1) still stands. The originally-proposed mechanism did not —
verified directly against Claude Code's own permission documentation via the
`claude-code-guide` agent, exactly as this section suggested: permission
rules evaluate **deny → ask → allow, in that order, with no specificity
tie-breaking**, so a narrower `allow` pattern added alongside the existing
broad `ask` pattern for `bulkops` would never have taken effect — the `ask`
rule wins regardless. §3 now specifies the corrected mechanism: a genuinely
distinct command name (`bulkops-under-plan`, not a flag on `bulkops`) gated
entirely by a **PreToolUse hook** that checks live `OrchestratorRunPlan`
state, leaving the existing `ask` pattern for ad hoc `bulkops` completely
untouched (different command name, never matches it). Also confirmed in the
same pass: shell-metacharacter smuggling across compound commands is not a
real risk — Claude Code validates each subcommand in a compound shell
statement independently against the rules.

### 8.2 — Graduation numbers
Is **N = 3** consecutive clean passes a reasonable bar for promoting a stage,
given this project's actual cadence of real engagements? Too low and the
"tested over many projects" bar in the original ask isn't really met; too
high and the ladder never moves in practice. This is a judgment call about
risk appetite and project pace that only the project owner can make.

### 8.3 — Retry policy inside an orchestrated run
§3 proposes **no auto-retry** inside a plan — every retry, even of a
tier-1/2 failure, is its own fresh decision. Is that too conservative for
a genuinely low-severity, previously-seen failure class, or is that
exactly the intended posture? Worth confirming explicitly rather than
assuming.

### 8.4 — Who can approve
Is the plan-approval action always the same human, in the same live Claude
Code session, who confirms org/auth per Hard Rule 2 today — or could
approval ever come from someone else, or through a different channel (e.g.
once ROADMAP #54's Slack/Teams integration exists)? This affects whether
`ApprovedBy` needs to capture anything beyond the OS user Claude Code is
running as.

### 8.5 — Baseline cold-start
For an object with no prior Dev/UAT `BulkOpsLog` history at all (a brand-new
object on its first real pass), tier assessment has no baseline to compare
against — should such an object simply be ineligible for anything above
Stage 1 (shadow mode) until it has at least one clean historical run, or is
there a reasonable tier default for a cold-start object? This document
assumes the former (no baseline, no coarse approval) but that assumption
should be confirmed, not just inherited silently.
