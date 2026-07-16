---
type: MigrationPattern
title: Households become Party Relationship Groups (AFNP)
description: NPSP's Household Account model has no direct object
  equivalent in Agentforce Nonprofit -- a Household becomes an Account
  (Business Account type or similar) plus a separate Party Relationship
  Group record representing the household grouping itself.
tags: [npsp, npc, afnp, household, party-relationship-group, account-model, migration-pattern]
timestamp: "2026-07-16"
---
# Households become Party Relationship Groups (AFNP)

NPSP models a household as an `Account` with a Household record type,
holding the household's Contacts via the standard Account-Contact
relationship. AFNP's account model is different: it separates the
*grouping concept* (a household as a set of related people) from the
*account record* itself. Per the migration guide's §5.4.1.3/§7.2.3/
§7.2.6, migrating a Household means creating **both**:

1. An Account record for the household (guide's own account-record-type
   framing, §7.2.3).
2. A **Party Relationship Group** record with `Type = "Household"`,
   looking up to that same Account's real (already-migrated) Id --
   created as its own distinct step, §7.2.6, *after* the household
   Account exists, never combined into one insert.

This ordering dependency (Account first, Party Relationship Group
second, by real Id) is exactly the kind of two-pass, Id-dependent load
this framework's own Hard Rule 6 (Parent-Batch Sort) and migration-key
conventions are built for -- the household's NPSP-legacy Id becomes the
join key connecting the new Account to its Party Relationship Group.

# Citations

1. Migration guide §5.4.1.3 "Households (Party Relationship Groups)",
   §7.2.3, §7.2.6 (see [migration-guide.md](migration-guide.md))
