# CLAUDE.md — SQL-centric Salesforce migration framework

## What this repo is
A Python framework for SQL-centric Salesforce data migration. A SQL database
(local, database `SF_Migration`) is the integration hub — SQL Server, SQLite,
or PostgreSQL, per project (`SQL_BACKEND` in `.env`; see "SQL backend" below).
`replicate` pulls org → SQL; `bulkops` pushes SQL → org and writes the
Salesforce `Id` / `Error` back into the load table. All transformation logic
is SQL under `sql/transformations/`, versioned in git — T-SQL, ANSI SQL, or
SQLite's dialect, depending on the project's backend.
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
- **Use the commands you build.** Once something gets built into a real `cli.py`
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
- **Gather the relevant OKF/validators knowledge before building, never
  after a mistake.** `describe()` tells you an org's *structure*; the
  `okf/` and `validators/` bundles hold its learned *behavior* —
  auto-created records, platform validations, real join/cardinality
  quirks, and (in `okf/synthetic-data-recipes/`) whether a vetted external
  recipe already exists for a cloud. Before building a transform or a new
  cloud's sample-data recipe, run `gather-okf --objects <Object> ...` (and
  `check-validators <Object>`) and actually read the hits — this is
  captured precisely so the next person (or the next pass) doesn't
  rediscover it on a live org. Don't treat these as optional background;
  the Standard Workflow's step 1 makes consulting them a required step, and
  `orchestrator-assess` surfaces them too. Applies most sharply the first
  time this repo touches an unfamiliar cloud.
- **Make sure a Migration Run Book exists once a real migration project starts.**
  After the first `analyze-load-order` for a new project, check whether a
  Migration Run Book workbook exists yet and offer `generate-migration-run-book` if not — this
  is the project's "bigger picture" document (manual steps + scripted
  steps, Pre-Migration through Post-Migration) and shouldn't be an
  afterthought. Before each new environment pass (Dev → UAT → PROD), offer
  `add-migration-run-book-pass` rather than a fresh `generate-migration-run-book`, so the
  recipe (Items/Script names/dependencies/Critical flags) carries forward
  instead of being retyped. See `ROADMAP.md` #16 and `migration_run_book.py`.
- **Offer a post-mortem once a migration project reaches a real
  completion milestone** — a full pass built, loaded, and verified, not
  necessarily final production cutover; a proof-of-concept or a completed
  Dev/UAT pass both count. Copy `docs/MIGRATION_POSTMORTEM_TEMPLATE.md`
  to `postmortems/<YYYY-MM-DD>-<short-slug>.md` and fill it in for real —
  what went well/poorly, reusable artifacts produced (and where they now
  live), target-platform-only knowledge extracted into its own OKF
  subject area if one doesn't exist yet, process/tooling gaps written
  into `ROADMAP.md`. The point is durability, not ceremony: a finding
  that stays only in this one file hasn't finished its job — it should
  end up cross-referenced into `validators/`, `okf/`, or `ROADMAP.md`,
  the same homes every other real finding in this repo already uses, so
  the next project (or the next pass of this one) doesn't rediscover it
  from scratch. See `postmortems/2026-07-17-npsp-to-npc-poc.md` for a
  real, filled-in example.
- **Real work happens on a branch, not `main` — not just a fixed rule, a
  practice adopted deliberately once the project outgrew always-direct
  pushes.** Anything that changes behavior, adds a feature, or fixes a bug
  with real logic gets its own branch (or an isolated worktree for
  genuinely exploratory/risky work — new dependencies, unverified
  compatibility questions, "let's see if this works" spikes) and a real PR
  (`gh pr create`), not a direct push to `main`. Reasoning: a same-day
  ruthless review of a direct-to-main change once found 16 real issues
  already living on `main`, including a crash-on-success bug — a branch
  doesn't prevent bugs, but it keeps them off `main` until review actually
  happens. Trivial fixes (a typo, a one-line doc clarification) can still
  go direct — say so out loud when treating something as trivial rather
  than silently deciding for the user.
- **Let CI finish before merging.** This repo runs its test suite on
  push/PR already (`.github/workflows/tests.yml`) — that should gate the
  merge, not just report after the fact once something's already on `main`.
- **Never merge a PR without explicit approval**, the same rule that
  already governs `git push` to `main`, extended to merging. Opening a PR
  is not the same as approving it — always wait to be told to merge.

## How to operate here: read-only eyes, reviewed hands
- To **look** at the SQL backend (schemas, row counts, samples, validating a
  load), use `sqlcmd` on SQL Server, `psql` on PostgreSQL, or the `sqlite3`
  CLI on SQLite (or the read-only DBHub MCP if configured). Read-only.
- To **change** anything, run the Python CLI verbs via bash. Those are the
  auditable operations.
- The migration logic lives in `sql/transformations/*.sql`. Edit those files;
  don't inline large SQL into one-off shell commands.

## Canonical commands (Windows; venv at .venv)

Invoke every verb as `.venv/Scripts/python.exe cli.py <verb> ...` — call the
venv Python directly (`cd` doesn't persist between bash calls). The prefix is
omitted below for brevity. Read-only unless noted; each entry points at its
ROADMAP # / module for the full rationale.

**Discovery / bootstrap**
- `bootstrap-project brief.yaml run_book.xlsx --tab Dev1` — mechanical first pass from a discovery YAML brief: confirms each named object via `describe()`, runs `analyze-load-order`, scaffolds a Run Book. Never guesses mapping. (ROADMAP #59; `migration_brief.py`)
- `generate-discovery-checklist Account Contact [--output f.md]` — generates the discovery questions to *ask*, from live org signals (validation rules, RecordTypes, out-of-scope lookups). No mirror DB needed. (ROADMAP #60; `discovery_checklist.py`)

**Inspect org** (read-only)
- `list-objects` · `describe Account` · `dump-describe Account`
- `sample-reference-records Account --ids <ids> | --where "<SOQL>" | --limit N` — real field-level shape of *working* records (populated-N-of-M, sample values vs `describe()` flags) + automation summary. Reach for it anytime. (ROADMAP #78; `sample_reference_records.py`)
- `record-counts Account Contact [--all-objects]` — fast per-object counts via `/limits/recordCount`; approximate/cached, not a load-verification substitute. (ROADMAP #41)

**Query**
- `query "SELECT ... LIMIT 10" [--all] [--csv path] [--excel path]` — ad hoc SOQL; basic DLO/DMO lookups work here too. (ROADMAP #18)

**Data Cloud (D360)** (`data_cloud.py`; ROADMAP #18)
- `data-cloud-query "SELECT ... FROM SomeDMO"` — complex Data Cloud SQL (separate tenant token).
- `list-calculated-insights` · `query-calculated-insight <__cio>` · `data-cloud-status <type> [Name]` · `list-data-graphs` — all via core-org SOQL, no tenant token.
- `data-cloud-profile <DMO> "[field=value]"` — Unified Profile lookup by required equality filter; `--fields/--limit/--offset/--orderby`.

**Replicate (org → mirror DB)**
- `replicate Account [--where "..."] [--raw]`
- `replicate-subset Account Contact Opportunity --where "..." --limit 50` — root subset + every named object constrained to rows whose in-scope parents this run just replicated. (ROADMAP #34; `subset_replication.py`)

**Import files (→ mirror DB)**
- `import-parquet file.parquet SourceAccounts [--append]` — Parquet → typed SQL table. (`parquet_import.py`; SQL-Server-only)
- `import-csv-directory dir --ticket PROJ-123 [--rebuild Table ...] [--run-book path --run-book-tab Dev1]` — stages each CSV as all-`NVARCHAR` via a numbered, git-committed script under `sql/source_ingestion/`; cross-pass column-order drift hard-stops that file until `--rebuild`. (ROADMAP #46; `source_ingestion.py`)
- `enable-source-ingestion-logging --schema dbo` · `disable-source-ingestion-logging --schema dbo` — opt-in `<schema>.SourceIngestionLog`.

**Profile** (ROADMAP #47; `profiling.py`)
- `profile-salesforce Account` (live aggregate SOQL) · `profile-sql-table Account` · `export-profile-excel f.xlsx` — skips already-profiled by default; `--reprofile` forces a refresh.

**Load order / RecordTypes**
- `analyze-load-order Account Contact Opportunity ...`
- `resolve-record-types Account` — writes target RecordType Id/DeveloperName into `dbo.RecordTypeMap` for the transform to `JOIN` by `DeveloperName` (RecordType Resolution Rule #15). (ROADMAP #36)

**Data model diagrams** (Mermaid SDMN-style; ROADMAP #57; `data_model_diagram.py`)
- `generate-target-data-model Account Contact ... --output m.md [--mapping-path ...]` — relationships from live `describe()`, real.
- `generate-source-data-model --subject-area "Name:T1,T2" --output-dir models/ [--mapping-path ...]` — staging tables; relationships are naming-convention guesses, labeled `(guessed)`.

**Mock data** (never touches Salesforce)
- `generate-mock-data Account --count 50` — Mockaroo (needs `MOCKAROO_API_KEY`); writes `<Object>_Mock`. (`mock_data.py`)
- `generate-related-mock-data Account Contact --count Account=10 --count Contact=3` — Snowfakery, relationship-aware; `NAME=N-M` randomizes per-parent count; recipe to `_stage/`. (`snowfakery_data.py`)
- `generate-adversarial-mock-data Account --count 50 --scenario <s>:<field>:<rows> ...` — corrupts rows on purpose to provoke known Bulk API failure classes (`duplicate_key`/`oversized_string`/`missing_required`/`invalid_picklist`/`bad_reference`), validated vs `describe()`. Writes `<Object>_Mock_Adversarial` with a `REF_` scenario column. (ROADMAP #62; `adversarial_mock_data.py`)

**Mapping** (human-owned — Hard Rule 11; `mapping_doc.py`/`auto_mapper.py`)
- `generate-mapping-doc Account mapping/Migration_Mapping.xlsx SourceAccounts` — one tab per object (reuse the same workbook path); one row per source field, blank Target block; auto-fills profiling %.
- `set-mapping-script Account mapping/...xlsx [--dir source_ingestion]` — fills the sheet's Transform Script header (auto-resolved, GitHub-linked); run only *after* the transform exists.
- `check-mapping-balance Account mapping/...xlsx sql/transformations/<NNN>_account_load.sql` — diffs Target block vs the transform's `INSERT` list both ways; flags invalid fields + Rule-14 duplicate targets.
- `check-required-mappings Account mapping/...xlsx` — flags `Migrate=Yes` rows with no Target; suggests via `auto-map` matching (read-only). (ROADMAP #49)
- `auto-map Account mapping/...xlsx SourceAccounts` — first-pass suggestions (name/synonym/fuzzy) gated by profiling data; never overwrites a human's Target; needs the source profiled. (ROADMAP #47/#48)

**Solution doc**
- `generate-solution-doc Solution.docx Account Contact ... --mapping-path ...` — Word design doc from load-order + mapping + profiling; `--company/--project/--prepared-by/--appendix/--template`. (`solution_doc.py`)

**Load-table pre-flight** (Hard Rules 6/7; `load_table_prep.py`; either backend; both validate the column exists first)
- `add-bulk-load-sort-column Account_Load AccountId [--schema dbo]` (Parent-Batch Sort Rule #6)
- `check-load-table-duplicate-keys Account_Load Legacy_Id__c [--schema dbo]` (Migration Key Integrity Rule #7; exits nonzero on findings)

**Load — WRITES TO SALESFORCE** (confirm the target org first — Live-Org Write Confirmation Rule #2; `bulkops.py`)
- `bulkops Account upsert Account_Load --external-id Legacy_Id__c --email-deliverability system-email-only` — insert/upsert **require** `--email-deliverability no-access|system-email-only|all-email` (Email Deliverability Attestation Rule #9); `all-email` also needs `--confirm-external-email-risk`. Every sent column is pre-flight-checked against live `describe()`; `REF_`-prefixed columns are never sent (Rule 13; `--ref-prefix` overrides).
- `bulkops Account delete Account_Purge --external-id Legacy_Id__c` — delete by external id (resolved to real Ids first).
- `bulkops Account delete --where "<SOQL>" [--dry-run] [--hard-delete]` — purge by filter into `<Object>_Purge`; run `--dry-run` first; soft delete is default; `--hard-delete` is **irreversible** + needs the Bulk API Hard Delete perm. No delete-all default — write `"Id != null"` explicitly. Rule 2 applies. (ROADMAP #32/#84)
- Flags: `--batch-size auto|none|<N>` (default `auto` dynamic recommendation; a pinned integer always wins — ROADMAP #15) · `--run-book <path> --run-book-tab <name>` (opt-in Load-phase sync — #16) · `--engine python|sfdmu` (sfdmu = SFDX-Data-Move-Utility, upsert/update only, needs `--external-id`; `sfdmu_bridge.py` + README).
- `bulkops-retry Contact_Load` — copies only failed rows to `<table>_Retry`; does not call Salesforce (resubmit separately).
- `triage-failures Contact_Load [--object Contact] [--mapping-path ...]` — groups failures by normalized error signature, maps known Bulk API codes to likely cause + next command; advisory. (ROADMAP #61; `failure_triage.py`)

**Reset / reconcile / readiness**
- `reset-dev-cycle --objects Account Contact [--purge-org-where "Obj:WHERE"] [--dry-run]` — drops this project's `_Mock`/`_Load`/`_Purge` tables + clears their profiling rows (mirror-DB-only, safe). `--purge-org-where` also deletes matching org test data via `bulkops delete` (Rule 2 applies — confirm the org). (ROADMAP #63; `dev_cycle.py`)
- `reconcile-load-counts Account ... [--mapping-path ...] [--load-table Obj=Table]` — cross-checks source vs Load vs `bulkops` counts. (ROADMAP #64; `reconciliation.py`)
- `assess-migration-readiness Account [--migration-key Obj=Field] [--mapping-path ...] [--load-table Obj=Table]` — one go/no-go view re-checking Rules 6/7/12, org-risk coverage, mapping balance, Email Deliverability, reconciliation. (ROADMAP #65; `readiness.py`)

**Activity logging** (opt-in per schema; presence of the table is the on/off switch)
- `enable-bulkops-logging --schema dbo` · `disable-bulkops-logging --schema dbo` — `<schema>.BulkOpsLog`; every `bulkops` call then logs itself (never logs `query` reads). `disable` drops history — confirm.

**Org risk / orchestrator / batch size**
- `analyze-org-risk Account Contact ... [--mapping-path ...] [--skip-child-shape-check]` — active validation rules/triggers/Flows/workflows/approvals via Tooling API, plus `child_record_risk.py`'s empirical auto-generated-child detection (managed-package automation the Tooling API can't see). Advisory. (`risk_analyzer.py`)
- `orchestrator-assess Account [--log-id N] [--environment uat|prod]` — deterministic Tier 1–4 for a completed `bulkops` run (Phase 1 only, read-only, never gates `bulkops`). (ROADMAP #53; `docs/ORCHESTRATOR_DESIGN.md`; `orchestrator.py`)
- `enable-orchestrator-logging --schema dbo` · `disable-orchestrator-logging --schema dbo` — `<schema>.OrchestratorRunEvent` shadow-mode log.
- `recommend-batch-size Opportunity` · `suggest-batch-heuristics` — batch-size recommendation / candidate `reference/batch_size_heuristics.json` edits (never writes the file). (ROADMAP #15; `batch_advisor.py`)

**Migration Run Book** (ROADMAP #16; `migration_run_book.py`; `--script-dir` on the generate/pass/update verbs points script resolution at an attempts workspace)
- `generate-migration-run-book run_book.xlsx --tab Dev1 --objects Account Contact [--project/--source-env/--target-env/--ticket-url/--ticket-label]` — first/new tab from `docs/MIGRATION_RUN_BOOK_TEMPLATE.md`; `--objects` auto-fills the Load phase; refuses to overwrite an existing tab.
- `add-migration-run-book-pass run_book.xlsx --from-tab Dev1 --to-tab UAT --target-env UAT_ALIAS` — new pass; copies recipe columns, blanks results; `--target-env` never carried forward.
- `update-migration-run-book run_book.xlsx --tab Dev1` — pulls new `BulkOpsLog` (Load) + `SourceIngestionLog` (Pre-Migration) rows since the last watermark; idempotent; never overwrites human entries.
- `generate-run-book-flowchart run_book.xlsx --tab Dev1 --output m.md` — Mermaid process flow from Stage/Object/Dependency/Status; edges only from "After: X" text. (ROADMAP #52)
- `generate-pass-summary run_book.xlsx --tab Dev1 --output s.md [--load-table Obj=Table]` — plain-English client-facing pass summary; `--load-table` adds a `triage-failures` root cause. (ROADMAP #66; `pass_summary.py`)

**Validate / diff**
- `validate-external-id Account Legacy_Id__c` — confirms the field is externalId+unique live (Live Migration Key Validation Rule #12); exits nonzero on failure.
- `compare-reference-record Account Account_Load <RecordId> --migration-key Legacy_Id__c [--key-column/--id-column/--error-column]` — diffs a live hand-created record vs its Load row by migration key. (ROADMAP #51; `reference_record.py`)

**Read SQL directly** (read-only): `sqlcmd -S localhost -E -d SF_Migration -Q "..."` (`-E` = Windows auth; prefer a read-only login). On a SQLite project, use the `sqlite3` CLI against the `<schema>.db` under `SQL_SQLITE_DIR`.

### SQL backend
`SQL_BACKEND` in `.env` is `mssql` (default), `sqlite`, or `postgresql`, per
project (`sql_client.py`/`sql_dialect.py`). SQLite uses `SQL_SQLITE_DIR` +
`SQL_SQLITE_SCHEMAS` (one `<schema>.db` per schema, each `ATTACH`ed);
PostgreSQL reuses `SQL_SERVER`/`SQL_DATABASE`/`SQL_UID`/`SQL_PWD` plus
`SQL_PORT` (5432) and `SQL_POSTGRES_SSLMODE` (`prefer`). The load engine
(`replicate`, `bulkops`, hard rules 6/7, `import-csv-directory`) works on all
three; several data-architect tools (`profiling`, `auto_mapper`,
`solution_doc`, `parquet_import`, `record_types`, `reference_record`) and the
`sql/functions/` library are **SQL-Server-only for now** — port incrementally
via `sql_dialect.py` when a real SQLite/Postgres project needs it. The full
dated account of the Postgres port — every bug found and fixed, the live
end-to-end verification, the `postgres:16` CI service — is in **ROADMAP #69**,
not repeated here.

### Slash-command skills
Every read-only command above also has a matching `/verb` slash-command skill
under `.claude/commands/*.md` (the harness lists them in-session). They're a
pre-scoped efficiency layer, **not a boundary** — general reasoning/coding
(Apex, LWC, architecture, anything else) is always available even with no
dedicated skill. When you add a new command, add its skill wrapper too.

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
    practice, testing, and self-testing new tooling — never for a live
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

The library is an **Open Knowledge Format (OKF) v0.1 bundle** (roadmap
#72, the pilot): every non-reserved `.md` file carries YAML frontmatter
with a `type:` field (`SystemValidator`, `ObjectValidator`, or `Guide`),
plus recommended `title`/`description`/`tags`/`timestamp` —
`validators/README.md`'s "Frontmatter (OKF)" section has the format. The
OKF reserved filenames `index.md` (directory listing) and `log.md`
(change history) live at the `validators/` root only, **never inside
`system/`** (where they'd be mistaken for system validators —
`validators_lookup.py` also excludes them defensively). A new validator
entry needs its frontmatter, an `index.md` line, and a dated `log.md`
entry; `tests/test_okf_conformance.py` enforces the frontmatter half in
CI. `check-validators` parses the frontmatter and displays it as a
compact structured header (Type/Tags/Resource) rather than raw YAML —
the same parse-then-present pattern OKF's own reference consumer uses.

## Standard workflow: building a new load-table script
When asked to build a script/transform for a new object, follow this order —
don't jump straight to writing SQL:
1. **Gather the knowledge that already exists — validators AND OKF — before
   writing anything.** This step is not optional and not a skim-past: the
   whole point of these bundles is that a known issue is learned from a doc,
   not rediscovered on a live org after a failed load.
   - **Validators**: read `validators/<Object>.md` if one exists (a
     project-specific gotcha found the hard way last time), and skim
     `validators/system/` on your first pass through this project.
     `check-validators <Object>` retrieves both.
   - **OKF**: run `gather-okf --objects <Object> [<Object> ...]` to surface
     the target-platform behavior relevant to these objects — auto-created
     records, platform validations, real join/cardinality quirks — that
     `describe()` alone can't tell you, plus (via
     `okf/synthetic-data-recipes/`) whether a vetted **external recipe**
     already exists for this cloud before you author one from scratch. Read
     the hits it returns; do not proceed past a relevant one unread. This is
     the same knowledge the orchestrator gathers when it assesses a load —
     surfaced up front here so you head off the issue instead of scoring it
     after the fact.
   - **Data-shape profile** (if one exists): `show-data-shape <Object>` for the
     structured, machine-readable behavioral shape — auto-created children,
     active automation, real field population — that `describe()` alone can't
     give. Build/refresh it with `build-data-shape-profile <Object>` (roadmap
     #83) once `analyze-org-risk`/`profile-salesforce` have run. On a **fresh
     clone with no org profile yet**, `show-data-shape <Object> --cloud <cloud>`
     falls back to the committed cloud-level profile
     (`okf/<cloud>/data-shapes/<Object>.json`), and `gather-okf` surfaces those
     profiles automatically — so the cloud-true behavior (what auto-creates,
     date-range pairs, standard structure) is known before profiling your own
     org. Once you've built an org profile worth generalizing, promote it to
     that shared IP with `generalize-data-shape <Object> --cloud <cloud>` (it
     strips org-specifics — org custom fields, this org's automation counts /
     field population / auto-generation rates — keeping only cloud-true facts).
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
   file itself. **Naming pitfall, found live** (NPSP-to-NPC migration
   proof-of-concept): if the object's name itself contains another real
   object's name as a whole word (`AccountContactRelation`,
   `CampaignMember`, `GiftCommitmentSchedule`,
   `GiftTransactionDesignation`, etc.), don't put an underscore between
   the embedded segments in the filename (`accountcontactrelation_load.sql`,
   not `account_contact_relation_load.sql`) — `script_numbering.matches_token()`'s
   whole-token matching means an underscore-separated compound name still
   matches the shorter, unrelated object as a substring, and since
   `script_filename_for()` picks the highest-numbered match, a later
   compound-name script can silently outrank the real script for that
   shorter object everywhere `migration_run_book.py`/`set-mapping-script`
   resolve it. `script_filename_for()`'s own optional `known_objects`
   parameter now defends against this too (ROADMAP #76's real fix,
   built after the workaround) — every caller in this repo that has a
   natural object-name set already passes it — but this naming
   convention is still the safest default when writing a new script by
   hand, since a caller without `known_objects` gets no protection. See
   `matches_token()`'s own docstring in `script_numbering.py` and
   `ROADMAP.md` for the full account. Once the
   script is real, run `set-mapping-script` against
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

**`sample-reference-records` isn't one of the numbered steps above on
purpose** (roadmap #78) — real migration work happens in sprints, and the
true shape of a target object is often not fully understood until UAT
surfaces it, so this is meant to be reached for at any point, not gated
to a single step. Genuinely useful before step 6 (learning an unfamiliar
object's real shape before writing the transform), but just as useful
mid-sprint when refining, or after a UAT finding reveals a field nobody
thought to include — the same way `query`/`describe` themselves get used
throughout a project, not just once.

## Library vs. attempts workspace
Once a project has produced a real, proven set of transform scripts,
mapping workbook, and Migration Run Book tab (e.g. this repo's own NPC
fundraising sample data build, `sql/transformations/230-430`, committed as a
reference implementation rather than disposable client work — see
`okf/nonprofit-cloud/fundraising-sample-reference-implementation.md`),
a **second rebuild attempt against a freshly reset org must not overwrite
that reference state.** This is the same experience a new engineer
picking up this repo would have: use its knowledge and artifacts to
start fresh, without corrupting the starting point other people (or a
future pass of this same project) still need.

- **Library** — `sql/transformations/`, `sql/source_ingestion/`,
  `mapping/`, a project's committed `migration_run_book.xlsx`,
  `validators/`, `okf/`. Proven, shared reference state. Never worked on
  directly for a new rebuild attempt — only ever updated deliberately,
  once a new attempt's findings are worth folding back in (see
  "Promotion" below).
- **Attempts workspace** — a new top-level `attempts/<date>-<slug>/`
  folder (e.g. `attempts/2026-07-21-npc-sample-v2/`), mirroring `sql/`
  and `mapping/` inside it, for a new rebuild attempt's own scripts,
  mapping doc, and Run Book tab (or file) built *from* the library's
  knowledge without touching it:
  - `.venv/Scripts/python.exe cli.py next-script-number --dir attempts/<date>-<slug>/sql`
  - `.venv/Scripts/python.exe cli.py set-mapping-script Account attempts/<date>-<slug>/mapping/mapping.xlsx --dir attempts/<date>-<slug>/sql`
    (`--dir` on both commands accepts either the two shortcut keywords —
    `transformations`/`source_ingestion`, resolving to `sql/transformations`/
    `sql/source_ingestion` exactly as before — or any literal path, so an
    attempts-workspace directory works the same way with no new flag.)
  - `.venv/Scripts/python.exe cli.py generate-mapping-doc Account attempts/<date>-<slug>/mapping/mapping.xlsx SourceAccounts`
    (already a free-form output path — no change needed here.)
  - `.venv/Scripts/python.exe cli.py generate-migration-run-book attempts/<date>-<slug>/migration_run_book.xlsx --tab Dev1 --objects Account --script-dir attempts/<date>-<slug>/sql`
    (`--script-dir`, also on `add-migration-run-book-pass` and
    `update-migration-run-book`, controls only where the Load phase's
    script-resolution/hyperlink logic looks — left off, it resolves
    against `sql/transformations/` exactly as before.)
  - `.venv/Scripts/python.exe cli.py assess-migration-readiness Account --script-dir attempts/<date>-<slug>/sql`
    (same override, for the mapping-balance gate.)
  - `attempts/` is **not** gitignored — a real attempt's scripts/mapping
    are meant to be committed on their own feature branch and reviewed
    via PR, the same branch-per-change convention as everything else in
    this repo (see "Real work happens on a branch, not `main`" above).
- **Promotion (Replace model)** — once an attempt is proven, a deliberate
  PR moves its scripts into `sql/transformations/` (replacing the
  superseded number range), its mapping workbook becomes the new
  canonical `mapping/*.xlsx`, and its Run Book tab becomes the new
  canonical tab. One canonical "best known" reference lives in the
  library at a time — the superseded version is never kept as a second
  live copy, only recoverable through git history. `validators/`/`okf/`
  are the one exception: findings discovered *during* an attempt should
  be written into those shared files directly, in real time, the same as
  any other finding — they're durable knowledge, not attempt-specific
  work product, so there's no separate promotion step for them.
- **No dedicated tooling for scaffolding or promoting an attempt** —
  deliberately out of scope for now, matching this repo's own
  don't-build-until-proven-needed philosophy. Creating
  `attempts/<date>-<slug>/{sql,mapping}/` is a plain directory creation;
  promotion is a plain `git mv` + PR, exactly like every other
  deliberate change in this repo already works. Worth a real command
  later only if this convention gets used enough to justify it.

## Licensing
MIT licensed, Copyright JP Ziller LLC (see `LICENSE`) — free to use, modify,
and redistribute (including commercially), provided the copyright notice is
kept. Don't reference by name any tool this framework builds its own
replacement for (DBAmp, Field Trip, Salesforce Inspector Reloaded, Maven,
Workbench, etc.) in code, comments, docs, or generated file contents
(including spreadsheet column headers) — describe the behavior generically
instead. This does **not** apply to tools this framework actually integrates
with rather than replaces (Mockaroo, Snowfakery, SFDMU) — naming those is fine.

## Where things live
- `cli.py` — CLI entry point wiring every verb together.
- `config.py`, `sf_client.py`, `sql_client.py` — settings/env, Salesforce
  auth, SQL connection (SQL Server, SQLite, or PostgreSQL, per `SQL_BACKEND`).
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
  `validators/<Object>.md`), plus `parse_frontmatter()` — the one
  OKF-aware piece (roadmap #72): splits a file's YAML frontmatter from
  its body, tolerating absent/malformed frontmatter per the OKF spec's
  own conformance rules, and feeds `check-validators`' structured
  Type/Tags/Resource header. OKF reserved filenames (`index.md`/`log.md`)
  are excluded from the system-validator listing. Purely a lookup
  convenience; writing a new validator entry is always a deliberate
  manual edit, never automated.
- `okf_lookup.py` — `gather-okf`'s read-only retrieval logic for the
  `okf/` bundle (roadmap #83): surfaces the OKF docs relevant to a set of
  objects (matched against each doc's frontmatter title/description/tags)
  or a whole subject area, so target-platform behavior and external recipe
  sources are consulted **before** building, not rediscovered after a
  mistake — the OKF-side counterpart to `validators_lookup.py`. Reuses
  that module's `parse_frontmatter()`/`_RESERVED` rather than duplicating
  frontmatter handling. Called by CLAUDE.md's Standard Workflow step 1 and
  by `orchestrator-assess` (which surfaces an object's relevant OKF as
  part of its assessment). Purely a lookup convenience; writing a new OKF
  entry is always a deliberate manual edit.
- `data_shape.py` — `build-data-shape-profile`/`show-data-shape`'s logic
  (roadmap #83, v1): aggregates the *behavioral* signals the framework
  already produces — live `describe()` structure, `analyze-org-risk`'s
  `ObjectAutomationRisk` (active automation + `child_record_risk.py`'s
  auto-generated-child detection), and `profile-salesforce`'s `FieldProfile`
  (real field population) — into one structured, machine-readable per-object
  JSON profile a tool can reason over, complementing `describe()` metadata
  with the shape it can't give (what the platform auto-creates, what's really
  populated). Read-only; writes `data_shapes/<Object>.json`. Missing upstream
  signals report `scanned: false`/`profiled: false`, never a misleading clean
  zero. The structured counterpart to the prose in `validators/`/`okf/` — the
  "score the build from known data shape" direction #83 sets up.
  `assess-migration-readiness` and `orchestrator-assess` now **surface** an
  object's profile (advisory, never changing their verdict/tier); a harder
  *scoring* step (a signal becoming a gate) is a follow-up.
  **Cloud-level generalization** is built (roadmap #83): `generalize-data-shape
  <Object> --cloud <cloud>` (`generalize_profile()`) promotes an org profile to
  committed `okf/<cloud>/data-shapes/<Object>.json` — stripping org-specifics
  (org custom fields via `_api_name_kind()`, this org's automation counts /
  field population / auto-generation rates) and keeping only cloud-true facts
  (standard/packaged structure, auto-generated-child relationships, date-range
  pairs). `gather-okf` surfaces those committed profiles (`find_cloud_profiles()`)
  and `show-data-shape --cloud` falls back to one, so a fresh clone knows an
  object's platform behavior before profiling its own org.
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
- `subset_replication.py` — `replicate-subset`'s logic (roadmap #34):
  reuses `load_order.build_dependency_edges()`/`compute_load_order()` the
  same in-memory-only way `snowfakery_data.py` already does (no
  `dbo.ObjectDependency` persistence) to replicate a root object's subset
  first, then automatically constrain every other named object's
  `replicate.replicate()` call to rows whose in-scope parent lookup(s)
  point at Ids actually just replicated — read back from the mirror table
  itself via `_read_replicated_ids()`, not a second live-org round-trip.
  `_build_child_where()` groups a child's edges by field first, so a
  polymorphic lookup naturally unions every in-scope parent's Ids under
  one field (correct OR semantics, no separate detection pass); distinct
  fields on the same child combine with AND. `replicate.py` itself gained
  one small addition for this — a `limit` param on `replicate()`,
  appended as a SOQL `LIMIT`, mirroring how `where` already worked.
- `sfdmu_bridge.py` — the `--engine sfdmu` alternate load engine (opt-in,
  `bulkops` defaults to `python`/`bulk_op()` unchanged). Reuses
  `bulkops.py`'s own `_derive_sent_columns()`/`_preflight_check()`/
  `_check_email_deliverability()`/`_writeback_inplace()`/
  `_format_datetime_columns_for_csv()` rather than duplicating any of that
  logic — only the actual Salesforce write differs, shelling out to
  `sf sfdmu run` (`forcedotcom/SFDX-Data-Move-Utility`, Apache-2.0) against
  a generated `export.json`. Its own module docstring has the full account
  of every real, confirmed-live gotcha found building it: the specific
  `Id,Name`/`externalId:Id`/`Readonly` declaration an already-loaded parent
  object needs (a bare-`Id` query makes SFDMU treat it as degenerate and
  silently exclude any lookup pointing at it), that parent also needing its
  own tiny source CSV (its distinct already-resolved Ids, or the match
  silently resolves blank instead of erroring), SFDMU's own target-file
  naming (always `<Object>_update_target.csv`, even for an `Upsert`
  operation), why this framework's own `id_column` must NOT be sent to
  SFDMU (it gets treated as SFDMU's own row-tracking key, suppressing the
  full business-column echo-back needed to match results by external id),
  and the exact same datetime-string XSD parse failure `bulk_op()`'s own
  `_format_datetime_columns_for_csv()` already existed to fix, just never
  applied to this second CSV export path until found live here too. v1
  scope is upsert/update only (a real migration key is required either
  way, matching this framework's own convention everywhere else) with
  polymorphic lookup fields (e.g. `Task.WhatId`) skipped automatically, not
  guessed at — load those via the `python` engine as a separate pass.
- `failure_triage.py` — bulk-load failure triage assistant (roadmap #61):
  groups a completed `bulk_op()` run's failures by normalized error
  signature (`bulkops.py`'s own `_normalize_error_signature()`) and maps
  well-known Salesforce Bulk API error codes to a likely root cause and
  which existing command to run next. Advisory only — never changes
  data, never re-runs `bulkops`.
- `adversarial_mock_data.py` — adversarial mock data generation (roadmap
  #62): reuses `mock_data.py`'s describe()-derived Mockaroo schema
  directly, then deliberately corrupts a chosen, disjoint subset of rows
  per requested scenario to provoke known Bulk API failure classes on
  purpose. Writes to `<Object>_Mock_Adversarial`, tagging each corrupted
  row's scenario in a `REF_`-prefixed column (hard rule 13) so `bulkops`
  never sends it to Salesforce.
- `pass_summary.py` — auto-drafted client-facing pass summary (roadmap
  #66): drafts a plain-English Markdown summary from a Migration Run
  Book tab's own Load-phase results, optionally enriched per-object with
  `failure_triage.py`'s plain-language root cause via an explicit
  `--load-table` mapping (never guessed from a Run Book row's Object
  cell, which may be a bare object name or a script filename).
- `dev_cycle.py` — reset-dev-cycle command (roadmap #63): drops every
  `_Mock`/`_Mock_Adversarial`/`_Load`/`_Load_Result`/`_Load_Retry`/
  `_Purge`/`_Purge_Result` table for a given object list and clears their
  profiling rows (mirror-DB-only, always safe); optionally also purges
  matching org test data via a thin, undisguised pass-through to
  `bulkops.py`'s own `purge_by_filter()` (#32) — the exact same
  Hard-Rule-2-gated delete, not a separate mechanism. No skill wrapper —
  same reasoning as the main `bulkops` command itself, since this can
  trigger a real Salesforce delete depending on the flags passed.
- `reconciliation.py` — row-count reconciliation report (roadmap #64):
  cross-checks source table row count → Load table row count →
  `bulkops`' most recent submitted/succeeded/failed counts per object,
  flagging anywhere they don't reconcile. Read-only.
- `readiness.py` — migration readiness score (roadmap #65): one aggregate
  go/no-go view per object, re-checking or re-presenting hard rules
  6/7/12, `analyze-org-risk` coverage, `check-mapping-balance`, Email
  Deliverability attestation, and `reconciliation.py`'s own row-count
  reconciliation (#64) — no new checks invented. Read-only.
- `migration_brief.py` — migration brief intake / project bootstrap
  (roadmap #59): parses a minimal YAML "migration brief" a discovery-AI
  session could produce directly, confirms every named object is real
  via live `describe()`, runs `analyze-load-order`, and scaffolds a
  Migration Run Book — the mechanical first pass, closing the hand-off
  gap between upstream client discovery and this framework's own
  tooling. Never guesses mapping/field lists/transform logic.
- `discovery_checklist.py` — discovery question checklist generator
  (roadmap #60), the companion to `migration_brief.py` running the other
  direction: generates the questions an architect should ask during
  discovery from live org signals (active validation rules, RecordType
  usage, out-of-scope lookup dependencies) rather than a generic
  template. Read-only, no engine dependency — runs before the mirror DB
  even needs to exist.
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
  `risk_analyzer.py`, `child_record_risk.py`, `data_cloud.py`, `batch_advisor.py`,
  `migration_run_book.py`, `reference_record.py`, `sample_reference_records.py`,
  `record_types.py`, `data_model_diagram.py`
  — the Data Architect toolbelt (load-order analysis, profiling, ad hoc
  query, single-object and relationship-aware mock data, mapping doc,
  auto-mapping, solution document generation, org automation risk analysis,
  Data Cloud/D360 query and status tooling, dynamic batch-size recommendations,
  the Migration Run Book, reference-record pull/compare — roadmap #51,
  reference-record sampling to learn a target object's real field-level
  shape — roadmap #78, RecordType DeveloperName resolution — roadmap #36,
  SDMN-style Mermaid data model ERDs — roadmap #57, Mermaid process-flow
  diagrams from a Migration Run Book tab — roadmap #52).
  `child_record_risk.py` is `analyze-org-risk`'s own auto-generated-child-
  record check (see that command's own description above) — a real
  managed-package-automation blind spot the Tooling API can't see, closed
  by empirically diffing real reference data instead of introspecting
  metadata, the same real-data-over-metadata idea `sample_reference_records.py`
  already established one level down (a field's real shape vs. `describe()`).
- `validators/` — the validators library (see its own section above and
  `validators/README.md`): `validators/system/*.md` formalizes Hard Rules
  6/7/12/15 as named, retrievable checks; `validators/<Object>.md` (e.g.
  `Task.md`) captures object-specific findings as they're discovered.
  `system/` ships as genuine template content, same as `sql/functions/`;
  object files grow project-by-project, same "grows via real corrections"
  principle as the field-synonym thesaurus below — never rediscovered
  fresh on a second project once it's been written down once.
- `okf/` — the second OKF v0.1 bundle (roadmap #72), for external/
  industry knowledge that isn't a client engagement's own SQL mirror-DB
  artifact: official Salesforce documentation, target-platform data
  models, and migration patterns. Template content, always committed.
  Describe-and-link, never duplicate wholesale — a concept's `resource:`
  points at the real source document rather than copying it in, per the
  OKF spec's own `resource:`/`# Citations` convention (confirmed against
  `data_cloud.py`/ROADMAP #18-19's existing "link and summarize, don't
  inline-copy" precedent for external Salesforce docs). First subject
  area: `okf/npsp-to-npc/` — NPSP-to-Agentforce-Nonprofit (Nonprofit
  Cloud) migration guidance, built from Salesforce's own official
  migration guide and field-mapping workbook. Deliberately doesn't try to
  force this Salesforce-object-to-Salesforce-object mapping data through
  `mapping_doc.py`/`auto_mapper.py` (both hard-require a real, profiled
  SQL source table — confirmed by reading their code, not assumed; this
  content has no SQL table behind it at all) or `load_order.py` (strictly
  `describe()`-driven against a live org, no static-sequence input hook)
  — those tools do their real job correctly; this data just isn't their
  input shape. `okf/` stayed reader-less for a while by design (OKF's own
  point is "no required tooling"), but roadmap #83 added one deliberately
  — `gather-okf` (`okf_lookup.py`) — not to *require* tooling, but because
  a passively-present doc gets glossed over: the command actively surfaces
  the OKF relevant to the objects in play, and CLAUDE.md's Standard
  Workflow + `orchestrator-assess` both call it so the knowledge is
  consulted before a mistake, not after. Second subject area:
  `okf/nonprofit-cloud/` — split
  out of `okf/npsp-to-npc/` once that bundle's own platform-validation
  docs turned out to have zero NPSP-specific content. Deliberately
  source-agnostic: knowledge true of the Nonprofit Cloud/AFNP target
  platform itself, regardless of which system a client migrates *from* —
  a future "Raiser's Edge to NPC" or "Bloomerang to NPC" bundle reuses it
  directly instead of re-deriving the same platform facts.
- `postmortems/` — dated, filled-in migration post-mortems (see the
  "Offer a post-mortem" behavior default above and
  `docs/MIGRATION_POSTMORTEM_TEMPLATE.md`). Plain narrative Markdown, not
  an OKF bundle — no frontmatter ceremony, since a post-mortem is a
  retrospective account, not a structured lookup entry. Its job is to be
  the prompt that produces new `validators/`/`okf/`/`ROADMAP.md` entries,
  not a standalone archive.
- `sample_data/` — the committed, shareable **NPC fundraising sample
  dataset** (roadmap #82): `sample_data/recipes/*.recipe.yml` are the 10
  numbered, curated Snowfakery recipes that generate the fully-synthetic
  mock data the `sql/transformations/230-430` reference implementation
  consumes, and `sample_data/README.md` is the ordered "generate the mock
  data + load a fresh test org" runbook. This is what makes the dataset
  reproducible in a clone (the recipes used to live only in gitignored
  `_stage/`, so a clone couldn't rebuild the data at all). The recipes run
  standalone via `snowfakery run`, or are regenerated fresh from the
  target org's `describe()` via the `generate-related-mock-data` commands
  in the README — the framework path never drifts from the org schema.
  Fully synthetic, no real client data; safe to commit and share. Pairs
  with `okf/nonprofit-cloud/fundraising-sample-reference-implementation.md`
  (the transform-side reference) — this is the data-generation side.
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
- **SQL tables this framework creates** (not files — all deploy
  targets only, safe to drop/regenerate by re-running the command that
  built them, never edited by hand, never the source of truth for anything
  git already tracks; most are backend-agnostic per the "SQL backend"
  porting work above — a few noted there are still SQL-Server-only):
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
  auth boundary), `DOCKER.md` (roadmap #68/#69 — the Docker local dev
  environment quickstart for both the `mssql` and `postgres` profiles,
  auth-mode guidance, and what's deliberately out of scope),
  `CONTEXT_DOC_STANDARDS.md` (the standard for keeping this file lean and
  load-bearing — the rubric/routing/invariants the `/optimize-claude-md`
  skill applies; run it when this file grows past a comfortable budget).
- `Dockerfile`, `docker-compose.yml`, `docker/init-db.sh` (roadmap
  #68/#69) — the containerized local dev environment, one Dockerfile
  shared by two Compose **profiles**: `mssql` (default — SQL Server 2022
  Developer Edition + `sqlserver`/`app-mssql`) and `postgres`
  (PostgreSQL 16 + `postgres`/`app-postgres`), never both running at
  once. The shared `app-*` image has the ODBC driver + `sqlcmd`,
  `postgresql-client` (`psql`/`pg_isready`), and the Salesforce CLI
  preinstalled. `docker compose --profile <name> up -d` replaces
  README.md's manual SQL Server/PostgreSQL/driver setup steps; the repo
  is bind-mounted into the `app-*` container, not copied in, so this is a
  packaging change, not a design change — every Hard Rule below applies
  identically regardless of profile or whether `cli.py` runs in a venv or
  in either container. `docker/init-db.sh`'s Postgres branch also creates
  a `dbo` schema (`CREATE SCHEMA IF NOT EXISTS`) since Postgres has no
  built-in one the way SQL Server does, and every `cli.py` command
  defaults `--schema` to `"dbo"` regardless of backend. One real
  exception, not a Hard Rule but worth knowing: `SF_AUTH_MODE=cli` itself
  does NOT work inside either container (Salesforce's May 2026 CLI
  update moved org auth into the host OS's own keychain, unreachable from
  a Linux container) — `jwt`/`password` only there. See `docs/DOCKER.md`'s
  auth-mode section for the full finding, and `ROADMAP.md` #69 for the
  full account of the Docker Postgres build, its own live verification,
  and a real bug it surfaced (`replicate.py` writing Salesforce booleans
  as `0`/`1` instead of real Python `True`/`False`, which Postgres's
  native `BOOLEAN` columns reject outright).
- `ROADMAP.md` — idea backlog and build status for planned tooling.
- `metadata/*.json`, `mapping/*.xlsx` — generated, org-specific artifacts.
  Gitignored by default (every org's schema/mappings differ, so these
  aren't template content) — commit your own deliberately if a real
  engagement wants a versioned copy. `mapping/npc_*.xlsx` is one such
  deliberate exception, carved out in `.gitignore` — the NPSP-to-NPC
  migration proof-of-concept's own mapping workbooks, kept as a real
  reference implementation rather than disposable single-project output
  (see `okf/npsp-to-npc/reference-implementation.md`).
- A project's Migration Run Book workbook (`generate-migration-run-book`/`add-migration-run-book-pass`
  output — path is up to the caller, same as `generate-solution-doc`) is
  likewise project-specific, real operational history — not gitignored by
  a fixed pattern since there's no fixed output folder, but treat it the
  same way: commit deliberately, not by default.
- `.env` — connection config. Never commit, never print.
