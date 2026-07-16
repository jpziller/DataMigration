---
type: SystemValidator
title: Parent-Batch Sort Rule (Hard Rule 6)
description: Number Load-table rows by parent key into a [Sort] column so
  same-parent children never split across concurrent Bulk API 2.0 batches
  and lock-contend on the shared parent record.
tags: [system-validator, hard-rule-6, bulk-api, row-locking]
timestamp: "2026-07-11"
---
# Parent-Batch Sort Rule (System Validator)

CLAUDE.md Hard Rule #6.

## What happens if skipped
`bulkops` submits a Load table's rows in whatever order the SQL engine
happens to return them. Bulk API 2.0 splits a job into batches that
process **concurrently**. If several rows sharing the same parent record
end up scattered across different concurrent batches, those batches
lock-contend on that shared parent — real, observed row-lock errors on
objects with heavy child volume per parent, not a theoretical concern.

## Why
Numbering rows by `ROW_NUMBER() OVER (ORDER BY <parent key>)` into a
`[Sort]` column, then submitting in `[Sort]` order, guarantees every
child of the same parent lands in a contiguous range — and therefore the
same batch, or adjacent batches, never split across concurrent ones.

## What to do
Every `*_Load` table for an object with a parent lookup or master-detail
field gets a `[Sort]` column before `bulkops`, regardless of how small the
object "seems." No exceptions for volume — the failure mode is about
*concurrency*, not row count.

## Executable check
```
.venv/Scripts/python.exe cli.py add-bulk-load-sort-column <LoadTable> <ParentKeyColumn>
```
`load_table_prep.py` — plain Python + inline SQL via `sql_dialect.py`
(not a stored procedure), works on either SQL backend (SQL Server or
SQLite). Safe to re-run; refreshes the `[Sort]` column in place and
verifies every parent key's rows landed in a contiguous range.
