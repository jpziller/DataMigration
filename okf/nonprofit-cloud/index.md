# Nonprofit Cloud (AFNP)

Target-platform knowledge for Salesforce Nonprofit Cloud — Salesforce's
own documentation calls it "Agentforce Nonprofit" (AFNP). Deliberately
**source-agnostic**: everything here is true regardless of which system a
client is migrating *from* (NPSP, Raiser's Edge, Bloomerang, a
hand-rolled spreadsheet system, or nothing at all for a greenfield org).
Source-specific migration guidance (routing rules, field mappings FROM a
particular legacy system) belongs in that source's own OKF bundle —
e.g. [okf/npsp-to-npc/](../npsp-to-npc/index.md) for NPSP.

Split out of `okf/npsp-to-npc/` (2026-07-17) once that bundle's own
platform-validation docs turned out to have zero NPSP-specific content —
see that bundle's own history for the full account. First occupants
are the 3 official validation-rule docs plus real findings from this
repo's own NPSP-to-NPC proof-of-concept that turned out to be genuinely
platform-level, not NPSP-source-specific.

# Migration patterns

* [Fundraising/donor-management Snowfakery dogfood — reference implementation](fundraising-dogfood-reference-implementation.md) -
  what's reusable from the full 20-object, source-free Snowfakery build
  (2026-07-19) — transform scripts, the generation sequence, every real
  fix baked in — and what a next rebuild pass needs to redo or
  reconsider.
* [Full org reset between build attempts](full-org-reset-between-build-attempts.md) -
  NEW (2026-07-20) — the real reverse-dependency delete sequence for
  wiping every migrated record (plus auto-created children with no
  migration key of their own) from the NPC fundraising surface, two new
  platform delete-constraint quirks found doing it, and how this differs
  from a targeted corrective reload.

# Platform validations

Official, target-platform-enforced business rules — not migration
gotchas this framework discovered, but Salesforce's own documented
constraints on the fundraising objects (Appendix B of the NPSP-to-AFNP
migration guide, but the rules themselves apply to any data landing in
these objects from any source).

* [Gift Transaction validations](gift-transaction-validations.md) -
  includes a second, independent live confirmation (2026-07-19) of the
  Transaction Due Date / Single-Transaction-for-Custom-Schedule rules,
  plus the real `#N/A` CSV mechanics needed to clear a locked field.
* [Gift Commitment validations](gift-commitment-validations.md)
* [Gift Commitment Schedule validations](gift-commitment-schedule-validations.md)
* [GiftRefund/GiftSoftCredit/GiftTransactionDesignation validations](gift-refund-and-soft-credit-validations.md) -
  NEW (2026-07-19) — three objects not covered by the migration guide's
  own Appendix B tables at all; real constraints found empirically.

# Platform findings

Real, live-confirmed characteristics of the platform itself. Most were
discovered during this repo's own NPSP-to-NPC proof-of-concept
(2026-07-17/18) or the later full-surface Snowfakery dogfood build
(2026-07-19), but none are tied to either pass's own source data —
that's exactly why they live here rather than in a source-specific
bundle.

* [Person Accounts and RecordTypes](person-accounts-and-record-types.md) -
  Person Accounts are a mandatory prerequisite; the real RecordType
  taxonomy a fresh AFNP org ships with (including the
  `Business_Account`/`Org_Business_Account` naming trap).
* [Name field required with no default](name-field-createable-flag-quirk.md) -
  `GiftCommitment`/`GiftTransaction`/`PartyRelationshipGroup` all need a
  real `Name` value on insert, with no natural 1:1 source field —
  confirmed on 3 separate objects.
* [GiftCommitmentSchedule auto-creation](gift-commitment-schedule-auto-creation.md) -
  a Recurring-type GiftCommitment SOMETIMES gets its GiftCommitmentSchedule
  auto-created by the platform (confirmed 6/6 in one session, 0/12 in a
  later one) — check what's actually missing before inserting, never
  assume either way.
* [AccountContactRelation auto-creation](account-contact-relation-auto-creation.md) -
  NEW (2026-07-19) — the same auto-creation family, this time on Contact
  insert; an explicit insert collides silently, with zero error surfaced.
* [Contact Points (Address/Phone/Email)](contact-points.md) - NEW
  (2026-07-19) — new objects vs. NPSP, ParentId polymorphic Account/
  Individual, real field shape much sparser than describe() suggests.
* [Bulk API 2.0 CSV semantics](bulk-api-2-csv-semantics.md) - NEW
  (2026-07-19) — general (not NPC-specific) Bulk API 2.0 behavior: a
  blank CSV cell is a no-op on update, not "clear the field" (needs the
  literal `#N/A`); a sent boolean field can silently break `bulk_op()`'s
  default result-matching fingerprint with zero error surfaced.
