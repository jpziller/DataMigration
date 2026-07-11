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
- **Make sure a Migration Run Book exists once a real migration project starts.**
  After the first `analyze-load-order` for a new project, check whether a
  Migration Run Book workbook exists yet and offer `generate-migration-run-book` if not — this
  is the project's "bigger picture" document (manual steps + scripted
  steps, Pre-Migration through Post-Migration) and shouldn't be an
  afterthought. Before each new environment pass (Dev → UAT → PROD), offer
  `add-migration-run-book-pass` rather than a fresh `generate-migration-run-book`, so the
  recipe (Items/Script names/dependencies/Critical flags) carries forward
  instead of being retyped. See `ROADMAP.md` #16 and `migration_run_book.py`.

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
-               `.venv/Scripts/python.exe cli.py record-counts Account Contact [--all-objects]`
                (one HTTP call for many objects' record counts via `/limits/recordCount` —
                much cheaper than a SOQL `COUNT()` per object, but an **approximate, cached**
                snapshot, confirmed live to lag real inserts noticeably and to omit 0-record
                objects entirely rather than showing 0. Fast rough triage across many objects,
                **not** a substitute for `profile-salesforce`'s exact count when validating a
                load actually landed every row. See `ROADMAP.md` #41.)
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
- Import CSV directory (bulk, roadmap #46): `.venv/Scripts/python.exe cli.py import-csv-directory
                path/to/client_files --ticket PROJ-123 [--rebuild TableName ...] [--run-book path.xlsx --run-book-tab Dev1]`
                (generalizes a proven real-world convention: every `*.csv` in the directory gets
                staged as an all-`NVARCHAR(MAX)` table via `BULK INSERT` — no type sniffing, typed
                later via `sql/transformations/*.sql` like every other source, same "stage raw, type
                explicitly" philosophy. Deliberately different from `import-parquet`: generates a
                numbered, git-committed `.sql` script per file under `sql/source_ingestion/`
                (`--ticket` required, the Script Ticket Traceability Rule, #10) rather than loading directly in Python — the
                script is the real artifact of record, reused unchanged on every later pass, never
                silently regenerated. On a later pass, the current CSV's header is checked against
                what the existing script expects — **the full ordered column list, not just set
                membership**, since `BULK INSERT` maps columns positionally and a same-name reorder
                is exactly as dangerous as a rename. Any drift hard-stops that one file (the rest of
                the batch still runs) until `--rebuild <table>` explicitly regenerates the script —
                never automatic. `--run-book`/`--run-book-tab` auto-syncs results into that tab's
                **Pre-Migration** phase, same opt-in shape as `bulkops`' own run-book flags.)
                `.venv/Scripts/python.exe cli.py enable-source-ingestion-logging --schema dbo`
                (creates `<schema>.SourceIngestionLog` — same opt-in, presence-is-the-switch
                convention as `enable-bulkops-logging`. A drift-blocked run is logged too, so it
                shows up in the Migration Run Book as an `Issue` with the exact diff, not just a
                console message.)
                `.venv/Scripts/python.exe cli.py disable-source-ingestion-logging --schema dbo`
- Profile:      `.venv/Scripts/python.exe cli.py profile-salesforce Account` (live org, aggregate SOQL)
                `.venv/Scripts/python.exe cli.py profile-sql-table Account` (any SQL Server table)
                `.venv/Scripts/python.exe cli.py export-profile-excel profile.xlsx`
                (roadmap #47: profiling is a first-pass activity — both commands check
                `dbo.FieldProfile.AnalyzedDate` first and, by default, skip re-profiling an
                object/table already profiled in this schema, printing the existing date and
                still showing the current profile preview. `--reprofile` forces a real refresh
                regardless of prior state.)
- Load order:   `.venv/Scripts/python.exe cli.py analyze-load-order Account Contact Opportunity ...`
- Resolve RecordTypes: `.venv/Scripts/python.exe cli.py resolve-record-types Account`
                (roadmap #36, the RecordType Resolution Rule, #15 — RecordType Ids are org-specific and never portable
                across orgs. Queries the target org's real RecordType rows for the object and
                writes them into `dbo.RecordTypeMap` (shared across every object in the project,
                like `dbo.FieldProfile`) — the transform then `JOIN`s against it by `DeveloperName`
                to populate `RecordTypeId`, instead of ever hand-copying a raw source Id. Read-only
                against Salesforce, writes only to the mirror DB. Deliberately a plain T-SQL
                reference table, not automatic `bulkops` resolution — use a `LEFT JOIN` in the
                transform so an unmatched `DeveloperName` surfaces as a visible `NULL`, since this
                design has no automatic unresolved-value guard.)
- Data model diagrams (roadmap #57): `.venv/Scripts/python.exe cli.py generate-target-data-model
                Account Contact Opportunity --output target_model.md [--mapping-path ...]`
                `.venv/Scripts/python.exe cli.py generate-source-data-model
                --subject-area "Sales:SourceAccounts,SourceOpportunities" --output-dir models/ [--mapping-path ...]`
                (Mermaid `classDiagram` ERDs styled to approximate Salesforce Data Model Notation
                (SDMN) — verified against `developer.salesforce.com`'s actual SDMN guide before
                building this, not guessed. Renders as `classDiagram` rather than `erDiagram`/
                `flowchart` — confirmed against Mermaid's own docs to be the one diagram type that
                gets real UML composition (`*--`, filled diamond) vs aggregation (`o--`, hollow
                diamond) for master-detail vs lookup (a closer match to SDMN's own diamond-on-the-
                parent-side convention), real per-class fill/border color via `classDef`/`:::`
                styling (something `erDiagram` can't do at all — palette reused verbatim from
                `forcedotcom/sf-skills`' `external-diagram-mermaid-generate` skill's own validated
                Standard/Custom/External convention, not invented here), and attribute lists with
                `"1" *-- "1..*"`-style cardinality strings, all at once. **Target model**:
                relationships come straight from live `describe()` via
                `load_order.build_dependency_edges()` — real, never guessed; object-type coloring
                comes from `describe()`'s own `custom` flag and `__x` API-name suffix, also real.
                **Source model(s)**: staging tables carry no foreign keys, so relationships are a
                naming-convention **guess only**, always rendered as the weaker aggregation form and
                labeled `(guessed)`, printed separately for explicit human review, and never
                color-coded (no Standard/Custom/External axis exists for a plain SQL table). Subject
                areas are an explicit, human-chosen grouping (`--subject-area "Name:Table1,Table2"`,
                repeatable) — never auto-clustered. Both write plain `.md` files with a fenced
                ` ```mermaid ` block — GitHub renders it natively, Lucid supports paste-to-import,
                same "just emit plain Mermaid" convention `ROADMAP.md` #52 (not yet built) already
                sketched for Migration Run Book flowcharts. Read-only, safe without confirmation. See
                `ROADMAP.md` #57 for the full `sf-skills` cross-reference.)
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
                Latitude/Longitude subfields. `--count NAME=N-M` (e.g. `Contact=1-2`) randomizes
                the per-parent count via Snowfakery's own `random_number()` instead of a flat N —
                a statistical split, not a guaranteed exact percentage.)
- Mapping doc:  `.venv/Scripts/python.exe cli.py generate-mapping-doc Account mapping/Migration_Mapping.xlsx SourceAccounts`
                `.venv/Scripts/python.exe cli.py generate-mapping-doc Contact mapping/Migration_Mapping.xlsx SourceContacts`
                (one workbook, one tab per object — reuse the SAME output path for every object in
                the project; it appends/replaces that object's sheet, not the whole file. One row per
                SOURCE field from the named SQL table, with a blank Target block for a human to fill
                in once a mapping is decided — doesn't guess the mapping itself. Auto-fills "Data Profile
                Populated On/%" from existing profiling data for that source table, if any.)
                `.venv/Scripts/python.exe cli.py set-mapping-script Account mapping/Migration_Mapping.xlsx`
                (fills in that object's sheet's "Transform Script:" header field — auto-resolved from
                `sql/transformations/` (highest-numbered match, `--dir source_ingestion` for that folder
                instead), with a real GitHub hyperlink when this repo has a remote, same breadcrumb
                convention the Migration Run Book uses. Deliberately its own step, run only *after* the
                real transform is built — `generate-mapping-doc` never guesses this, since the script
                genuinely doesn't exist yet at mapping time in the standard workflow. Raises if no
                matching script is found rather than leaving a guessed filename in place.)
                `.venv/Scripts/python.exe cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/<NNN>_account_load.sql`
                (diffs a filled-in doc's Target block against the transform's real INSERT INTO list,
                both directions, plus flags any referenced field that doesn't actually exist on the object.
                Also flags rule 14 duplicates: the same Target Field chosen by two+ rows in one sheet,
                or the transform's own column list naming the same column twice.)
- Unmapped required fields: `.venv/Scripts/python.exe cli.py check-required-mappings Account mapping/Migration_Mapping.xlsx`
                (roadmap #49: flags every row flagged `Migrate Data = Yes` with no Target Field ever
                chosen, and attempts a `describe()`-driven suggestion for each via the same matching
                `auto-map` uses — read-only, never writes into the doc itself; that's `auto-map`'s job.)
- Auto-map:     `.venv/Scripts/python.exe cli.py auto-map Account mapping/Migration_Mapping.xlsx SourceAccounts`
                (requires the source table to already be profiled — raises a clear error otherwise.
                Suggests a Target field per source field via exact/normalized name match, then a
                git-tracked synonym thesaurus (`reference/field_synonyms.json`), then fuzzy string
                matching as a conservative fallback. Every suggestion is passed through the existing
                profiling data as a data-quality gate — a clean name match still gets downgraded to
                "No"/"Review" if the source field is barely populated or has only one distinct value.
                Writes suggestions into the mapping doc's Target block/Notes/Migrate Data columns,
                but never overwrites a row where a human already filled in the Target field — see
                `auto_mapper.py` for the full design rationale. Roadmap #47: a second run over the
                same source/target pair (`dbo.SourceRegistry.AutoMappedDate` already records this,
                no new state needed) is framed as a review pass — "N field(s) already decided by a
                human, M still blank, freshly suggested" — rather than the first-pass summary, since
                a later pass means reviewing existing work, not redrafting it. The underlying
                behavior doesn't change either way; only the console framing does.)
- Solution doc:  `.venv/Scripts/python.exe cli.py generate-solution-doc Solution.docx Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx`
                (auto-drafts a migration solution/design Word document from load-order analysis,
                a mapping doc, and profiling data — no binary template checked into git; the
                default document is built entirely from Python in `solution_doc.py`, fully
                reviewable like everything else this framework generates. `--company`/`--project`/
                `--prepared-by` fill in the cover; `--appendix` adds the full field-by-field
                mapping table; `--template <custom.docx>` lets a data architect swap in their own
                branded Word template with the same context as `docxtpl` Jinja tags, falling back
                to the default when omitted.)
- Load-table pre-flight checks (hard rules 6/7 — not stored procedures;
                plain Python + inline SQL via `sql_dialect.py`, works on either SQL backend):
                `.venv/Scripts/python.exe cli.py add-bulk-load-sort-column Account_Load AccountId [--schema dbo]`
                `.venv/Scripts/python.exe cli.py check-load-table-duplicate-keys Account_Load Legacy_Id__c [--schema dbo]`
                (`load_table_prep.py` — replaces the old `EXEC dbo.AddBulkLoadSortColumn`/
                `EXEC dbo.CheckLoadTableDuplicateKeys` stored-procedure step. `check-load-table-
                duplicate-keys` exits nonzero if anything is found, so it can gate a script.)
- Load (WRITES TO SALESFORCE — confirm the target org first):
                `.venv/Scripts/python.exe cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c --email-deliverability system-email-only`
                (insert/upsert require `--email-deliverability` — check Setup > Email Administration
                > Deliverability yourself first and pass what it actually shows; there's no API to
                read it, so `bulk_op()` requires this as an explicit human attestation and raises
                before touching the API if it's missing — the Email Deliverability Attestation Rule, #9. `all-email` also needs
                `--confirm-external-email-risk`.)
                (every sent column is checked against the target object's live describe() before
                the API is ever called — a typo'd, removed, or non-writable field aborts the whole
                call up front rather than burning a real Bulk API batch to find out the same thing;
                a required-but-unsent field on insert is reported as a warning instead, since
                automation could still default it. See `bulkops.py`'s pre-flight check. Exception:
                any column prefixed `REF_` — a human-only SQL-side audit field, rule 13 — is
                excluded from this check entirely, never sent, never flagged. `--ref-prefix` overrides
                the default `REF_` if a project uses a different convention.)
                `.venv/Scripts/python.exe cli.py bulkops Account delete Account_Purge --external-id Legacy_Id__c`
                (delete by external id — Bulk API 2.0's delete only ever accepts a real Id, so this
                resolves external id values to real Ids via a query first, then deletes the resolved
                rows. A value with no matching org record never reaches the API; it gets a clear
                local "no matching record found" error written back like any other failure.)
                `.venv/Scripts/python.exe cli.py bulkops Account delete --where "AccountNumber LIKE 'MOCKACCT-%'" [--dry-run]`
                (purge by filter — test-data cleanup without hand-building a delete load table:
                matching Ids are resolved via SOQL into `<Object>_Purge`, then deleted through the
                normal path (batch sizing, logging, run-book sync all apply). Run `--dry-run` first —
                it reports the matched count and sample Ids without touching anything. No
                delete-everything default: purging a whole object means writing `"Id != null"`
                explicitly. Standard delete only (Recycle Bin–recoverable, deliberately no
                hard-delete). See `ROADMAP.md` #32. Rule 2 applies in full — this deletes real
                records from a live org.)
                `--batch-size auto|none|<N>` (default `auto` — dynamic recommendation printed as
                rationale before the load runs, layering seed knowledge for OOTB-heavy objects
                (`reference/batch_size_heuristics.json`), this org's own automation (`analyze-org-risk`'s
                `ObjectAutomationRisk` table), and this project's own load history (`BulkOpsLog`'s
                `LockErrorCount`) — see `batch_advisor.py` and `ROADMAP.md` #15. `none` submits one
                unchunked job (Bulk API 2.0's own default without this framework's involvement); any
                integer pins that exact value verbatim and is never second-guessed — a scripted value
                always wins, same as every established migration tool's hardcode-it norm.)
                `--run-book <path.xlsx> --run-book-tab <name>` (opt-in, both required together —
                right after this load's own `BulkOpsLog` row is written, automatically calls the same
                sync `update-migration-run-book` uses against that tab's Load phase. Not automatic by
                default; `bulkops` shouldn't silently touch a spreadsheet file unless asked to. See
                `ROADMAP.md` #16.)
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
                attestation, start/end/duration, OS user, and (roadmap #53) distinct
                failure error messages and their counts as JSON in `FailureErrorCounts`
                — needed by `orchestrator-assess`'s "seen before vs. novel error" check,
                previously only visible in the writeback table, not the summary dict.
                No per-call flag needed; presence of the table is the on/off switch,
                same pattern as the `[Sort]` column and `key_column` writeback. Never
                logs `query` reads. Each schema (source/staging/dbo/etc.) opts in
                independently.)
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
- Orchestrator tier assessment (roadmap #53, `docs/ORCHESTRATOR_DESIGN.md` — Phase 1 only;
                read-only, never changes how `bulkops` itself is gated):
                `.venv/Scripts/python.exe cli.py orchestrator-assess Account [--log-id N] [--environment uat|prod]`
                (deterministic tier for a completed `bulkops` run, resolved from a real
                `BulkOpsLog` row — the most recent for that object if `--log-id` is omitted —
                plus that object's own history and whether `analyze-org-risk` has been run for
                it. Every tier has a name, printed alongside the number, never shown bare —
                **Tier 1 (Continue Silently)**, **Tier 2 (Continue with Warning)**, **Tier 3
                (Pause and Ask)**, **Tier 4 (Full Stop)** — see `orchestrator.TIER_NAMES`.
                Prints every reason that fired, not just the tier. `assess_tier()` in
                `orchestrator.py` is the actual logic — deliberately deterministic Python,
                never model judgment, per the design doc's own core requirement. Also reports
                `coarse_approval_eligible`: `False` whenever this object has no prior history
                at all, regardless of how clean the current run looks — an object needs at
                least one logged run before it's eligible for anything beyond Stage 1/shadow
                mode. Two things a completed run genuinely can't reveal are deliberately not
                checked here: a `bulk_op()` pre-flight failure and a missing Email
                Deliverability attestation are both hard `raise`s before any summary exists at
                all, so a real orchestrator loop treats that exception as **Tier 4 (Full
                Stop)** directly, never reaching this command.)
                `.venv/Scripts/python.exe cli.py enable-orchestrator-logging --schema dbo`
                (creates `<schema>.OrchestratorRunEvent` — same opt-in, presence-of-table
                convention as `BulkOpsLog`. Every `orchestrator-assess` call against that schema
                then logs itself automatically: LogId, object, tier, reasons, environment,
                timestamp, OS user. Never gates anything — purely the shadow-mode observation
                record Stage 1 needs to eventually confirm the tier logic agreed with what
                actually happened.)
                `.venv/Scripts/python.exe cli.py disable-orchestrator-logging --schema dbo`
                (drops `<schema>.OrchestratorRunEvent` — permanently discards that schema's
                shadow-mode history, so confirm before running.)
                Phase 2 (the actual coarse-approval mechanism — `bulkops-under-plan`, a
                PreToolUse hook, `orchestrator-approve`) is explicitly not built yet — see the
                design doc's own "Implementation status" note for why.
- Batch-size recommendation (read-only, no Salesforce write — same rationale `bulkops` prints
                automatically when `--batch-size` is left at `auto`):
                `.venv/Scripts/python.exe cli.py recommend-batch-size Opportunity`
                `.venv/Scripts/python.exe cli.py suggest-batch-heuristics`
                (the second one reads this project's own converged load history and prints candidate
                `reference/batch_size_heuristics.json` edits — never writes the file itself; a human
                reviews and commits deliberately, same as adding a new alias to the field-synonym
                thesaurus. See `batch_advisor.py` and `ROADMAP.md` #15.)
- Migration Run Book:     `.venv/Scripts/python.exe cli.py generate-migration-run-book migration_run_book.xlsx --tab Dev1 --objects Account Contact`
                (first tab for a new project, or any brand-new tab built straight from
                `docs/MIGRATION_RUN_BOOK_TEMPLATE.md` rather than copied forward. Structure is a
                direct mirror — reviewed for column names/layout only, never content — of a real
                client's in-production migration-status tab: **one unified table** (Stage, Object,
                Dependency, Status, Critical, Person Responsible, Begin Time, End Time, Execution
                Time, JIRA Ticket Link, Notes, Total/Success/Failed Records, Success Percent, Error
                Details) used for every phase, with phases marked by a single dark-navy banner row
                rather than a repeated header. `--objects` auto-fills the Load phase from
                `analyze-load-order`'s results — omit it for a blank Load phase to fill in by hand.
                `Status` is a real dropdown (Not Started/N/A/In Process/Completed/Issue) driven by
                live conditional-formatting colors (yellow/light green/dark green/red) that update
                if a human changes the value later — same mechanism for `Critical = Yes` (a
                different signal: ahead-of-time risk, not "something already went wrong"). Refuses
                to overwrite an existing `--tab` name; a Migration Run Book tab holds live,
                manually-entered operational history. Every tab also gets a fixed header block —
                Project, Source/Target Environment, a Git Repository link, the exact commit/branch
                and a link to the scripts at that commit, and (if configured) a link to the ticket
                system's project — `--project`/`--source-env`/`--target-env`/`--ticket-url`/
                `--ticket-label` override the auto-filled defaults (`SQL_DATABASE`/`SF_ORG_ALIAS`/
                `TICKET_SYSTEM_URL`/`TICKET_SYSTEM_LABEL`). A matched Load-phase `Object` cell gets
                a real hyperlink to that script at the pinned commit, when this repo has a GitHub
                remote.)
                `.venv/Scripts/python.exe cli.py add-migration-run-book-pass migration_run_book.xlsx --from-tab Dev1 --to-tab UAT --target-env UAT_ORG_ALIAS`
                (a new pass over the same project — Dev → UAT → PROD — copies the source tab's
                recipe columns forward (Stage/Object/Dependency/Critical/JIRA Ticket Link) and
                blanks every result column (Status reset to "Not Started", not left empty) for the
                fresh run. Also refuses to overwrite an existing `--to-tab`. Header carry-forward:
                Project/Source Environment/ticket link carry forward from the source tab unless
                overridden; Commit/Branch and the Scripts link always refresh to the *current* Git
                state; Target Environment is never silently carried forward — Dev/UAT/PROD are
                different orgs — pass `--target-env` explicitly. See `migration_run_book.py` and
                `ROADMAP.md` #16 — `dbo.BulkOpsLog` (#14) can never see manual steps like disabling
                CPQ automation, so every phase's result columns always need a human filling Person
                Responsible/Begin-End Time; this is the framework's "bigger picture" document
                spanning both manual and scripted steps.)
                `.venv/Scripts/python.exe cli.py update-migration-run-book migration_run_book.xlsx --tab Dev1`
                (pulls new `dbo.BulkOpsLog` rows into that tab's Load phase since the last sync —
                fills in a still-pending auto-fill placeholder for that object if one exists,
                otherwise inserts a new row (e.g. a retry) — never overwrites an already-resolved
                row or anything a human typed in by hand. Tracks a per-tab "Last Synced Log Id"
                watermark in the header block (never carried forward on a new pass) so re-running
                is idempotent. Only `BulkOpsLog`'s own aggregate columns get pulled in — per-row
                `Error Details` text isn't populated (would need the separate `_Result` writeback
                table too). Also available as an opt-in automatic step on `bulkops` itself via
                `--run-book`/`--run-book-tab` (same underlying sync, called right after that load's
                own `BulkOpsLog` row is written) instead of running this separately. Since roadmap
                #46, this same command **also** pulls new `dbo.SourceIngestionLog` rows into that
                tab's **Pre-Migration** phase in the same call, via its own independent "Last Synced
                Source Ingestion Log Id" watermark — the two syncs never interfere with each other.
                Also available as an opt-in automatic step on `import-csv-directory` itself via its
                own `--run-book`/`--run-book-tab`.)
- Validate migration key: `.venv/Scripts/python.exe cli.py validate-external-id Account Legacy_Id__c`
                (confirms the named field is genuinely externalId+unique in the live org's
                describe() before it's trusted as a migration key — rule 12. Read-only, no
                confirmation needed, exits nonzero on failure. Not this framework's job to
                create/fix the field; only to gate on it being correctly in place.)
- Reference-record diff: `.venv/Scripts/python.exe cli.py compare-reference-record Account Account_Load
                <RecordId> --migration-key Legacy_Id__c`
                (roadmap #51: diffs a live, hand-created reference record — e.g. one an architect made
                through the Salesforce UI to see how the org's real automation shapes it — against the
                Load table row its migration key corresponds to, field by field. Matches by migration
                key, not `Id`, since a hand-created record was never loaded through `bulkops` and so has
                no `Id` in the Load table to match against — the key's value is read directly off the
                live record. Read-only, a review/debugging aid only; never writes anything back.
                `--key-column`/`--id-column`/`--error-column` override the Load table's writeback column
                names if not the defaults.)
- Look at SQL:  `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.Account;"`
  `-E` = Windows auth; use `-U`/`-P` for a SQL login. Prefer a read-only login
  for ad-hoc queries. On a SQLite-backed project, use the `sqlite3` CLI (or
  any SQLite browser) against the relevant `<schema>.db` file under
  `SQL_SQLITE_DIR` instead — there's no `sqlcmd` equivalent needed.

**SQL backend**: `SQL_BACKEND` in `.env` is `mssql` (default) or `sqlite`,
per project — see `sql_client.py`/`sql_dialect.py`. SQLite mode uses
`SQL_SQLITE_DIR` (a directory, one `<schema>.db` file per schema) and
`SQL_SQLITE_SCHEMAS` (comma-separated, e.g. `dbo,source,staging`) instead
of `SQL_SERVER`/`SQL_DATABASE`/the ODBC settings — every declared schema
is `ATTACH DATABASE`'d under its own name on each connection, so an
existing `schema=` argument anywhere in this codebase already means the
right thing on either backend, no per-call-site changes needed. The
actual load engine — `replicate`, `bulkops` (writeback, activity logging,
retry), hard rules 6/7's tooling, and `import-csv-directory`'s CSV
staging — works on both backends. The SQL-Server-only cleansing/matching
function library (`sql/functions/cleansing|matching|lookups`) and several
data-architect tools (`profiling.py`, `risk_analyzer.py`, `auto_mapper.py`,
`migration_run_book.py`, `mock_data.py`/`snowfakery_data.py`,
`solution_doc.py`, `load_order.py`, `mapping_doc.py`, `parquet_import.py`,
`record_types.py`, `reference_record.py`) are **SQL-Server-only for now**
— a deliberate scope boundary, not an oversight; port one incrementally
via the same `sql_dialect.py` helpers whenever a real SQLite project
actually needs it.

Matching slash-command skills exist for the read-only ones — `/list-objects`,
`/describe`, `/dump-describe`, `/record-counts`, `/query`, `/profile`, `/analyze-load-order`,
`/generate-mock-data`, `/generate-related-mock-data`, `/generate-mapping-doc`,
`/check-mapping-balance`, `/auto-map`, `/generate-solution-doc`,
`/bulkops-retry`, `/analyze-org-risk`, `/import-parquet`, `/replicate`,
`/build-load`, `/validate-load`, `/status`, `/data-cloud-query`,
`/data-cloud-status`, `/data-cloud-profile`, `/list-calculated-insights`,
`/query-calculated-insight`, `/list-data-graphs`, `/recommend-batch-size`,
`/suggest-batch-heuristics`, `/generate-migration-run-book`, `/add-migration-run-book-pass`, `/update-migration-run-book`,
`/validate-external-id`, `/import-csv-directory`, `/check-required-mappings`,
`/compare-reference-record`, `/resolve-record-types`, `/generate-target-data-model`,
`/generate-source-data-model`, `/add-bulk-load-sort-column`,
`/check-load-table-duplicate-keys`, `/next-script-number`, `/set-mapping-script`,
`/check-validators`, `/orchestrator-assess`
(`.claude/commands/*.md`). These are the project's "skills": pre-scoped,
no-prompt capabilities for anyone who opens this repo in Claude Code, so
asking for one of these doesn't require re-deriving how to do it from
scratch each time. They're an efficiency layer, not a boundary — general
reasoning/coding (Apex, LWC, architecture work, anything else) is still
available even when there's no dedicated skill for it.

## Hard rules
Each rule keeps its number for stable cross-referencing elsewhere in this
file and in `ROADMAP.md`, but leads with a short name — "rule 6" means
nothing out of context; "the Parent-Batch Sort Rule" is self-explanatory
on its own. Rules 6, 7, 12, and 15 are also formalized as executable
**System Validators** (see `validators/system/` below) — the same check,
just packaged for per-object, retrieve-by-name lookup alongside any
project-specific validator found for one particular object.

1. **Mirror-DB-Only Writes.** `replicate` and any `DROP`/`CREATE` run ONLY
   against the mirror DB `SF_Migration` (or, on a SQLite-backed project,
   the mirror files under `SQL_SQLITE_DIR` — see "SQL backend" below).
   Never point the tools at a source or production database. Confirm
   `SQL_DATABASE`/`SQL_SQLITE_DIR` in `.env` before any replicate.
2. **Live-Org Write Confirmation.** `bulkops` writes to a live Salesforce
   org. Before running it, state which org (`SF_ORG_ALIAS` and auth mode)
   and get confirmation. Never run it speculatively or to "test."
3. **Credential Non-Disclosure.** Never read or print `.env`, `server.key`,
   or any credential. The access token comes from
   `sf org auth show-access-token` (the 2026 CLI update redacts it from
   `sf org display`).
4. **Fingerprint Result Mapping.** Result mapping is fingerprint-based, not
   row-order (see `bulkops.py`). For inserts, the load table must carry a
   unique key mapped to a real SF field (e.g. `Legacy_Id__c`). Do not
   "simplify" this to positional mapping.
5. **No Invented Field Names.** Don't invent Salesforce object or field API
   names — confirm with `describe` or `dump-describe` first.
6. **Parent-Batch Sort Rule** (System Validator —
   `validators/system/parent-batch-sort.md`). Every `*_Load` table for an
   object with a parent lookup/master-detail field must get a `[Sort]`
   column before `bulkops`, via
   `.venv/Scripts/python.exe cli.py add-bulk-load-sort-column <LoadTable> <ParentKeyColumn>`
   (`load_table_prep.py` — plain Python + inline SQL via `sql_dialect.py`,
   not a stored procedure; works on either SQL backend). This numbers rows by
   `ROW_NUMBER() OVER (ORDER BY <parent key>)` so all children of the same
   parent land in a contiguous range — `bulkops.py` submits in `[Sort]` order
   when the column is present, keeping same-parent rows in the same batch
   instead of scattered across batches that process concurrently and
   lock-contend on the shared parent record. Always include this step; don't
   skip it because an object "seems small enough."
7. **Migration Key Integrity Rule** (System Validator —
   `validators/system/migration-key-integrity.md`). Every `*_Load` table
   must have its migration-key column checked for duplicates/NULLs before
   `bulkops`, via
   `.venv/Scripts/python.exe cli.py check-load-table-duplicate-keys <LoadTable> <MigrationKeyColumn>`
   (`load_table_prep.py`, same non-stored-procedure convention as rule 6).
   A duplicate or NULL migration key breaks the fingerprint-based result
   mapping in rule 4 — resolve every duplicate it reports before loading,
   don't let it surface later as an unexplained `ambiguous` count after a
   real Salesforce API call.
8. **Field-Level Security Bundling Rule.** When deploying a new custom
   field via `sf project deploy start`, bundle a `Profile`/`PermissionSet`
   metadata component granting Read+Edit to System Administrator in the
   **same deploy**. API-deployed fields get zero field-level security by
   default (unlike Setup-UI-created fields, which auto-grant the admin
   profile) — don't wait for a manual Setup fix or a failed query to
   surface the gap. Re-evaluate which profile/permission set to grant once
   a dedicated API-only migration user exists.
9. **Email Deliverability Attestation Rule.** Before any `bulkops
   insert`/`upsert`, check Setup > Email Administration > Deliverability
   yourself and pass `--email-deliverability
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
10. **Script Ticket Traceability Rule.** Every new file under
    `sql/transformations/` **or `sql/source_ingestion/`** must have its
    ticket reference (JIRA story/bug key, or whichever ticketing system
    this project actually uses) hardcoded in a comment near the top when
    the script is first built — `import-csv-directory`'s `--ticket`
    enforces this for generated ingestion scripts the same way. Never
    invent a ticket number — if one hasn't been given for the work at
    hand, ask for it before writing the header comment, or state explicitly
    that this project isn't using a ticket system. This is a
    consistency/traceability rule (not a safety-critical one like 1-9), but
    still every project, every script.
11. **Human-Owned Mapping Rule.** Auto-mapping (and any similar first-draft
    tool) only ever produces a first pass on real client data — never a
    finished mapping. Profile, document, auto-map, add notes, then stop.
    The workshop process and the human own everything past that point,
    every time, no exceptions — mapping is iterative and client-facing, not
    something to autonomously complete on someone else's real data. The one
    deliberate exception: data this framework generated itself
    (`generate-mock-data`/`generate-related-mock-data`) has known ground
    truth, so a mapping may be carried all the way to complete for
    practice, testing, and dogfooding new tooling — never for a live
    engagement's actual data. See `ROADMAP.md` #48.
12. **Live Migration Key Validation Rule** (System Validator —
    `validators/system/external-id-validation.md`). Before any `bulkops
    insert`/`upsert` (or a delete resolved by external id), the target
    field being used as the migration key must be checked live via
    `validate-external-id <Object> <Field>` — confirms it's genuinely
    flagged both External ID and Unique in the org's current `describe()`,
    not just assumed from the mapping doc's field name or the transform's
    column name. Do not load until it passes. It is not this framework's
    job to create or fix the field if it isn't — that's another team's
    task; this rule only gates on it already being correctly in place. See
    `ROADMAP.md` #50.
13. **REF_ Audit Column Exemption Rule.** Any Load table column prefixed
    `REF_` (case-insensitive) is a human-only, SQL-side audit field —
    never sent to Salesforce, never flagged by `bulkops`' pre-flight check
    as "not a real field." Excluded automatically from the auto-derived
    column list `bulk_op()` sends (default `--ref-prefix REF_`,
    overridable); an explicitly-passed `send_columns`/column list is never
    second-guessed this way. Not this framework's job to validate what an
    architect puts in one — only to recognize and exclude it. See
    `ROADMAP.md` #55.
14. **No Duplicate Target Field Rule.** No single `CREATE TABLE`/`INSERT
    INTO` column list, and no single mapping-doc sheet, may target the
    same field twice — different scripts/sheets targeting the same field
    is fine and expected (e.g. two source systems feeding the same
    object). `check-mapping-balance` reports both
    (`duplicate_target_fields` — one sheet, two+ source rows choosing the
    same Target Field; `duplicate_implemented_columns` — one transform's
    own column list repeating a name), and `import-csv-directory` refuses
    to stage a CSV whose own header row already has a repeated column. See
    `ROADMAP.md` #56.
15. **RecordType Resolution Rule** (System Validator —
    `validators/system/record-type-resolution.md`, when the object carries
    a `RecordTypeId`). Any Load table populating a `RecordTypeId` must
    resolve the target org's real RecordTypes first via
    `resolve-record-types <Object>` — RecordType Ids are org-specific and
    never portable across orgs. The transform's own SQL should `JOIN
    dbo.RecordTypeMap` by `DeveloperName` (a real, portable identifier) to
    populate `RecordTypeId`, never hand-copy a raw Id from the source.
    This design deliberately has no automatic unresolved-value guard — use
    a `LEFT JOIN` so an unmatched `DeveloperName` surfaces as a visible
    `NULL RecordTypeId`, and verify no row is left unresolved before
    loading. See `ROADMAP.md` #36.

## Validators library
`validators/` is a git-tracked knowledge base of things to check **before**
(and, where automatable, **after**) building a transform for a given
object — retrieved by object name rather than re-derived from memory or
rediscovered the hard way on a live org. Two kinds:

- **System validators** (`validators/system/*.md`) — apply to every
  object, no exceptions. Each formalizes one of the Hard Rules above that's
  also an executable check (rules 6, 7, 12, 15) — the markdown explains
  *why*, and points at the real CLI command that runs it. Not a
  reimplementation of those commands, just a named, retrievable home for
  the same check.
- **Object validators** (`validators/<Object>.md`, e.g. `validators/Task.md`)
  — findings specific to one object, discovered the hard way on a real
  project (a metadata deployment quirk, a polymorphic field, a business-
  rule field cluster that can't be independently mocked). Created the
  first time something object-specific is discovered; nothing is created
  preemptively for an object with no known gotchas yet.

Before building a transform for any object (Standard Workflow step 5,
below), check `validators/<Object>.md` if one exists, and skim
`validators/system/` if this is your first time through this project. A
validator entry is knowledge captured so it survives past one session and
one script — even a correctly-written script that already avoids a known
issue should still have that issue documented here, since this repo gets
handed off before most objects' scripts are ever built the first time.
Some entries are markdown-only (a judgment call, or a check not worth
automating yet); others point at real executable code — both are equally
valid, and a doc-only entry may graduate to executable later, same
tool-proposes-human-commits principle as `reference/batch_size_heuristics.json`.

## Standard workflow: building a new load-table script
When asked to build a script/transform for a new object, follow this order —
don't jump straight to writing T-SQL:
1. **Check the validators library first** — read `validators/<Object>.md`
   if one exists for this object (a project-specific gotcha found the hard
   way last time), and skim `validators/system/` if this is your first
   pass through this project. Cheaper to learn a known issue from a doc
   than to rediscover it on a live org.
2. **Profile the source table first** (`profile-sql-table`) — auto-mapping
   and any real mapping-quality judgment depend on knowing how populated a
   field actually is, not just what it's named. Don't skip to mapping
   before this exists.
3. **Review the mapping** (source field → target field, transformation
   notes) for the object in question — `generate-mapping-doc` to build the
   starting structure, then `auto-map` to suggest a first pass at the
   Target block/Notes from the profiling data plus name/thesaurus/fuzzy
   matching. Both are a starting point for human review, not a finished
   mapping — treat every "Review" recommendation, and any auto-map "No"
   on a field that instinctively looks mappable, as worth a second look.
4. **Confirm target field API names** with `describe`/`dump-describe` (the
   No Invented Field Names Rule, #5) — never guess a field name from the
   mapping doc alone.
5. **Resolve RecordTypes first, if this object carries a `RecordTypeId`**
   — `resolve-record-types <Object>` (the RecordType Resolution Rule,
   #15), so the transform can `JOIN dbo.RecordTypeMap` by `DeveloperName`
   rather than ever hand-copying a raw, org-specific Id from the source.
6. **Build the transform** under `sql/transformations/`, producing the
   `*_Load` table. Include the ticket reference in a header comment (the
   Script Ticket Traceability Rule, #10) — ask for it if it hasn't been
   given. Get the number from
   `.venv/Scripts/python.exe cli.py next-script-number` rather than
   guessing — scripts are numbered in gaps of 10 (010, 020, 030...) so a
   script that needs inserting later between two that already exist can
   take an unused number in that gap without renumbering anything already
   committed; pass `--after <NNN> --before <MMM>` for that insertion case.
   Same command, `--dir source_ingestion`, for `sql/source_ingestion/`.
   Read-only/advisory — it suggests a number, never creates or renames a
   file itself. Once the script is real, run `set-mapping-script` against
   the mapping doc so its header records which script actually implements
   this object — never before, since the script doesn't exist yet earlier
   in this workflow. If this build turned up a new object-specific
   gotcha (a metadata quirk, a field that can't be safely mocked/loaded
   independently, anything a future pass through this object would want
   to know up front), write it into `validators/<Object>.md` now — the
   whole point of the library is that this doesn't get rediscovered next
   time, on this project or another one.
7. **Sort it** — `add-bulk-load-sort-column` against the object's parent
   key (the Parent-Batch Sort Rule, #6), if it has one.
8. **Dupe-check it** — `check-load-table-duplicate-keys` against the
   migration key (the Migration Key Integrity Rule, #7). Resolve anything
   it flags.
9. **Validate the migration key live** — `validate-external-id <Object>
   <Field>` against the actual target field (the Live Migration Key
   Validation Rule, #12). Do not proceed until it reports OK; fixing a
   failing field is another team's job, not something to work around here.
10. Only then move to `bulkops`, with explicit org/auth confirmation (the
    Live-Org Write Confirmation Rule, #2) and, for insert/upsert, Email
    Deliverability checked and passed (the Email Deliverability
    Attestation Rule, #9). Leave `--batch-size` at its `auto` default
    unless you already know a pinned value from a prior run of this same
    project — a scripted integer always wins over the recommendation and
    stays exactly as written, the same "hardcode it in the load script"
    norm every established migration tool uses, just with a smarter
    starting point (see `ROADMAP.md` #15).

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
  auth, SQL connection (SQL Server or SQLite, per `SQL_BACKEND`).
- `sql_dialect.py` — the backend-aware SQL seam every other module routes
  through instead of hand-rolling `OBJECT_ID`/`COL_LENGTH`/bracket-quoted
  T-SQL: table/column existence checks, identifier quoting, `SELECT INTO`
  vs `CREATE TABLE AS SELECT`, `TOP`/`LIMIT`, autoincrement PK DDL, and a
  per-backend Salesforce-field-to-SQL-type mapping. Keyed off the real
  engine in hand (`engine.dialect.name`), not a separately-threaded flag.
- `load_table_prep.py` — hard rules 6/7 (load-table sort column, migration-
  key duplicate/NULL check). Originally SQL Server stored procedures;
  retired in favor of plain Python + inline SQL via `sql_dialect.py`, so
  both work on either backend with no `CREATE PROCEDURE`/`EXEC` step.
- `script_numbering.py` — `next-script-number`'s numbering logic for
  `sql/transformations/`/`sql/source_ingestion/` (gaps of 10, with
  `--after`/`--before` insertion into an existing gap), and
  `script_filename_for()` — resolving which real script implements a given
  object (highest-numbered match wins), shared by `migration_run_book.py`'s
  Load-phase sync and `mapping_doc.py`'s `set-mapping-script`. Purely
  advisory, same "tool proposes, human/Claude commits deliberately"
  principle as `batch_advisor.py`'s recommendations — never creates or
  renames a file.
- `git_info.py` — shared git-repo introspection (current commit/branch,
  and the GitHub base URL when a GitHub remote exists) used by both
  `migration_run_book.py`'s breadcrumb header and `mapping_doc.py`'s
  `set-mapping-script` hyperlink, so every "jump to this file at this
  commit" link across the project is built the same way, from one place.
- `validators_lookup.py` — `check-validators`'s read-only retrieval logic
  for the validators library (`validators/system/*.md`,
  `validators/<Object>.md`). Purely a lookup convenience; writing a new
  validator entry is always a deliberate manual edit, never automated.
- `orchestrator.py` — `orchestrator-assess`'s logic (roadmap #53, Phase 1
  only): `assess_tier()`, the deterministic Tier 1 (Continue Silently)
  through Tier 4 (Full Stop) assessment `docs/ORCHESTRATOR_DESIGN.md`'s
  Foundational Architecture Choice section requires never be model
  judgment (`TIER_NAMES` — every tier gets a real name, never shown as a
  bare number), plus the `BulkOpsLog` history/`ObjectAutomationRisk` reads
  it needs and the opt-in `OrchestratorRunEvent` shadow-mode logging. Reuses
  `reference/orchestrator_thresholds.json` (tier boundary numbers per
  environment, same git-tracked/human-tunable convention as
  `batch_size_heuristics.json`). Never changes how `bulkops` itself is
  gated — Phase 2 (the actual coarse-approval mechanism) isn't built yet.
- `replicate.py`, `bulkops.py`, `type_map.py`, `metadata.py` — org ↔ SQL
  movement and SF type mapping. `type_map.py` is the SQL Server flavor;
  `sql_dialect.py`'s `SqliteDialect.sf_type_to_sql()` is SQLite's.
- `parquet_import.py` — file → SQL movement (Parquet into a typed mirror-DB
  table), the flat-file counterpart to `replicate.py`'s org-sourced path.
  SQL-Server-only for now (see the "SQL backend" note above).
- `source_ingestion.py` — bulk CSV-directory ingestion into the mirror DB
  (roadmap #46): generates/reuses numbered staging scripts under
  `sql/source_ingestion/` (a `BULK INSERT` script on SQL Server; DDL text
  paired with a Python-driven `read_csv`+`to_sql` load on SQLite, since it
  has no `BULK INSERT` equivalent), cross-pass structure drift detection,
  and the opt-in `SourceIngestionLog`. A third flat-file entry point
  alongside `replicate.py`/`parquet_import.py`, for the "client hands over
  a whole directory of CSVs" starting point specifically.
- `load_order.py`, `profiling.py`, `query_tool.py`, `mock_data.py`,
  `snowfakery_data.py`, `mapping_doc.py`, `auto_mapper.py`, `solution_doc.py`,
  `risk_analyzer.py`, `data_cloud.py`, `batch_advisor.py`, `migration_run_book.py`,
  `reference_record.py`, `record_types.py`, `data_model_diagram.py`
  — the Data Architect toolbelt (load-order analysis, profiling, ad hoc
  query, single-object and relationship-aware mock data, mapping doc,
  auto-mapping, solution document generation, org automation risk analysis,
  Data Cloud/D360 query and status tooling, dynamic batch-size recommendations,
  the Migration Run Book, reference-record pull/compare — roadmap #51,
  RecordType DeveloperName resolution — roadmap #36, SDMN-style Mermaid
  data model ERDs — roadmap #57).
- `validators/` — the validators library (see its own section above and
  `validators/README.md`): `validators/system/*.md` formalizes Hard Rules
  6/7/12/15 as named, retrievable checks; `validators/<Object>.md` (e.g.
  `Task.md`) captures object-specific findings as they're discovered.
  `system/` ships as genuine template content, same as `sql/functions/`;
  object files grow project-by-project, same "grows via real corrections"
  principle as the field-synonym thesaurus below — never rediscovered
  fresh on a second project once it's been written down once.
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
- `docs/MIGRATION_RUN_BOOK_TEMPLATE.md` — git-tracked recipe template used by
  `migration_run_book.py`'s `generate_migration_run_book()`: section names, column headers, and
  starter Pre-/Post-Migration items (Email Deliverability, CPQ automation,
  etc.), parsed directly from this file's Markdown tables. Edit this file
  to change what every new project's first Migration Run Book tab starts with — same
  "git is truth" principle as the field-synonym thesaurus and batch-size
  heuristics, but Markdown here since the structure itself is meant to be
  read directly, not hidden behind Python constants.
- `sql/transformations/*.sql` — the migration logic (numbered; run in order).
  Ships **empty** (just `.gitkeep`) — unlike `sql/functions/`, no illustrative
  example script lives here, since a numbered transform is always real,
  project-specific logic for one client's one object, never a generic
  template. The style/pattern an example would show instead lives in
  `docs/MIGRATION_PLAYBOOK.md`'s "Migration Script Pattern" section, as
  documentation rather than a file in the numbered sequence. These scripts
  *are* meant to be committed to git once real
  (that project's own repo/branch, not this framework's shared template
  repo) — a full reset of a practice/test run erases every numbered
  script; a real client project's scripts persist and are never erased
  without explicit approval, even to remove just one.
- `sql/source_ingestion/*.sql` — generated `BULK INSERT` scripts, one per
  client-provided CSV file (`import-csv-directory`, roadmap #46). Numbered
  like `sql/transformations/`, but conceptually upstream of it: these stage
  a raw file into an all-`NVARCHAR(MAX)` table; typing/transforming that
  data is `sql/transformations/`'s job, not this folder's. Reused unchanged
  across every pass — never hand-edited or silently regenerated; only
  `--rebuild` replaces one, and only after a reported structure drift has
  been reviewed.
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
  - `dbo.RecordTypeMap` — `resolve-record-types` output (roadmap #36):
    the target org's real RecordType Id/DeveloperName/Name per object,
    shared across every object in the project like `dbo.FieldProfile` —
    a transform `JOIN`s against this by `DeveloperName` to populate
    `RecordTypeId`, never a raw hand-copied source Id.
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
  - `<Object>_Purge` — `bulkops <Object> delete --where` purge mode's
    materialized Id list (dropped/recreated each purge; its `_Result`
    twin gets the delete outcomes written back).
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
  - `<schema>.SourceIngestionLog` — **opt-in only, never created
    automatically**, same convention as `BulkOpsLog`.
    `enable-source-ingestion-logging --schema <schema>` creates it; from
    then on every `import-csv-directory` call against that schema logs
    itself (table, csv path, script path, status, row count, start/end/
    duration, OS user) — including a drift-blocked attempt, with the exact
    column diff, so it's visible in the Migration Run Book as an `Issue`
    row rather than only a console message. `disable-source-ingestion-logging`
    drops it and its history entirely.
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
- A project's Migration Run Book workbook (`generate-migration-run-book`/`add-migration-run-book-pass`
  output — path is up to the caller, same as `generate-solution-doc`) is
  likewise project-specific, real operational history — not gitignored by
  a fixed pattern since there's no fixed output folder, but treat it the
  same way: commit deliberately, not by default.
- `.env` — connection config. Never commit, never print.
