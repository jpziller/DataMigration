---
type: MigrationPattern
title: What the NPC sample-data loop changes for an NPSP-to-NPC build
description: The NPC target-platform behavior discovered while building the
  fully-synthetic fundraising sample dataset (2026-07 clone-clean loop),
  mapped onto the NPSP-to-NPC PoC transforms and mappings that predate it --
  the concrete rebuild plan for a fresh, knowledge-informed NPSP-to-NPC build.
tags: [npsp, npc, afnp, migration-pattern, rebuild-plan, auto-created-records, sample-data, data-shape]
timestamp: "2026-07-27"
---
# What the NPC sample-data loop changes for an NPSP-to-NPC build

## Why this doc exists

Two bodies of work in this repo touch the same NPC fundraising objects,
built months apart:

1. **The NPSP-to-NPC PoC** (`sql/transformations/090-220`, `mapping/npc_*_from_*.xlsx`,
   `okf/npsp-to-npc/`) — real NPSP-sourced transforms across 14 object
   families, built 2026-07-17/18. See
   [reference-implementation.md](reference-implementation.md).
2. **The NPC fundraising sample-data loop** (`sql/transformations/230-430`,
   `sample_data/`, the `okf/nonprofit-cloud/` + `okf/salesforce-platform/`
   findings) — a fully-synthetic, source-free dataset iterated to
   **clone-clean** across many reset+reload cycles. See
   [postmortems/2026-07-27-npc-sample-data-clone-clean-loop.md](../../postmortems/2026-07-27-npc-sample-data-clone-clean-loop.md).

The sample-data loop is where this repo actually **learned how the NPC
target behaves** — auto-created records, keyless auto-generated children,
designation inheritance, a refund-order race, date-range ordering. **The
PoC's scripts predate all of it.** When a real NPSP-to-NPC engagement
starts, the fresh build starts from the PoC's knowledge but must fold in
these learnings. This doc is that mapping — target behavior → what the
NPSP-to-NPC transform/mapping must do differently — so it isn't
rediscovered on a live client org.

This is a **plan and a knowledge doc, not a code change**: the PoC scripts
stay as the committed reference (per the Library-vs-attempts model in
CLAUDE.md); a fresh build is a new `attempts/<date>-npsp-to-npc-v2/`
workspace that applies the below and is promoted when proven.

## The machine-readable head start

Before writing any transform, the fresh build can consult the committed
cloud data-shape profiles for the whole surface —
`okf/nonprofit-cloud/data-shapes/*.json`, 18 objects (see that bundle's
[index](../nonprofit-cloud/index.md)). `gather-okf --objects <Object>` and
`show-data-shape <Object> --cloud nonprofit-cloud` surface each object's
standard structure, parent lookups, date-range pairs, and **confirmed**
auto-created-child relationships **before the org is ever profiled**. That
is the target-side knowledge this doc's findings are distilled from, in a
form a tool reads directly.

## Finding → what the NPSP-to-NPC build must do

### 1. Don't insert platform auto-created records
The platform creates several records itself; an explicit insert either
collides or silently duplicates. Confirmed auto-creations (now in the
cloud data-shape profiles and each object's validator):

| Auto-created record | Trigger | PoC script affected | Fresh build |
| --- | --- | --- | --- |
| `AccountContactRelation` (`IsDirect=true`) | Contact insert | `110_npc_accountcontactrelation_load` **inserts it** | Make it **doc-only** (mirror `sql/transformations/250`); only ever *update* the auto-created row's group flags, never insert. See [account-contact-relation-auto-creation](../nonprofit-cloud/account-contact-relation-auto-creation.md), `validators/AccountContactRelation.md`. |
| `GiftDefaultDesignation` | GiftDesignation / GiftCommitment | **not in the PoC at all** | Never insert — doc-only (mirror `420`). See `validators/GiftDefaultDesignation.md`. |
| `GiftCommitmentSchedule` | Recurring `GiftCommitment` (nuanced — regular vs pledge, nightly job) | `170`/`190` **insert it** | **Check-first** (replicate the schedule, `LEFT JOIN`, insert only where genuinely missing) — mirror `370`. See [gift-commitment-schedule-auto-creation](../nonprofit-cloud/gift-commitment-schedule-auto-creation.md). |
| Keyless `GiftTransaction` | Recurring commitment's `CreateTransactions` schedule, over its date range | `200`/`210` insert transactions | Expect platform-generated, **keyless** transactions to already exist for recurring commitments; scope any reset by `GiftCommitmentId`, not the migration key, and prefer the schedule to generate them. See `validators/GiftCommitment.md`, [blocked-by-platform-managed-records-or-state](../salesforce-platform/blocked-by-platform-managed-records-or-state.md). |
| Person Account `Contact`/`Account` shadow | Person Account insert | `100_npc_person_account_load` | Already handled correctly in the PoC; the shadow relationship is now explicit in the `Account`/`Contact` cloud profiles. |

### 2. GiftTransactionDesignation inherits from GiftDefaultDesignation
The sample-data `430` rewrite (confirmed live with a real NPC architect)
inherits a transaction's designation from the parent's real
`GiftDefaultDesignation` chain (GiftCommitment → Campaign → org default via
`GiftDesignation.IsDefault`), not from a naive 1:1 copy. The PoC's
`220_npc_gifttransactiondesignation_from_allocation_load` maps from the
NPSP **Allocation** fan-out instead. A fresh build must reconcile the two:
the NPSP Allocation gives the *intended split*, but the target caps the
total designation Amount at `CurrentAmount` and manages a default
designation — so the Allocation mapping must respect the
`GiftDefaultDesignation` the platform already made. See
`validators/GiftTransactionDesignation.md`,
[allocation-to-gift-transaction-designation](allocation-to-gift-transaction-designation.md).

### 3. Load designations before refunds (CurrentAmount race)
A transaction's total designation Amount is capped at `CurrentAmount`
(`OriginalAmount − RefundedAmount`), and a refund reduces it
**asynchronously**. Loading a `GiftRefund` before the
`GiftTransactionDesignation` can make the designation exceed the
now-reduced `CurrentAmount` and fail. **Order: designations (430) before
refunds (400).** The PoC had no refund objects; a fresh build that migrates
NPSP refunds must place them after designations in the load order. See
`validators/GiftTransactionDesignation.md`, postmortem §"GiftTransactionDesignation".

### 4. Order start/end date pairs; clamp dates into windows
Any object with a start/end date pair needs end ≥ start, and any date that
must fall inside a parent's window (a transaction due date inside its
schedule window) needs a two-sided clamp. Generic date-range ordering is
now built into mock generation (`snowfakery_data.py`), and the
transform-layer clamps live in `370`/`390`. The cloud data-shape profiles
list each object's date-range pairs explicitly (e.g.
`GiftCommitment.EffectiveStartDate→ExpectedEndDate`,
`GiftCommitmentSchedule.StartDate→EndDate`). A fresh build's transforms
should carry the same clamps for real NPSP dates. See
[date-range-fields-must-be-ordered](../salesforce-platform/date-range-fields-must-be-ordered.md).

### 5. Objects the PoC never covered
The sample-data build exercised objects the NPSP-sourced PoC didn't route
through, because NPSP had no clean source for them: `ContactContactRelation`,
`ContactPointAddress`/`Phone`/`Email`, `GiftRefund`, `GiftSoftCredit`,
`GiftDefaultDesignation`. A fresh NPSP-to-NPC build should decide, per
object, whether the NPSP source has data for it (soft credits and refunds
often do; contact points map from NPSP address/phone/email fields) and add
it to scope — the target-side shape and validations are already captured
in `okf/nonprofit-cloud/` and the cloud profiles.

## Suggested sequence for the fresh build

1. Scaffold `attempts/<date>-npsp-to-npc-v2/{sql,mapping}/` (CLAUDE.md's
   Library-vs-attempts model — do **not** edit `090-220` in place).
2. For each object, run `gather-okf --objects <Object>` +
   `show-data-shape <Object> --cloud nonprofit-cloud` +
   `check-validators <Object>` **first** — the target shape and every
   finding above is retrievable, not rediscovered.
3. Rebuild the transforms applying findings 1–4; add finding 5's objects to
   scope where the NPSP source supports them.
4. Reuse the PoC's routing logic (opportunity-routing, household-to-PRG)
   and the `MigrationID__c` convention verbatim — those were correct.
5. Prove it on a real (or realistic) NPSP source, then promote the attempt
   to the library as the new canonical NPSP-to-NPC starter kit.
