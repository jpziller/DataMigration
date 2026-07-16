---
type: MigrationPattern
title: New org, not an in-place upgrade (AFNP)
description: Salesforce strongly recommends migrating into a brand-new
  org rather than upgrading an existing NPSP org in place -- Person
  Accounts are mandatory, Opportunities split across multiple objects,
  and NPSP/AFNP can't safely coexist in one org.
tags: [npsp, npc, afnp, org-strategy, migration-pattern, person-accounts]
timestamp: "2026-07-16"
---
# New org, not an in-place upgrade (AFNP)

The migration guide's §2.3.1 "New Salesforce Orgs vs. In-Place
Migrations" is explicit and unambiguous, not a mild preference: **stand
up a brand-new, clean org for Agentforce Nonprofit; keep the existing
NPSP org as the source, unmodified.** This guide is written with that
premise throughout. The reasoning, verbatim from the source:

- **Person Accounts are mandatory in AFNP.** NPSP represents people as
  plain Contacts; AFNP requires Person Accounts, which combine Account
  and Contact attributes into one record. Migrating every existing
  Contact into a Person Account "is more practical as part of a data
  import into a new org than an in-place transformation."
- **Opportunities split across multiple destination objects** (Gift
  Transaction / Gift Commitment / Opportunity -- see
  [opportunity-routing.md](opportunity-routing.md)). Performing that
  transformation *within* the org that still has to keep running is
  called "complex and error-prone."
- **NPSP and AFNP cannot actively coexist in one org.** Provisioning
  AFNP into an existing NPSP org and leaving it deactivated until
  migration finishes is technically possible but explicitly called "a
  high-risk scenario" -- if AFNP features are accidentally activated
  before migration is complete, **they cannot be reverted.**
- **Uninstalling NPSP afterward is itself error-prone.** Depending on
  how NPSP was originally implemented, certain package elements can
  throw errors on uninstall, leaving UI artifacts and spurious data that
  "can be hidden but not removed."

**Practical implication**: any real NPSP→AFNP project needs (at least)
two orgs from the start -- the existing NPSP org, read-only for the
duration of the migration, and a genuinely new, empty target org. This
also matches this framework's own default operating stance (Hard Rule 1,
Mirror-DB-Only Writes / Hard Rule 2, Live-Org Write Confirmation) of
never writing exploratory or migration-in-progress data into a
still-live production org.

# Citations

1. Migration guide §2.3.1 "New Salesforce Orgs vs. In-Place Migrations"
   (see [migration-guide.md](migration-guide.md))
