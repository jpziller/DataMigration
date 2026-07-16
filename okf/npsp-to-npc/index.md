# NPSP to Nonprofit Cloud (AFNP)

Reference knowledge for migrating from Salesforce Nonprofit Success Pack
(NPSP) to Nonprofit Cloud — Salesforce's own documentation calls the
target "Agentforce Nonprofit" (AFNP). Sourced from Salesforce's official
migration guide and its companion field-mapping workbook, described and
linked here rather than duplicated. Pass 1: the guide's own map, the
official fundraising validation rules, and two of the most structurally
significant conceptual changes. Deeper content (the full ~35-step
migration sequence, the three sibling workbooks for other legacy managed
packages) is deliberately deferred until a real project needs that
specific piece — see [migration-guide.md](migration-guide.md)'s own
outline for what's already mapped out but not yet written up in full.

# Reference

* [Migration guide](migration-guide.md) - the official guide's own table
  of contents and migration-sequence outline, pointing back to the real
  document for full detail.
* [Mapping spreadsheets](mapping-spreadsheets.md) - index of all 4
  companion field-mapping workbooks; only one reviewed so far.
* [NPSP to AFNP field mapping](npsp-to-afnp-field-mapping.md) - the
  reviewed workbook's real structure, taxonomy, and a worked example.

# Platform validations

Official, target-platform-enforced business rules — not migration
gotchas this framework discovered, but Salesforce's own documented
constraints on the new fundraising objects.

* [Gift Transaction validations](gift-transaction-validations.md)
* [Gift Commitment validations](gift-commitment-validations.md)
* [Gift Commitment Schedule validations](gift-commitment-schedule-validations.md)

# Migration patterns

* [Households to Party Relationship Groups](households-to-party-relationship-groups.md)
* [Opportunity routing](opportunity-routing.md) - the Gift
  Transaction / Gift Commitment / Opportunity three-way split.
