# Post-Mortem: NPSP→NPC v2 — the fresh build run end-to-end on real NPSP data

**Date:** 2026-07-27
**Scope:** Step 3 of the NPSP→NPC "cloneable starter kit" arc — running the
fresh v2 build (`attempts/2026-07-27-npsp-to-npc-v2/`, steps 1–2 in PRs
#39–#41) end-to-end against a **real NPSP org's data**, not synthetic. Source
`NPSP_SOURCE`, target `NPC_TARGET_v2`. The goal was validation-by-real-data:
prove the v2 transforms on data the PoC's hand-seeded set couldn't represent,
and capture everything the run surfaced.

**Outcome:** the migration completed end-to-end. 79 records across 10 objects
(16 accounts, 8 AccountContactRelation, 8 PartyRelationshipGroup, 4 Campaign,
4 CampaignMember, 2 GiftDesignation, 6 GiftCommitment, 3 GiftCommitmentSchedule,
15 GiftTransaction, 8 GiftTransactionDesignation), loaded alongside the target
org's pre-existing data. Four real findings, all banked.

## What went well

- **Real data validated the v2 build — including the reconciliations from
  step 2.** The decimal fix, the ACR household-membership correction (my fix to
  the rebuild plan), the schedule check-first pattern, and the two-sided
  due-date clamp all held on real data. The single genuine gap real data
  exposed (paid/unpaid) was found and fixed in the run, not discovered later.
- **"Fix the class, not the instance" kept working.** The decimal fix was made
  scale-aware for *all* numeric fields, not just the one that failed; the
  paid/unpaid fix landed in both transaction branches (`120`+`130`), and caught
  a *silent* mislabel in `130` that never even errored.
- **Look-before-delete prevented a real disaster.** The target turned out to
  hold ~5,000 accounts / 11,000+ gifts we didn't create — almost certainly the
  architect's own dataset — not the clean sample org everyone assumed. Counting
  first (and noticing 99% carried no `MigrationID__c`) stopped a broad
  reverse-dependency "reset" that had already been authorized on a false
  premise.
- **Every surprise was investigated, not worked around** — the decimal error,
  the account-type mix, the paid/unpaid failure each got a root-cause query
  before any fix, per the standing "don't brute-force" principle.

## What went poorly (and what was fixed)

- **`replicate.py` decimal-precision failure on real currency (PR #42).**
  Replicating a real Account failed with `pyodbc: Converting decimal loses
  precision`. Two facets: Bulk API 2.0 exports large currency in scientific
  notation (`1.39E+8` → positive-exponent Decimal), and values carry a
  different scale than their column (`250.0` into a scale-0 column). Both break
  `fast_executemany`'s DECIMAL binding. Fix: a scale-aware coercer
  (`type_map._decimal_coercer`) quantizing every value to its column's scale.
  Invisible in the PoC only because that pass scoped replicates to hand-picked
  Ids that dodged large/odd-scale values. Would break any real client with
  large gift/revenue amounts. `tests/test_type_map.py`.
- **The target was not the clean org we assumed (org-safety near-miss).** The
  cleanup I'd planned and gotten authorization for rested on "it only holds our
  ~323-record sample data." It actually held ~30,000+ records, ~99% not ours.
  Corrected to: delete **only** records carrying our `MigrationID__c`, load
  **alongside** the rest. New standing rule captured in memory
  (only-delete-migrated-records; anything broader always asks, even on a test
  org; never delete from source). See
  `okf/salesforce-platform/blocked-by-platform-managed-records-or-state.md`'s
  sibling concern — this is the "whose data is this" half.
- **`GiftTransaction.Status` hardcoded `'Paid'` (PR #44).** Real NPSP has
  unpaid/pledged installments (`npe01__Paid__c = false`, no payment date, only
  a scheduled date); AFNP rejects `Paid` without a completion date. 6 of 10
  single-payment-Opp transactions failed. Fix (`120`/`130`): derive Status from
  the real paid flag, set completion dates only when paid,
  `TransactionDueDate = COALESCE(payment date, scheduled date)`. The PoC's
  all-paid seed hid this entirely. `validators/GiftTransaction.md`.
- **A SQL-only command needed the Salesforce alias.**
  `check-load-table-duplicate-keys` connected to Salesforce (empty flat
  `SF_ORG_ALIAS`, since the project uses the two-org SOURCE/TARGET config) and
  errored before doing its SQL-only work. Worked around inline
  (`SF_ORG_ALIAS=NPC_TARGET_v2`); logged as a tooling gap below.

## Reusable artifacts produced

- **The real-data-validated v2 transforms** (`attempts/2026-07-27-npsp-to-npc-v2/`)
  — now proven on a real org, ready to promote to the library as the canonical
  NPSP→NPC starter kit.
- **The decimal fix** (`type_map.py`, PR #42) — benefits every replicate on
  every project, not just this one.
- **The first NPSP source fingerprint** (`okf/npsp-to-npc/source-fingerprint-npsp.json`
  + note) — the first concrete instance of ROADMAP #89, captured from this
  run's real source data.
- **The only-delete-migrated-records rule** (memory) — a durable data-safety
  practice, learned the right way.

## Target-platform-only knowledge extracted

- **`GiftTransaction.Status` requires a completion date for `Paid`; unpaid
  gifts use `Unpaid` + a scheduled due date** — `validators/GiftTransaction.md`.
- **A recurring GiftCommitment's schedule is platform-auto-created (async);
  immediately post-load it may not exist yet**, so a transaction's
  `GiftCommitmentScheduleId` is legitimately NULL at load time (LEFT JOIN, not
  an error). Confirmed again live — matches the check-first pattern in `090`.

## Process and tooling gaps found

- **`check-load-table-duplicate-keys` (and other SQL-only prep commands)
  shouldn't require a Salesforce connection.** They connect via `_ctx()` and
  fail on an empty flat `SF_ORG_ALIAS` even though they never touch the org.
  → ROADMAP candidate: let SQL-only prep verbs run without an org.
- **The NPSP source was a mixed dev org** (nonprofit + standard demo data);
  scoping to the nonprofit subset (`npe01__SYSTEM_AccountType__c = 'Household
  Account'`) was a manual, per-object judgment. The source-fingerprint idea
  (#89) is partly aimed at making "which records are actually in scope"
  recognizable.

## Open questions for next time

- **Open question #1 (ACR multi-member household shape) is STILL unvalidated.**
  The real source households are all single-member, so the `IsDirect=false`
  membership field shape (`IsIncludedInGroup`/`IsPrimaryMember`) still hasn't
  been tested against a genuine multi-member household. Needs Ali or a client
  with real shared households.
- **Open question #2 was observed, not resolved.** 7 of 15 transactions carried
  no explicit Allocation designation and relied on the auto-created default
  (v2 "option (a)" — held without error). Take the live result to Ali to
  confirm that's the intended behavior vs. inheriting an explicit GTD.
- **Scope-expansion objects** (GiftRefund, GiftSoftCredit, ContactPoint*,
  ContactContactRelation) — still need a per-object source-mapping decision
  before building; deferred deliberately, not forgotten.
- **Promotion** of the v2 attempt to the library is the next milestone now that
  the transforms are real-data-validated.
