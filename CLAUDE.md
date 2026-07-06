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
- Auto-map:     `.venv/Scripts/python.exe cli.py auto-map Account mapping/Migration_Mapping.xlsx SourceAccounts`
                (requires the source table to already be profiled — raises a clear error otherwise.
                Suggests a Target field per source field via exact/normalized name match, then a
                git-tracked synonym thesaurus (`reference/field_synonyms.json`), then fuzzy string
                matching as a conservative fallback. Every suggestion is passed through the existing
                profiling data as a data-quality gate — a clean name match still gets downgraded to
                "No"/"Review" if the source field is barely populated or has only one distinct value.
                Writes suggestions into the mapping doc's Target block/Notes/Migrate Data columns,
                but never overwrites a row where a human already filled in the Target field — see
                `auto_mapper.py` for the full design rationale.)
- Solution doc:  `.venv/Scripts/python.exe cli.py generate-solution-doc Solution.docx Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx`
                (auto-drafts a migration solution/design Word document from load-order analysis,
                a mapping doc, and profiling data — no binary template checked into git; the
                default document is built entirely from Python in `solution_doc.py`, fully
                reviewable like everything else this framework generates. `--company`/`--project`/
                `--prepared-by` fill in the cover; `--appendix` adds the full field-by-field
                mapping table; `--template <custom.docx>` lets a data architect swap in their own
                branded Word template with the same context as `docxtpl` Jinja tags, falling back
                to the default when omitted.)
- Load (WRITES TO SALESFORCE — confirm the target org first):
                `.venv/Scripts/python.exe cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c`
                (every sent column is checked against the target object's live describe() before
                the API is ever called — a typo'd, removed, or non-writable field aborts the whole
                call up front rather than burning a real Bulk API batch to find out the same thing;
                a required-but-unsent field on insert is reported as a warning instead, since
                automation could still default it. See `bulkops.py`'s pre-flight check.)
- Retry a failed load:
                `.venv/Scripts/python.exe cli.py bulkops-retry Contact_Load`
                (copies only the failed rows — where `Error` is populated — from a load table or its
                `_Result` table into a fresh `<table>_Retry` table. Does not call Salesforce itself;
                resubmit the new table via a normal, separately-confirmed `bulkops` call once you've
                looked at why those rows failed.)
- Look at SQL:  `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Account;"`
  `-E` = Windows auth; use `-U`/`-P` for a SQL login. Prefer a read-only login
  for ad-hoc queries.

Matching slash-command skills exist for the read-only ones — `/list-objects`,
`/describe`, `/dump-describe`, `/query`, `/profile`, `/analyze-load-order`,
`/generate-mock-data`, `/generate-mapping-doc`, `/check-mapping-balance`,
`/auto-map`, `/generate-solution-doc`, `/bulkops-retry`, `/replicate`,
`/build-load`, `/validate-load`, `/status`
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
1. **Profile the source table first** (`profile-sql-table`) — auto-mapping
   and any real mapping-quality judgment depend on knowing how populated a
   field actually is, not just what it's named. Don't skip to mapping
   before this exists.
2. **Review the mapping** (source field → target field, transformation
   notes) for the object in question — `generate-mapping-doc` to build the
   starting structure, then `auto-map` to suggest a first pass at the
   Target block/Notes from the profiling data plus name/thesaurus/fuzzy
   matching. Both are a starting point for human review, not a finished
   mapping — treat every "Review" recommendation, and any auto-map "No"
   on a field that instinctively looks mappable, as worth a second look.
3. **Confirm target field API names** with `describe`/`dump-describe`
   (rule 5) — never guess a field name from the mapping doc alone.
4. **Build the transform** under `sql/transformations/`, producing the
   `*_Load` table.
5. **Sort it** — `AddBulkLoadSortColumn` against the object's parent key
   (rule 6), if it has one.
6. **Dupe-check it** — `CheckLoadTableDuplicateKeys` against the migration
   key (rule 7). Resolve anything it flags.
7. Only then move to `bulkops`, with explicit org/auth confirmation (rule 2).

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
  `mapping_doc.py`, `auto_mapper.py`, `solution_doc.py` — the Data Architect
  toolbelt (load-order analysis, profiling, ad hoc query, mock data, mapping
  doc, auto-mapping, solution document generation).
- `reference/field_synonyms.json` — git-tracked field-name synonym
  thesaurus used by `auto_mapper.py` (e.g. `zip`/`postal`/`postcode` all
  resolve to `BillingPostalCode`). This is template content — always
  committed, unlike everything under `mapping/`/`metadata/`. Every human
  correction during a real mapping session is a candidate new alias; add it
  here rather than hardcoding it in Python, so the thesaurus improves
  across migrations instead of staying static.
- `sql/transformations/*.sql` — the migration logic (numbered; run in order).
- `sql/functions/` — reusable T-SQL function library (see its own README).
- `force-app/` — Salesforce metadata deployed via `sf project deploy`
  (custom fields, profile FLS grants).
- `mapping/` — generated field-mapping workbooks (`generate-mapping-doc`).
- `dbo.SourceRegistry`, `dbo.AutoMapSuggestions` (SQL Server, not files) —
  per-project auto-mapping state written by `auto-map`: which source
  tables have been auto-mapped against which target objects, and the
  suggestions themselves (match method, score, migrate recommendation,
  rationale). Deploy targets only, like every other table this framework
  creates — never edited by hand, never the source of truth for the
  thesaurus (that's always `reference/field_synonyms.json` in git).
- `docs/` — reference material: `MIGRATION_PLAYBOOK.md` (methodology),
  `SOQL_QUERY_LIBRARY.md` (Tooling API queries), `SECURITY_OVERVIEW.md`
  (credential inventory, trust boundaries, what's code-enforced vs.
  convention-enforced — read this before a security review, and update it
  alongside any change that adds a credential type, network listener, or
  auth boundary).
- `ROADMAP.md` — idea backlog and build status for planned tooling.
- `metadata/*.json`, `mapping/*.xlsx` — generated, org-specific artifacts.
  Gitignored by default (every org's schema/mappings differ, so these
  aren't template content) — commit your own deliberately if a real
  engagement wants a versioned copy.
- `.env` — connection config. Never commit, never print.
