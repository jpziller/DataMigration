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

# Platform validations

Official, target-platform-enforced business rules — not migration
gotchas this framework discovered, but Salesforce's own documented
constraints on the fundraising objects (Appendix B of the NPSP-to-AFNP
migration guide, but the rules themselves apply to any data landing in
these objects from any source).

* [Gift Transaction validations](gift-transaction-validations.md)
* [Gift Commitment validations](gift-commitment-validations.md)
* [Gift Commitment Schedule validations](gift-commitment-schedule-validations.md)

# Platform findings

Real, live-confirmed characteristics of the platform itself, discovered
during this repo's own NPSP-to-NPC proof-of-concept but not tied to that
migration's source data in any way.

* [Person Accounts and RecordTypes](person-accounts-and-record-types.md) -
  Person Accounts are a mandatory prerequisite; the real RecordType
  taxonomy a fresh AFNP org ships with.
* [Name field createable-flag quirk](name-field-createable-flag-quirk.md) -
  `describe()`'s `createable` flag can't be trusted at face value for
  `Name` on this object family — confirmed on 3 separate objects.
