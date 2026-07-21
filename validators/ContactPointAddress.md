---
type: ObjectValidator
title: Contact Point (Address/Phone/Email) validator
description: Object-specific findings for ContactPointAddress,
  ContactPointPhone, and ContactPointEmail (Nonprofit Cloud/AFNP) --
  covered together since they share the same real ParentId shape and
  scoping decision. New in NPC vs NPSP, which had no equivalent
  standalone Contact Point objects (compound address fields on
  Account/Contact instead).
tags: [object-validator, contact-point-address, contact-point-phone, contact-point-email, nonprofit-cloud, afnp, contact-points]
timestamp: "2026-07-19"
---
# Contact Point (Address/Phone/Email) validator

## ParentId is polymorphic (Account or Individual) -- scope to Account only
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build. All three Contact Point objects' `ParentId` references
either `Account` or `Individual` (a distinct standard object from
`Contact`, used for privacy/data-protection preferences, often
auto-created alongside a Person Account). Confirmed live via
`sample-reference-records ContactPointAddress` that this org's real
`ParentId` values are Account-shaped (`001`-prefixed), not
Individual-shaped.
**What to do:** scope to `Account` only unless a specific project needs
`Individual` coverage -- it isn't part of this build's object set, has
no `MigrationID__c` plan, and nothing else references it. With
`Individual` excluded from the object list passed to
`generate-related-mock-data`, `ParentId` never even reaches
`build_recipe()`'s polymorphic-cohort machinery (only edges whose target
is in-scope get recorded at all), so this isn't a workaround, just a
correct scoping choice.

## ContactPointAddress: real reference data is much sparser than describe() suggests
**Found:** same session. `sample-reference-records` against 3 real,
non-migrated `ContactPointAddress` rows in `NPC_TARGET_v2` showed
`City`/`State`/`Country`/`Name`/`IsDefault`/`IsThirdPartyAddress`/
`IsUndeliverable`/`IsPrimary` populated, but `Street`, `PostalCode`,
`AddressType`, `UsageType`, `PreferenceRank`,
`ActiveFromDate`/`ActiveToDate`, `BestTimeToContact*`, the Seasonal
fields, and the `LastChangeOfAddress`/`LastAddressStd` geocoding fields
were NOT -- a thin sample (n=3), but the only real evidence available.
**What to do:** match the real shape rather than the full describe()-
createable field list -- a migration that populates every plausible-
looking field ends up looking less human-created than one that follows
what real users actually fill in, even from a small sample. Re-check
this with a larger sample once more real usage exists in this org.

## ContactPointPhone/ContactPointEmail: no real reference data yet
**Found:** same session. `record-counts` showed 0 real rows for either
object at build time, so field selection for these two was a judgment
call (TelephoneNumber/AreaCode/PhoneType/IsSmsCapable/IsPersonalPhone/
IsBusinessPhone/UsageType for Phone; EmailAddress/UsageType for Email),
excluding system-computed/display-only fields
(FormattedInternational/NationalPhoneNumber, EmailMailBox/EmailDomain,
EmailLatestBounce*) rather than real evidence. Revisit with
`sample-reference-records` once real usage exists.

## Boolean fields can silently break bulk_op()'s default result matching
**Found:** same session, same root cause already documented in
[AccountContactRelation.md](AccountContactRelation.md) -- an insert of
`ContactPointAddress` reported succeeded=0/failed=0 despite all 35 rows
being created successfully (confirmed by direct query), because the
default fingerprint (every sent column) included several boolean fields
Salesforce echoes back reformatted. **What to do:** pass
`--fingerprint-columns MigrationID__c` on every bulkops call for an
object whose Load table sends any boolean column, proactively -- don't
wait for a 0/0 surprise. If an insert has already silently succeeded
this way, the fix is a follow-up `upsert` (not another `insert`, which
would create duplicates) with the same `--fingerprint-columns` flag, to
get the writeback Id correctly populated without re-creating anything.
