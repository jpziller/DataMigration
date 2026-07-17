---
type: ObjectValidator
title: GiftTransaction validator
description: Object-specific findings for GiftTransaction (Nonprofit
  Cloud/AFNP) -- Name is required on insert despite describe() reporting
  createable=false, same pattern as GiftCommitment/PartyRelationshipGroup.
tags: [object-validator, gift-transaction, nonprofit-cloud, afnp, npsp-to-npc]
timestamp: "2026-07-17"
---
# GiftTransaction validator

## Name is required on insert despite describe() reporting createable=false
**Found:** 2026-07-17, NPSP-to-NPC migration proof-of-concept.
**What happens:** same signature as [GiftCommitment](GiftCommitment.md)'s
own finding -- `describe('GiftTransaction')` reports `Name` as
`createable: False`, the pre-flight check only warns, and the real Bulk
API call fails with `REQUIRED_FIELD_MISSING: Required fields are missing:
[Name]`.
**Why:** see GiftCommitment.md's write-up -- this is the same
describe()/API mismatch, confirmed independently on a third object
([PartyRelationshipGroup](PartyRelationshipGroup.md) also hit it), strong
enough evidence now to treat it as a real characteristic of this whole
AFNP fundraising object family rather than a one-off.
**What to do:** always send a real `Name` value. This migration reused
the source Opportunity's/Payment's own `Name`.
**Executable check:** none yet -- see GiftCommitment.md's own note on a
possible pre-flight enhancement (escalate required=true + createable=false
to a louder warning).

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
