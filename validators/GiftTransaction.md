---
type: ObjectValidator
title: GiftTransaction validator
description: Object-specific findings for GiftTransaction (Nonprofit
  Cloud/AFNP) -- Name is a genuinely required field with no default, same
  pattern as GiftCommitment/PartyRelationshipGroup.
tags: [object-validator, gift-transaction, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-17"
---
# GiftTransaction validator

## Name is a genuinely required field with no default
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept -- omitted
initially, real Bulk API call failed with `REQUIRED_FIELD_MISSING:
Required fields are missing: [Name]`.
**Correction (2026-07-18):** see [GiftCommitment](GiftCommitment.md)'s
own corrected write-up -- this is an ordinary required field
(`createable: True, nillable: False, defaultedOnCreate: False`), not a
`describe()`/API mismatch as originally (incorrectly) claimed here.
`bulk_op()`'s pre-flight check already warned about this correctly
before the failure; the mistake was proceeding past the warning.
**What to do:** always send a real `Name` value. This migration reused
the source Opportunity's/Payment's own `Name`.

## GiftCommitmentId links a Gift Transaction back to its originating Gift Commitment
**Found/confirmed:** 2026-07-17 -- not a gotcha, a design note worth
recording since it's easy to assume a Gift Transaction always stands
alone. Every Gift Transaction created from an installment of a Recurring
Donation or a multi-Payment Opportunity should carry `GiftCommitmentId`
pointing at the Gift Commitment created from that same parent -- verified
live (a Recurring-Donation-linked Opportunity's migrated Gift Transaction
correctly carried the real `GiftCommitmentId` of the Gift Commitment
built from its parent Recurring Donation). See
`okf/npsp-to-npc/opportunity-routing.md` for the full three-way routing
rule this is part of.
