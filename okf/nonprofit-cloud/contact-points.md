---
type: PlatformFinding
title: Contact Points (Address/Phone/Email) -- shape and scoping
description: ContactPointAddress/ContactPointPhone/ContactPointEmail are
  new standalone objects in Nonprofit Cloud with no NPSP equivalent
  (compound address fields on Account/Contact instead). ParentId is
  polymorphic Account/Individual; real ContactPointAddress data is
  sparser than describe() suggests.
tags: [npc, afnp, contact-point-address, contact-point-phone, contact-point-email, platform-finding, contact-points]
timestamp: "2026-07-19"
---
# Contact Points (Address/Phone/Email) -- shape and scoping

**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build — the first time this repo's own tooling built real
transforms for these three objects. New in Nonprofit Cloud, with no
NPSP equivalent: NPSP carries mailing/billing address as compound fields
directly on `Account`/`Contact`; NPC models an address, phone, or email
as its own standalone child record, each row independently marked
primary/default/preferred.

## ParentId is polymorphic: Account or Individual
All three objects' `ParentId` references either `Account` or
`Individual` — a distinct standard Salesforce object from `Contact`,
used for privacy/data-protection preferences, often auto-created
alongside a Person Account. Confirmed live via `sample-reference-records`
that this org's real `ParentId` values are Account-shaped
(`001`-prefixed), not Individual-shaped, across the household/
organization/person-account population sampled.

**What to do:** scope `ParentId` to `Account` only unless a specific
project's own scope genuinely needs `Individual` coverage — real usage
in this org doesn't need it, and pulling `Individual` into a Snowfakery
recipe's object list would need its own describe/mapping/RecordType work
for a second, unrelated object family.

## Real ContactPointAddress data is much sparser than describe() suggests
`sample-reference-records` against 3 real, non-migrated
`ContactPointAddress` rows in `NPC_TARGET_v2` showed `City`/`State`/
`Country`/`Name`/`IsDefault`/`IsThirdPartyAddress`/`IsUndeliverable`/
`IsPrimary` populated, but `Street`, `PostalCode`, `AddressType`,
`UsageType`, `PreferenceRank`, `ActiveFromDate`/`ActiveToDate`,
`BestTimeToContact*`, the Seasonal fields, and the
`LastChangeOfAddress`/`LastAddressStd` geocoding fields were NOT — a
thin sample (n=3), but the only real evidence available at the time.

**What to do:** a migration or mock-data build targeting these objects
should match the real, evidenced shape rather than the full
describe()-createable field list — populating every plausible-looking
field produces data that looks *less* human-created than following what
real users actually fill in, even from a small sample. Re-check with a
larger sample once more real usage exists in a given org; this is a
snapshot, not an assumed-permanent rule.

`ContactPointPhone`/`ContactPointEmail` had zero real reference records
in this org at the time of writing (`record-counts` showed 0 for both) —
no real-shape evidence exists yet for either object.

# Citations

1. Live-confirmed, 2026-07-19, `NPC_TARGET_v2`. Not documented in the
   migration guide's own Appendix B validation tables as of this writing
   (Contact Points aren't in the guide's own §7 Data Migration Sequence
   validation appendix at all — the sequence itself does name them,
   §7.3 "Migrate Addresses").
