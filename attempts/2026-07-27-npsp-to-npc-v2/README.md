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
| GiftDesignation | (increment 2) | Rework — designation chain feeds GiftDefaultDesignation/GiftTransactionDesignation |
| GiftCommitment (RD + Opportunity branches) | (increment 2) | Rework — schedule/transaction auto-creation; check-first |
| GiftCommitmentSchedule | (increment 2) | Rework — check-first (mirror `370`), forward-window date guard |
| GiftTransaction | (increment 2) | Rework — two-sided due-date clamp; expect keyless auto-generated transactions for recurring commitments |
| GiftDefaultDesignation | (increment 2) | **NEW — doc-only.** Platform auto-creates it; never insert (mirror `420`) |
| GiftTransactionDesignation | (increment 2) | Rework — inherit from GiftDefaultDesignation; respect `CurrentAmount` cap; load before refunds |
| GiftRefund / GiftSoftCredit / ContactContactRelation / ContactPoint* | (increment 2, scope decision) | NEW scope where the NPSP source supports it |

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

- **Increment 1 (this commit):** scaffold + charter + the account/relationship
  foundation (`010-060`), carried forward with v2 headers, plus the ACR
  correction folded back into the rebuild plan.
- **Increment 2 (next):** the gift objects with their corrections, the new
  doc-only GiftDefaultDesignation, scope-expansion objects, the mapping
  workbooks, and a Migration Run Book tab for this attempt.
- **Step 3:** prove on a real/realistic NPSP source, resolve the open
  questions above, then promote (Replace model) to the library.

No live-org writes happen in step 2 — these are SQL transform scripts and
docs. Validation loads belong to step 3, under the Live-Org Write
Confirmation Rule.
