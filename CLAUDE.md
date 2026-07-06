# CLAUDE.md — SQL-centric Salesforce migration framework

## What this repo is
A Python framework for SQL-centric Salesforce data migration. SQL Server (local, database `SF_Migration`)
is the integration hub. `replicate` pulls org → SQL; `bulkops` pushes SQL → org
and writes the Salesforce `Id` / `Error` back into the load table. All
transformation logic is T-SQL under `sql/transformations/`, versioned in git.
Full design is in `README.md` — read it before making architectural changes.

## Claude Code behavior defaults (edit this section for your own preferences)
These are default interaction behaviors for any Claude Code session working
in this repo — not fixed rules. This file travels with the repo, so anyone
who opens it here gets the same defaults automatically instead of having to
re-establish them; edit this section directly to change how Claude behaves
for you, and it'll stick for future sessions too.

- **Show actual output, don't narrate it.** When asked to run a query, test,
  or command so the user can see the result, paste the real output into the
  reply (a code block for tabular/console output, verbatim for logs/errors)
  — not a summary of what it showed. The user only sees text replies, not
  raw tool call results, so "it worked" or "here's what came back" is not a
  substitute for actually showing it.
- **Working past Claude's training cutoff**: this org runs API version 67.0
  (Summer '26), after Claude's training cutoff (January 2026). Don't assume
  training-era knowledge of SOQL functions, API behavior, or Data Cloud/D360
  specifics is current — when something looks new, version-specific, or is
  behaving unexpectedly, check developer.salesforce.com/docs or
  help.salesforce.com (WebFetch/WebSearch) rather than guessing from
  possibly-stale training data.

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
-               `.venv/Scripts/python.exe cli.py dump-describe Account`
- Query:        `.venv/Scripts/python.exe cli.py query "SELECT Id, Name FROM Account LIMIT 10"`
                `[--all]` to paginate everything, `[--csv path]`/`[--excel path]` to export.
- Replicate:    `.venv/Scripts/python.exe cli.py replicate Account [--where "..."] [--raw]`
- Profile:      `.venv/Scripts/python.exe cli.py profile-salesforce Account` (live org, aggregate SOQL)
                `.venv/Scripts/python.exe cli.py profile-sql-table Account` (any SQL Server table)
                `.venv/Scripts/python.exe cli.py export-profile-excel profile.xlsx`
- Load order:   `.venv/Scripts/python.exe cli.py analyze-load-order Account Contact Opportunity ...`
- Mock data:    `.venv/Scripts/python.exe cli.py generate-mock-data Account --count 50`
                (needs `MOCKAROO_API_KEY` in `.env` — free tier, 200 requests/day;
                get a key at mockaroo.com/account. Writes to `<Object>_Mock`, never touches Salesforce.)
- Mapping doc:  `.venv/Scripts/python.exe cli.py generate-mapping-doc Account mapping/Migration_Mapping.xlsx SourceAccounts`
                `.venv/Scripts/python.exe cli.py generate-mapping-doc Contact mapping/Migration_Mapping.xlsx SourceContacts`
                (one workbook, one tab per object — reuse the SAME output path for every object in
                the project; it appends/replaces that object's sheet, not the whole file. One row per
                SOURCE field from the named SQL table, with a blank Target block for a human to fill
                in once a mapping is decided — doesn't guess the mapping itself. Auto-fills "Data Profile
                Populated On/%" from existing profiling data for that source table, if any.)
                `.venv/Scripts/python.exe cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/010_account_load.sql`
                (diffs a filled-in doc's Target block against the transform's real INSERT INTO list,
                both directions, plus flags any referenced field that doesn't actually exist on the object.)
- Load (WRITES TO SALESFORCE — confirm the target org first):
                `.venv/Scripts/python.exe cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c`
- Look at SQL:  `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Account;"`
  `-E` = Windows auth; use `-U`/`-P` for a SQL login. Prefer a read-only login
  for ad-hoc queries.

Matching slash-command skills exist for the read-only ones — `/list-objects`,
`/describe`, `/dump-describe`, `/query`, `/profile`, `/analyze-load-order`,
`/generate-mock-data`, `/generate-mapping-doc`, `/check-mapping-balance`,
`/replicate`, `/build-load`, `/validate-load`, `/status`
(`.claude/commands/*.md`). These are the project's "skills": pre-scoped,
no-prompt capabilities for anyone who opens this repo in Claude Code, so
asking for one of these doesn't require re-deriving how to do it from
scratch each time. They're an efficiency layer, not a boundary — general
reasoning/coding (Apex, LWC, architecture work, anything else) is still
available even when there's no dedicated skill for it.

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
7. Every `*_Load` table must have its migration-key column checked for
   duplicates/NULLs before `bulkops`, via
   `EXEC dbo.CheckLoadTableDuplicateKeys '<LoadTable>', '<MigrationKeyColumn>'`
   (`sql/functions/utilities/CheckLoadTableDuplicateKeys.sql`). A duplicate or
   NULL migration key breaks the fingerprint-based result mapping in rule 4 —
   resolve every duplicate it reports before loading, don't let it surface
   later as an unexplained `ambiguous` count after a real Salesforce API call.
8. When deploying a new custom field via `sf project deploy start`, bundle a
   `Profile`/`PermissionSet` metadata component granting Read+Edit to System
   Administrator in the **same deploy**. API-deployed fields get zero
   field-level security by default (unlike Setup-UI-created fields, which
   auto-grant the admin profile) — don't wait for a manual Setup fix or a
   failed query to surface the gap. Re-evaluate which profile/permission set
   to grant once a dedicated API-only migration user exists.

## Standard workflow: building a new load-table script
When asked to build a script/transform for a new object, follow this order —
don't jump straight to writing T-SQL:
1. **Review the mapping** (source field → target field, transformation
   notes) for the object in question. Ask for it if it hasn't been provided.
2. **Confirm target field API names** with `describe`/`dump-describe`
   (rule 5) — never guess a field name from the mapping doc alone.
3. **Build the transform** under `sql/transformations/`, producing the
   `*_Load` table.
4. **Sort it** — `AddBulkLoadSortColumn` against the object's parent key
   (rule 6), if it has one.
5. **Dupe-check it** — `CheckLoadTableDuplicateKeys` against the migration
   key (rule 7). Resolve anything it flags.
6. Only then move to `bulkops`, with explicit org/auth confirmation (rule 2).

## Licensing
MIT licensed, Copyright JP Ziller LLC (see `LICENSE`) — free to use, modify,
and redistribute (including commercially), provided the copyright notice is
kept. Don't reference by name any tool this framework builds its own
replacement for (DBAmp, Field Trip, Salesforce Inspector Reloaded, Maven,
Workbench, etc.) in code, comments, docs, or generated file contents
(including spreadsheet column headers) — describe the behavior generically
instead. This does **not** apply to tools this framework actually integrates
with rather than replaces (Mockaroo, Snowfakery) — naming those is fine.

## Where things live
- `cli.py` — CLI entry point wiring every verb together.
- `config.py`, `sf_client.py`, `sql_client.py` — settings/env, Salesforce
  auth, SQL Server connection.
- `replicate.py`, `bulkops.py`, `type_map.py`, `metadata.py` — org ↔ SQL
  movement and SF type mapping.
- `load_order.py`, `profiling.py`, `query_tool.py`, `mock_data.py`,
  `mapping_doc.py` — the Data Architect toolbelt (load-order analysis,
  profiling, ad hoc query, mock data, mapping doc).
- `sql/transformations/*.sql` — the migration logic (numbered; run in order).
- `sql/functions/` — reusable T-SQL function library (see its own README).
- `force-app/` — Salesforce metadata deployed via `sf project deploy`
  (custom fields, profile FLS grants).
- `mapping/` — generated field-mapping workbooks (`generate-mapping-doc`).
- `docs/` — reference material: `MIGRATION_PLAYBOOK.md` (methodology),
  `SOQL_QUERY_LIBRARY.md` (Tooling API queries).
- `ROADMAP.md` — idea backlog and build status for planned tooling.
- `metadata/*.json`, `mapping/*.xlsx` — generated, org-specific artifacts.
  Gitignored by default (every org's schema/mappings differ, so these
  aren't template content) — commit your own deliberately if a real
  engagement wants a versioned copy.
- `.env` — connection config. Never commit, never print.
