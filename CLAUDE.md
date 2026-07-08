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
  reply — not a summary of what it showed. The user only sees text replies,
  not raw tool call results, so "it worked" or "here's what came back" is
  not a substitute for actually showing it.
- **Tabular results as Markdown tables, not the CLI's ASCII box.** `query`,
  `profile-salesforce`/`profile-sql-table`, and similar commands render to
  the console via `rich` as a plain ASCII box (`+`/`-`/`|` characters) —
  fine on a real terminal, but shows as literal characters if pasted into
  a chat reply's code block instead of rendering as a grid. When relaying
  tabular/query results in a chat reply, reformat them as a Markdown pipe
  table (`| col | col |`) instead of pasting the raw console output —
  logs/errors/non-tabular output still go verbatim in a code block. This
  only changes how results are *presented in chat*; running a command
  directly in a terminal still shows `rich`'s own ASCII-box style.
- **Working past Claude's training cutoff**: this org runs API version 67.0
  (Summer '26), after Claude's training cutoff (January 2026). Don't assume
  training-era knowledge of SOQL functions, API behavior, or Data Cloud/D360
  specifics is current — when something looks new, version-specific, or is
  behaving unexpectedly, check developer.salesforce.com/docs or
  help.salesforce.com (WebFetch/WebSearch) rather than guessing from
  possibly-stale training data.
- **Dogfood built commands.** Once something gets built into a real `cli.py`
  command during a session, use *that* command to verify results and report
  findings going forward — not the ad hoc script that helped research/build
  it, even if that script still works fine. Retire the scratch script once
  the real command exists; don't keep reaching for it out of habit.
- **Every requested review includes a security pass.** When asked to review
  the repo (or any part of it), always check for security issues as part of
  it — never-committed-secrets in git history, credential patterns in code/
  docs, personal/org-identifying content that shouldn't ship, and drift in
  `docs/SECURITY_OVERVIEW.md` — not just correctness and doc consistency.
  This repo is meant to be opened up to others; it stays clean continuously,
  not just before a visibility change.
- **Make sure a run book exists once a real migration project starts.**
  After the first `analyze-load-order` for a new project, check whether a
  run-book workbook exists yet and offer `generate-run-book` if not — this
  is the project's "bigger picture" document (manual steps + scripted
  steps, Pre-Migration through Post-Migration) and shouldn't be an
  afterthought. Before each new environment pass (Dev → UAT → PROD), offer
  `add-run-book-pass` rather than a fresh `generate-run-book`, so the
  recipe (Items/Script names/dependencies/Critical flags) carries forward
  instead of being retyped. See `ROADMAP.md` #16 and `run_book.py`.

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
                (Basic DLO/DMO lookups already work here too, no separate command needed —
                confirmed live, see `ROADMAP.md` #18.)
- Data Cloud (D360): `.venv/Scripts/python.exe cli.py data-cloud-query "SELECT ... FROM SomeDMO"`
                (complex/cross-object Data Cloud SQL — a separate tenant token exchange under
                the hood, `data_cloud.py`; confirmed live against a real Data Cloud org)
                `.venv/Scripts/python.exe cli.py list-calculated-insights`
                `.venv/Scripts/python.exe cli.py query-calculated-insight RateCount__cio`
                `.venv/Scripts/python.exe cli.py data-cloud-status calculated-insight|data-stream|dso|identity-resolution|data-transform|data-graph [Name]`
                (all six via plain core-org SOQL, no Data Cloud tenant token needed — see
                `ROADMAP.md` #18 for the full tested findings and required org/app setup.)
                `.venv/Scripts/python.exe cli.py data-cloud-profile UnifiedssotIndividualIndv__dlm "[ssot__LastName__c=Smith]"`
                (Unified Profile lookup by a required equality filter — the CLI alternative to
                clicking through Data Cloud's own Profile Explorer; `--fields`/`--limit`/`--offset`/
                `--orderby` optional. `filters` really is required by the API itself, not just this
                framework — there's no "browse everyone" mode.)
                `.venv/Scripts/python.exe cli.py list-data-graphs`
                (Data Graph metadata discovery — confirmed live, though this org has none
                configured yet; querying a specific Data Graph's data is written in `data_cloud.py`
                but not yet live-verified, no CLI command wired up for it until it is.)
- Replicate:    `.venv/Scripts/python.exe cli.py replicate Account [--where "..."] [--raw]`
- Import file:  `.venv/Scripts/python.exe cli.py import-parquet path/to/file.parquet SourceAccounts [--append]`
                (Parquet -> typed SQL Server table, column types inferred from the file's own
                schema via `pyarrow` — no coercion step needed since Parquet is already typed,
                unlike Salesforce's Bulk API 2.0 CSV extracts. Drops/recreates the target table
                by default; `--append` adds to an existing compatible table instead. A second
                entry point into the mirror DB alongside `replicate`, for source data that starts
                as a file rather than a live org.)
- Profile:      `.venv/Scripts/python.exe cli.py profile-salesforce Account` (live org, aggregate SOQL)
                `.venv/Scripts/python.exe cli.py profile-sql-table Account` (any SQL Server table)
                `.venv/Scripts/python.exe cli.py export-profile-excel profile.xlsx`
- Load order:   `.venv/Scripts/python.exe cli.py analyze-load-order Account Contact Opportunity ...`
- Mock data:    `.venv/Scripts/python.exe cli.py generate-mock-data Account --count 50`
                (needs `MOCKAROO_API_KEY` in `.env` — free tier, 200 requests/day;
                get a key at mockaroo.com/account. Writes to `<Object>_Mock`, never touches Salesforce.)
- Related mock data (Snowfakery): `.venv/Scripts/python.exe cli.py generate-related-mock-data
                Account Contact --count Account=10 --count Contact=3`
                (relationship-aware alternative to `generate-mock-data` — auto-builds a Snowfakery
                YAML recipe from `describe()` + this framework's own load-order dependency graph
                (`load_order.py`), nesting child objects under their parent so e.g. every mock
                Contact actually references one of the mock Accounts. Recipe is written to
                `_stage/` for review/hand-editing, not hidden. Writes to `<Object>_Mock` tables —
                a child's parent linkage is a synthetic `_ParentMockRef` column, not a real
                Salesforce Id, since none exist yet; building the real `*_Load` transform
                (assigning the actual migration key) is still a manual next step. Never touches
                Salesforce. Same skip policy as `generate-mock-data` — no Data.com fields, no
                Latitude/Longitude subfields.)
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
                `.venv/Scripts/python.exe cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c --email-deliverability system-email-only`
                (insert/upsert require `--email-deliverability` — check Setup > Email Administration
                > Deliverability yourself first and pass what it actually shows; there's no API to
                read it, so `bulk_op()` requires this as an explicit human attestation and raises
                before touching the API if it's missing — rule 9. `all-email` also needs
                `--confirm-external-email-risk`.)
                (every sent column is checked against the target object's live describe() before
                the API is ever called — a typo'd, removed, or non-writable field aborts the whole
                call up front rather than burning a real Bulk API batch to find out the same thing;
                a required-but-unsent field on insert is reported as a warning instead, since
                automation could still default it. See `bulkops.py`'s pre-flight check.)
                `.venv/Scripts/python.exe cli.py bulkops Account delete Account_Purge --external-id Legacy_Id__c`
                (delete by external id — Bulk API 2.0's delete only ever accepts a real Id, so this
                resolves external id values to real Ids via a query first, then deletes the resolved
                rows. A value with no matching org record never reaches the API; it gets a clear
                local "no matching record found" error written back like any other failure.)
                `--batch-size auto|none|<N>` (default `auto` — dynamic recommendation printed as
                rationale before the load runs, layering seed knowledge for OOTB-heavy objects
                (`reference/batch_size_heuristics.json`), this org's own automation (`analyze-org-risk`'s
                `ObjectAutomationRisk` table), and this project's own load history (`BulkOpsLog`'s
                `LockErrorCount`) — see `batch_advisor.py` and `ROADMAP.md` #15. `none` submits one
                unchunked job (Bulk API 2.0's own default without this framework's involvement); any
                integer pins that exact value verbatim and is never second-guessed — a scripted value
                always wins, same as every established migration tool's hardcode-it norm.)
- Retry a failed load:
                `.venv/Scripts/python.exe cli.py bulkops-retry Contact_Load`
                (copies only the failed rows — where `Error` is populated — from a load table or its
                `_Result` table into a fresh `<table>_Retry` table. Does not call Salesforce itself;
                resubmit the new table via a normal, separately-confirmed `bulkops` call once you've
                looked at why those rows failed.)
- Bulk load activity logging (opt-in, per schema — off by default, never
                automatic; the same opt-in-per-database convention established
                commercial migration tools use):
                `.venv/Scripts/python.exe cli.py enable-bulkops-logging --schema dbo`
                (creates `<schema>.BulkOpsLog`. From then on, every `bulkops` call
                against that schema logs itself automatically — action, object,
                source table, record counts, job count, the Email Deliverability
                attestation, start/end/duration, OS user. No per-call flag needed;
                presence of the table is the on/off switch, same pattern as the
                `[Sort]` column and `key_column` writeback. Never logs `query` reads.
                Each schema (source/staging/dbo/etc.) opts in independently.)
                `.venv/Scripts/python.exe cli.py disable-bulkops-logging --schema dbo`
                (drops `<schema>.BulkOpsLog` — permanently discards that schema's
                log history, so confirm before running.)
- Org risk check: `.venv/Scripts/python.exe cli.py analyze-org-risk Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx`
                (object-level automation inventory before a load — active validation rules, Apex
                triggers, record-triggered Flows, legacy workflow rules, approval processes, via
                live Tooling API + standard Query API calls. Not a field-level formula parser; the
                one field-level signal it does give cheaply is cross-referencing an active
                validation rule's `ErrorDisplayField` against the mapping doc's actually-migrated
                target fields (`Migrate Data == Yes`) as a "direct hit." See `risk_analyzer.py`.)
- Batch-size recommendation (read-only, no Salesforce write — same rationale `bulkops` prints
                automatically when `--batch-size` is left at `auto`):
                `.venv/Scripts/python.exe cli.py recommend-batch-size Opportunity`
                `.venv/Scripts/python.exe cli.py suggest-batch-heuristics`
                (the second one reads this project's own converged load history and prints candidate
                `reference/batch_size_heuristics.json` edits — never writes the file itself; a human
                reviews and commits deliberately, same as adding a new alias to the field-synonym
                thesaurus. See `batch_advisor.py` and `ROADMAP.md` #15.)
- Run book:     `.venv/Scripts/python.exe cli.py generate-run-book run_book.xlsx --tab Dev1 --objects Account Contact`
                (first tab for a new project, or any brand-new tab built straight from
                `docs/RUN_BOOK_TEMPLATE.md` rather than copied forward. `--objects` auto-fills the
                Script/Transformation section from `analyze-load-order`'s results — omit it for a
                blank section to fill in by hand. Refuses to overwrite an existing `--tab` name;
                a run-book tab holds live, manually-entered operational history.)
                `.venv/Scripts/python.exe cli.py add-run-book-pass run_book.xlsx --from-tab Dev1 --to-tab UAT`
                (a new pass over the same project — Dev → UAT → PROD — copies the source tab's
                recipe columns forward (Item/Script name/Dependency/Critical flag) and blanks every
                execution-result column for the fresh run. Also refuses to overwrite an existing
                `--to-tab`. See `run_book.py` and `ROADMAP.md` #16 — `dbo.BulkOpsLog` (#14) can
                never see manual steps like disabling CPQ automation, so the run book's Pre-/
                Post-Migration sections always need a human filling Person/Start/End; this is the
                framework's "bigger picture" document spanning both manual and scripted steps.)
- Look at SQL:  `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Account;"`
  `-E` = Windows auth; use `-U`/`-P` for a SQL login. Prefer a read-only login
  for ad-hoc queries.

Matching slash-command skills exist for the read-only ones — `/list-objects`,
`/describe`, `/dump-describe`, `/query`, `/profile`, `/analyze-load-order`,
`/generate-mock-data`, `/generate-related-mock-data`, `/generate-mapping-doc`,
`/check-mapping-balance`, `/auto-map`, `/generate-solution-doc`,
`/bulkops-retry`, `/analyze-org-risk`, `/import-parquet`, `/replicate`,
`/build-load`, `/validate-load`, `/status`, `/data-cloud-query`,
`/data-cloud-status`, `/data-cloud-profile`, `/list-calculated-insights`,
`/query-calculated-insight`, `/list-data-graphs`, `/recommend-batch-size`,
`/suggest-batch-heuristics`, `/generate-run-book`, `/add-run-book-pass`
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
9. Before any `bulkops insert`/`upsert`, check Setup > Email Administration >
   Deliverability yourself and pass `--email-deliverability
   no-access|system-email-only|all-email` — `bulk_op()` requires it and
   raises before touching the API if it's missing. There is no supported
   API to read this setting (verified: retrieved `EmailAdministrationSettings`
   live and cross-checked Salesforce's own field reference — neither has
   any such field), so this is a required human attestation, not something
   Claude Code can check on its own; state what Setup actually shows before
   passing the flag, don't guess or default to a value. `all-email` also
   needs `--confirm-external-email-risk`, since that's the one state that
   can send real mail to real external contacts — don't pass it
   speculatively "to get past the check."

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
7. Only then move to `bulkops`, with explicit org/auth confirmation (rule 2)
   and, for insert/upsert, Email Deliverability checked and passed (rule 9).
   Leave `--batch-size` at its `auto` default unless you already know a
   pinned value from a prior run of this same project — a scripted
   integer always wins over the recommendation and stays exactly as
   written, the same "hardcode it in the load script" norm every
   established migration tool uses, just with a smarter starting point
   (see `ROADMAP.md` #15).

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
- `parquet_import.py` — file → SQL movement (Parquet into a typed mirror-DB
  table), the flat-file counterpart to `replicate.py`'s org-sourced path.
- `load_order.py`, `profiling.py`, `query_tool.py`, `mock_data.py`,
  `snowfakery_data.py`, `mapping_doc.py`, `auto_mapper.py`, `solution_doc.py`,
  `risk_analyzer.py`, `data_cloud.py`, `batch_advisor.py`, `run_book.py`
  — the Data Architect toolbelt (load-order analysis, profiling, ad hoc
  query, single-object and relationship-aware mock data, mapping doc,
  auto-mapping, solution document generation, org automation risk analysis,
  Data Cloud/D360 query and status tooling, dynamic batch-size recommendations,
  the migration run book).
- `reference/field_synonyms.json` — git-tracked field-name synonym
  thesaurus used by `auto_mapper.py` (e.g. `zip`/`postal`/`postcode` all
  resolve to `BillingPostalCode`). This is template content — always
  committed, unlike everything under `mapping/`/`metadata/`. Every human
  correction during a real mapping session is a candidate new alias; add it
  here rather than hardcoding it in Python, so the thesaurus improves
  across migrations instead of staying static.
- `reference/batch_size_heuristics.json` — git-tracked batch-size knowledge
  base used by `batch_advisor.py`: the fixed sizing ladder, per-object and
  managed-package-prefix seeds for OOTB-heavy objects, and the rules for
  adjusting off org automation/load history. Same "git is truth, human
  reviews and commits deliberately" principle as the field synonym
  thesaurus — `suggest-batch-heuristics` only ever prints candidate edits,
  never writes the file itself.
- `docs/RUN_BOOK_TEMPLATE.md` — git-tracked recipe template used by
  `run_book.py`'s `generate_run_book()`: section names, column headers, and
  starter Pre-/Post-Migration items (Email Deliverability, CPQ automation,
  etc.), parsed directly from this file's Markdown tables. Edit this file
  to change what every new project's first run-book tab starts with — same
  "git is truth" principle as the field-synonym thesaurus and batch-size
  heuristics, but Markdown here since the structure itself is meant to be
  read directly, not hidden behind Python constants.
- `sql/transformations/*.sql` — the migration logic (numbered; run in order).
- `sql/functions/` — reusable T-SQL function library (see its own README).
- `force-app/` — Salesforce metadata deployed via `sf project deploy`
  (custom fields, profile FLS grants).
- `mapping/` — generated field-mapping workbooks (`generate-mapping-doc`).
- **SQL Server tables this framework creates** (not files — all deploy
  targets only, safe to drop/regenerate by re-running the command that
  built them, never edited by hand, never the source of truth for anything
  git already tracks):
  - `dbo.FieldProfile`, `dbo.FieldProfileValues` — `profile-salesforce`/
    `profile-sql-table` results.
  - `dbo.ObjectDependency`, `dbo.ObjectLoadOrder` — `analyze-load-order`
    results.
  - `dbo.SourceRegistry`, `dbo.AutoMapSuggestions` — `auto-map` state
    (which source tables have been auto-mapped against which target
    objects, and the suggestions themselves — match method, score, migrate
    recommendation, rationale). Never the source of truth for the
    thesaurus itself (that's always `reference/field_synonyms.json` in git).
  - `dbo.ObjectAutomationRisk` — `analyze-org-risk` results (validation
    rules, Apex triggers, record-triggered Flows, workflow rules, approval
    processes per object).
  - `<Object>_Mock` — `generate-mock-data` output.
  - `<LoadTable>_Result`, `<LoadTable>_Retry` — `bulkops`/`bulkops-retry`
    writeback and retry tables (only when the load table has no
    `key_column` for in-place writeback, or a retry was built).
  - `<schema>.BulkOpsLog` — **opt-in only, never created automatically.**
    `enable-bulkops-logging --schema <schema>` creates it; from then on
    every `bulkops` call against that schema logs itself (action, object,
    source table, record counts, job count, Email Deliverability
    attestation, start/end/duration, OS user, batch size + source +
    row-lock error count for `batch_advisor.py`'s history layer).
    Re-running `enable-bulkops-logging` on an existing table upgrades it
    in place if it predates the batch-size columns — history is
    preserved, not discarded. `disable-bulkops-logging` drops it and its
    history entirely.
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
- A project's run-book workbook (`generate-run-book`/`add-run-book-pass`
  output — path is up to the caller, same as `generate-solution-doc`) is
  likewise project-specific, real operational history — not gitignored by
  a fixed pattern since there's no fixed output folder, but treat it the
  same way: commit deliberately, not by default.
- `.env` — connection config. Never commit, never print.
