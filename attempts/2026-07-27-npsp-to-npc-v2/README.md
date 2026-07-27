# NPSP-to-NPC v2 — fresh build attempt (2026-07-27)

A **fresh NPSP-to-Nonprofit-Cloud build**, built from the library's knowledge
without editing it, per CLAUDE.md's "Library vs. attempts workspace"
(Replace-model) convention. When proven (step 3), this is promoted to become
the canonical, cloneable NPSP-to-NPC starter kit in `sql/transformations/` +
`mapping/`.

## What this applies

This build starts from two proven bodies of work and reconciles them:

1. **The NPSP-to-NPC PoC** — `sql/transformations/090-220`,
   `mapping/npc_*_from_*.xlsx`,
   [okf/npsp-to-npc/reference-implementation.md](../../okf/npsp-to-npc/reference-implementation.md).
   Real NPSP-sourced transforms, live-validated 2026-07-17/18.
2. **The NPC sample-data clone-clean loop** — `sql/transformations/230-430`,
   where the target-platform behavior was actually learned. The rebuild plan
   distilling it:
   [okf/npsp-to-npc/sample-data-learnings-for-migration.md](../../okf/npsp-to-npc/sample-data-learnings-for-migration.md).

## Object inventory — carry-forward vs. rework

Assessed script by script against the rebuild plan. **The learnings concentrate
entirely in the gift objects; the account/relationship layer was already
correct.**

| Object | v2 script | Status vs. PoC |
| --- | --- | --- |
| Household Account | `010` | Carry forward unchanged |
| Person Account | `020` | Carry forward unchanged (Person Account shadow now documented in the cloud data-shape profile) |
| AccountContactRelation | `030` | **Carry forward — and correct the rebuild plan.** The PoC inserts the *household-membership* ACR (`IsDirect=false`, household Account → member's shadow Contact, `IsIncludedInGroup=true`); that is the confirmed household-grouping mechanism (2026-07-18 architect review) and is **not** auto-created. Only the `IsDirect=true` self-ACR is platform-auto-created, and the PoC never touched it. The rebuild plan's "make ACR doc-only" was an over-generalization from the sample data (which had no multi-member households); corrected in that doc. |
| PartyRelationshipGroup | `040` | Carry forward unchanged (Category left unset / address fields already corrected 2026-07-18) |
| Campaign | `050` | Carry forward unchanged |
| CampaignMember | `060` | Carry forward unchanged |
| GiftDesignation | `070` | Carry forward (GAU → GiftDesignation); note the auto-created GiftDefaultDesignation for the downstream consumer |
| GiftCommitment (from RD) | `080` | Carry forward — already had the ScheduleType cross-validation |
| GiftCommitmentSchedule (from RD) | `090` | Carry forward the check-first/Custom-only fix; **v2 add**: defensive forward-window guard on EndDate (finding 4) |
| GiftCommitment (from Opportunity) | `100` | Carry forward |
| GiftCommitmentSchedule (from Opportunity) | `110` | Carry forward |
| GiftTransaction (from Opportunity) | `120` | Carry forward the live-replicate GiftCommitmentScheduleId derivation; **v2 add**: defensive two-sided due-date clamp (finding 4) |
| GiftTransaction (from Payment) | `130` | Carry forward (Single-Transaction-for-Custom-Schedule handling); clamp documented, not baked (no schedule joined) |
| GiftDefaultDesignation | `140` | **NEW — doc-only.** Platform auto-creates it; never insert (mirror `420`) |
| GiftTransactionDesignation (from Allocation) | `150` | Carry forward the proportional split; **v2 add**: load-before-refunds order + `CurrentAmount` note (findings 2/3) + the Allocation-vs-default open question flagged inline |
| GiftRefund / GiftSoftCredit / ContactContactRelation / ContactPoint* | step 3 scope | NEW scope where the NPSP source supports it — deferred; building untested transforms without the real source shape would be speculative (see below) |

## Open reconciliation questions (want architect/live confirmation — step 3)

- **ACR household-membership field shape.** `IsIncludedInGroup=true` +
  one `IsPrimaryMember` per household is carried forward from the PoC (the
  mechanism the architect review validated). The sample-data build found
  real `IsDirect=true` rows are `False/False`, but that is a *different*
  population (auto-created self-links, not household membership). Confirm the
  `IsDirect=false` membership shape against a real org with genuine
  multi-member households before promotion.
- **GiftTransactionDesignation: Allocation fan-out vs. inherited default.**
  The PoC (`220`) maps from the NPSP Allocation; sample-data `430` inherits
  from the platform's `GiftDefaultDesignation`. A real build must honor both —
  the Allocation gives the intended split, the target caps the total at
  `CurrentAmount` and manages a default designation. Reconcile per the
  rebuild plan's finding 2; confirm with the architect.

## Status

- **Increment 1 (done):** scaffold + charter + the account/relationship
  foundation (`010-060`), carried forward with v2 headers, plus the ACR
  correction folded back into the rebuild plan.
- **Increment 2 (done):** the full core gift chain (`070-150`) — carried
  forward from the PoC's live-validated `150-220` (which already held the
  2026-07-18 schedule-auto-creation fixes), plus the genuine v2
  additions: the new doc-only `140` GiftDefaultDesignation, the defensive
  date guards on `090`/`120` (finding 4), and the load-before-refunds order
  + `CurrentAmount` note + the flagged Allocation-vs-default open question on
  `150` (findings 2/3).
- **Deferred to step 3 (needs the real NPSP source):**
  - **Mapping workbooks** — the library's `mapping/npc_*_from_*.xlsx` carry
    forward unchanged (same NPSP→NPC field mappings); regenerating a fresh
    per-object mapping doc needs the source tables profiled, which needs a
    real NPSP source replicated. Not a v2 change.
  - **Migration Run Book tab** — generated for the attempt at load time
    (`generate-migration-run-book --script-dir attempts/2026-07-27-npsp-to-npc-v2/sql`),
    an operational artifact filled during the actual run.
  - **Scope-expansion objects** (GiftRefund, GiftSoftCredit,
    ContactContactRelation, ContactPoint*) — each needs a decision about the
    NPSP source (negative payments? OCR/soft-credit objects? Contact
    address/phone/email fields?) and would be an untested transform without
    the real source in hand. Build them against real client data, not
    speculatively.
- **Step 3:** replicate a real/realistic NPSP source, run each transform,
  resolve the two open questions, load to a target org (under the Live-Org
  Write Confirmation Rule), then promote (Replace model) to the library as
  the canonical NPSP-to-NPC starter kit.

No live-org writes happened in step 2 — these are SQL transform scripts and
docs. Every validation load belongs to step 3.
