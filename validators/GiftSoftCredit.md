---
type: ObjectValidator
title: GiftSoftCredit validator
description: Object-specific findings for GiftSoftCredit (Nonprofit
  Cloud/AFNP) -- RecipientId is a real Account reference (confirmed live,
  matching the Person Account model), and PartialAmount/PartialPercent
  are mutually exclusive.
tags: [object-validator, gift-soft-credit, nonprofit-cloud, afnp, gift-transaction]
timestamp: "2026-07-19"
---
# GiftSoftCredit validator

## RecipientId is an Account, not a Contact
**Found:** 2026-07-19, NPC fundraising/donor-management Snowfakery
dogfood build, confirmed via `sample-reference-records GiftSoftCredit`
against real, non-migrated data in `NPC_TARGET_v2` (Phase 0 recon) --
real `RecipientId` values are `001`-prefixed (Account), not
`003`-prefixed (Contact). Makes sense under the Person Account model: the
"recipient" being soft-credited is always an Account row, whether that's
a Household/Organization Account or a Person Account's own Account
record.
**What to do:** assign `RecipientId` against the Account pool, never
Contact.

## PartialAmount and PartialPercent are mutually exclusive
**Found:** same session -- a real insert of 23 generated rows failed
100% with `FIELD_INTEGRITY_EXCEPTION: "Enter a value only in the Partial
Amount field or the Partial Percent field."`, since Snowfakery generates
both fields independently with no awareness they're a real either/or
pair. The same shape as the already-known Percent+Amount pairing
requirement on `GiftTransactionDesignation` (see
`okf/npsp-to-npc/allocation-to-gift-transaction-designation.md`).
**What to do:** pick exactly one per row (this build alternates
deterministically by row parity) and null the other -- never send both.
`PartyPhilanthropicRsrchPrflId` (an out-of-scope object reference) is
also left unset, confirmed 0% populated in real reference data.
