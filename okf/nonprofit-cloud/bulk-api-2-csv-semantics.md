---
type: PlatformFinding
title: Bulk API 2.0 CSV semantics that broke a real load -- null-clearing and boolean echo
description: >-
  Two real Bulk API 2.0 (not NPC-specific) behaviors that broke a real
  load and cost real debugging time -- a blank CSV cell on update is a
  no-op, not "set to null" (needs the literal N/A sentinel value); and a
  sent boolean field can come back reformatted, silently breaking
  bulk_op()'s default fingerprint-based result matching for the whole
  row with zero error surfaced.
tags: [npc, afnp, bulk-api, salesforce-platform, csv, platform-finding, general]
timestamp: "2026-07-19"
---
# Bulk API 2.0 CSV semantics that broke a real load

**Scope note:** unlike most of this bundle, neither finding here is
NPC/AFNP-specific — both are general Salesforce Bulk API 2.0 behavior,
true for any object on any org. Documented here (rather than a
not-yet-existing general-Salesforce OKF bundle) because both were found
live during the NPC fundraising/donor-management Snowfakery dogfood
build (2026-07-19) and are directly relevant to any future session
loading data into this or another NPC org with this framework's own
`bulkops` tooling.

## A blank CSV cell on update is a no-op, not "clear the field"
**Found:** correcting a wrongly-set `AccountContactRelation.MigrationID__c`
value — sending SQL `NULL` (which pandas/the CSV writer render as an
empty cell) left the real field completely unchanged on the live record,
even though the local Load table and the `bulk_op()` summary both showed
`succeeded`. Confirmed by direct query after the "successful" clear
attempt: the field was still populated.
**What to do:** to genuinely clear a field on an `update`/`upsert`, send
the literal string `#N/A` in that CSV cell, not a blank value. Confirmed
working live (`AccountContactRelation.MigrationID__c`,
`GiftTransaction.GiftCommitmentScheduleId`).

## A sent boolean field can break bulk_op()'s default result-matching fingerprint, with zero error surfaced
**Found:** an `insert`/`update` against several different objects
(`AccountContactRelation`, `ContactPointAddress`) reported
`submitted: N, succeeded: 0, failed: 0` — no error text at all, even
though direct queries confirmed the real DML fully succeeded every time.
**Root cause:** `bulk_op()`'s default fingerprint matches Salesforce's
success/failure CSV results back to local rows by hashing every sent
column's value; Salesforce can echo a sent boolean back in a different
string representation than what pandas' CSV export originally sent
(e.g. `True`/`1` vs. `true`), and a single reformatted column silently
breaks the fingerprint match for the *entire* row, not just that column.
This is the same general class of bug already known for datetime columns
(see `bulkops.py`'s own module docstring) — booleans are a second,
previously-unconfirmed instance of it.
**What to do:** pass `--fingerprint-columns` (a real, already-known `Id`
for an update where one is available, or the migration key otherwise)
proactively for any object whose Load table sends a boolean column —
don't wait for a `succeeded=0/failed=0` surprise to notice. If an
`insert` has already silently succeeded this way, the fix is a follow-up
`upsert` (never another `insert`, which would create duplicates) with
the same `--fingerprint-columns` flag, to get the writeback `Id`
correctly populated without re-creating anything.

**Related, more serious bug this surfaced** (now fixed in `bulkops.py`
itself): a failed fingerprint match's writeback used to unconditionally
overwrite the Load table's `Id` column with `NULL`, destructively
clobbering a real, correct value the caller had already supplied going
in — see `validators/AccountContactRelation.md` for the full account.
Fixed to `COALESCE` instead of overwrite.

# Citations

1. Live-confirmed, 2026-07-19, `NPC_TARGET_v2`. Not Salesforce-documented
   behavior in any Appendix B table — general Bulk API 2.0 platform
   behavior, confirmed empirically.
