# CLAUDE.md — SQL-centric Salesforce migration framework

## What this repo is
A Python framework for SQL-centric Salesforce data migration. SQL Server (local, database `SF_Migration`)
is the integration hub. `replicate` pulls org → SQL; `bulkops` pushes SQL → org
and writes the Salesforce `Id` / `Error` back into the load table. All
transformation logic is T-SQL under `sql/transformations/`, versioned in git.
Full design is in `README.md` — read it before making architectural changes.

## How to operate here: read-only eyes, reviewed hands
- To **look** at SQL Server (schemas, row counts, samples, validating a load),
  use `sqlcmd` (or the read-only DBHub MCP if configured). Read-only.
- To **change** anything, run the Python CLI verbs via bash. Those are the
  auditable operations.
- The migration logic lives in `sql/transformations/*.sql`. Edit those files;
  don't inline large SQL into one-off shell commands.

## Canonical commands (Windows; venv already created at .venv)
Call the venv Python directly — `cd` does not persist between bash calls and the
venv may not be active in a fresh shell:

- Inspect org:  `.venv/Scripts/python.exe cli.py list-objects`
-               `.venv/Scripts/python.exe cli.py describe Account`
- Replicate:    `.venv/Scripts/python.exe cli.py replicate Account [--where "..."] [--raw]`
- Load (WRITES TO SALESFORCE — confirm the target org first):
                `.venv/Scripts/python.exe cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c`
- Look at SQL:  `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Account;"`
  `-E` = Windows auth; use `-U`/`-P` for a SQL login. Prefer a read-only login
  for ad-hoc queries.

## Hard rules
1. `replicate` and any `DROP`/`CREATE` run ONLY against the mirror DB
   `SF_Migration`. Never point the tools at a source or production database.
   Confirm `SQL_DATABASE` in `.env` before any replicate.
2. `bulkops` writes to a live Salesforce org. Before running it, state which org
   (`SF_ORG_ALIAS` and auth mode) and get confirmation. Never run it
   speculatively or to "test."
3. Never read or print `.env`, `server.key`, or any credential. The access token
   comes from `sf org auth show-access-token` (the 2026 CLI update redacts it
   from `sf org display`).
4. Result mapping is fingerprint-based, not row-order (see `bulkops.py`). For
   inserts, the load table must carry a unique key mapped to a real SF field
   (e.g. `Legacy_Id__c`). Do not "simplify" this to positional mapping.
5. Don't invent Salesforce object or field API names — confirm with `describe`
   or `dump-describe` first.
6. Every `*_Load` table for an object with a parent lookup/master-detail field
   must get a `[Sort]` column before `bulkops`, via
   `EXEC dbo.AddBulkLoadSortColumn '<LoadTable>', '<ParentKeyColumn>'`
   (`sql/functions/utilities/AddBulkLoadSortColumn.sql`). This numbers rows by
   `ROW_NUMBER() OVER (ORDER BY <parent key>)` so all children of the same
   parent land in a contiguous range — `bulkops.py` submits in `[Sort]` order
   when the column is present, keeping same-parent rows in the same batch
   instead of scattered across batches that process concurrently and
   lock-contend on the shared parent record. Always include this step; don't
   skip it because an object "seems small enough."

## Where things live
- `cli.py`, `replicate.py`, `bulkops.py`, `type_map.py`, `metadata.py` — framework.
- `sql/transformations/*.sql` — the migration logic (numbered; run in order).
- `metadata/*.json` — committed describe snapshots.
- `.env` — connection config. Never commit, never print.
