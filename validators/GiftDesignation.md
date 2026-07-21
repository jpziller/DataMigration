---
type: ObjectValidator
title: GiftDesignation validator
description: Object-specific findings for GiftDesignation (Nonprofit
  Cloud/AFNP) -- a GiftDesignation must be deactivated (IsActive=false)
  before it can be deleted.
tags: [object-validator, gift-designation, nonprofit-cloud, afnp]
timestamp: "2026-07-20"
---
# GiftDesignation validator

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
