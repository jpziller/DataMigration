---
type: ObjectValidator
title: GiftDesignation validator
description: Object-specific findings for GiftDesignation (Nonprofit
  Cloud/AFNP) -- a GiftDesignation must be deactivated (IsActive=false)
  before it can be deleted. IsDefault=true identifies the org-wide
  default designation dynamically -- never hardcode its Id.
tags: [object-validator, gift-designation, nonprofit-cloud, afnp, gift-default-designation]
timestamp: "2026-07-24"
---
# GiftDesignation validator

## IsDefault=true identifies the org-wide default designation -- confirmed live, never hardcode its Id
**Found:** 2026-07-24, building the corrected GiftTransactionDesignation
inheritance logic (see [GiftTransactionDesignation.md](GiftTransactionDesignation.md)).
Every auto-created `GiftDefaultDesignation` in `NPC_TARGET_v2` points at
the same real `GiftDesignation` -- confirmed live it has `IsDefault =
true`, `Name = "General fund"`. Matches Ali's own description of the
fallback: "usually something like General Fund or Unrestricted or Annual
Fund."
**What to do:** look this org's real default up dynamically
(`SELECT Id FROM GiftDesignation WHERE IsDefault = true`) every time it's
needed -- e.g. as the final fallback when a `GiftTransaction` has no
`GiftCommitmentId`/`CampaignId`-linked `GiftDefaultDesignation` to
inherit from. Never hardcode the literal Id, which is org-specific.

## Can't delete an active GiftDesignation
**Found:** 2026-07-20, purging every migrated record from `NPC_TARGET_v2`
to reset the org to a clean slate before a fresh rebuild. Deleting 8
real `GiftDesignation` records failed with `UNKNOWN_EXCEPTION: "You
can't delete an active gift designation."` -- 6 of 8 failed on the
first attempt (2 happened to already have `IsActive = false`, likely
from earlier manual review).
**What to do:** update `IsActive = false` on the target rows first
(a plain `bulkops update`, no other fields needed), then retry the
delete. Confirmed live: all 6 previously-failing rows deleted cleanly
once deactivated first. See
`okf/nonprofit-cloud/full-org-reset-between-build-attempts.md` for the
full reverse-dependency purge sequence this was found while building.
**Executable check:** none yet -- a pre-delete gate that checks
`IsActive` and deactivates automatically (or at least warns) before
attempting the delete would save a retry cycle; not built, since this
project's own `bulkops <Object> delete` doesn't currently have a
per-object pre-delete hook.
