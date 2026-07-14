# Roadmap / idea backlog

Notes on future tooling for this framework — captured as ideas to review and
scope later, not committed designs. Nothing here is built yet unless marked.

## Scope: what this framework is (and isn't)

The filter every idea below gets evaluated against, stated explicitly so
it doesn't have to be re-derived each time: this is a **data movement and
remediation tool** — move data between a Salesforce org and SQL Server
(`replicate`/`bulkops`), and clean/transform/validate it in T-SQL and
Python along the way (profiling, mapping, mock data, load-order,
run-book tracking). It is **not an integration platform** — not trying
to be a generic API-to-API bridge, a real-time sync tool, or a
replacement for enterprise integration middleware.

The purpose is to make a data architect's or data engineer's life
better with **free tools they'd otherwise pay for or piece together
across several different products** — not to build something for every
interesting Salesforce API that exists. An idea earns a place here
because it removes real friction from *moving or fixing migration data*,
not because the API is novel or well-documented. When something gets
looked at and doesn't clear that bar, it's recorded as **Researched —
not pursued (out of scope)**, distinct from *not built yet* (on the
list, just not done) or *deliberately deferred* (in scope, just not
prioritized) — so the reasoning survives and nobody re-proposes the same
API without seeing why it was already turned down.

## Capabilities at a glance

Read this table first — it's the answer to "what can this framework do
today," so a fresh full read of every section below shouldn't be necessary
just to find out what's built. Update this table in the same commit as any
future item that flips status, so it never drifts from the sections it
summarizes.

| # | Item | Status | Command / skill | What it means / when you'd use it |
|---|---|---|---|---|
| 1 | Reusable SQL function library | Built (library, no CLI wrapper) | `sql/functions/` | Common cleanup helpers (splitting a "Full Name" into first/last, validating emails/phones, stripping bad characters) written once in T-SQL instead of every migration reinventing them. **"No CLI wrapper" means there's no `cli.py` command for this** — you deploy one function at a time by running its `.sql` file directly (`sqlcmd -i sql/functions/cleansing/GetFirstName.sql`), then call it by name inside your own transform SQL (`dbo.GetFirstName(src.full_name)`). That's deliberate: which functions a migration needs varies project to project, so there's nothing to "wrap" — see the conversation above for the full reasoning on why one isn't planned. |
| 2 | Load-order dependency analyzer | **Built** | `analyze-load-order` | Figures out the safe order to load your objects so parents always land before their children — e.g. Account before Contact — so you don't hit "no such Account" errors from loading a child first. Run this before writing any transforms for a multi-object migration. |
| 3 | Field-mapping spreadsheet tool | **Built** | `generate-mapping-doc`, `check-mapping-balance` | Generates the spreadsheet where you record "this source field goes to that Salesforce field" — the standard document a data architect reviews with the client before any transform gets written. `check-mapping-balance` then double-checks your finished transform actually matches what the spreadsheet says. |
| 4 | Solution document generator | **Built** | `generate-solution-doc` | Auto-writes the migration design/solution Word document (what's being migrated, in what order, field-by-field detail) from data this framework already has, instead of a human writing it from scratch. |
| 5 | Org metadata risk analyzer | **Built** | `analyze-org-risk` | Checks the target org for things that could silently reject or interfere with your load — active validation rules, Apex triggers, Flows — *before* you run a real load, so you find out ahead of time instead of from a confusing failure mid-load. |
| 6 | Mock/demo data generation | **Built** | `generate-mock-data`, `generate-related-mock-data` | Generates realistic fake records for testing or demos, without touching any real Salesforce data. `generate-mock-data` does one object at a time; `generate-related-mock-data` generates several objects *linked together* (e.g. Accounts that really do have Contacts pointing back at them), with `--count NAME=N-M` for a randomized per-parent count (e.g. "1 or 2 Contacts each", "~half the Accounts get an Opportunity"). |
| 7 | Data profiling toolset | **Built** | `profile-salesforce`, `profile-sql-table`, `export-profile-excel` | Tells you how populated and clean a field actually is — what % of rows have a value, how many distinct values, min/max — before you decide whether it's even worth migrating. Run this before mapping fields, not after. |
| 8 | Ad hoc query tool | **Built** | `query` | Run a quick SOQL query from the command line for a fast lookup, without opening a separate query tool or browser extension. |
| 9 | Console output polish | **Built** | (applies to `query`/`profile-*`) | Query/profile results print as a readable table instead of a raw text dump. |
| 10 | Auto-mapping | **Built** | `auto-map` | Suggests a first-draft field mapping automatically (matching names, a synonym list, and a data-quality check) so you're reviewing/correcting a draft instead of starting the mapping spreadsheet from a blank sheet. |
| 11 | Bulk load pre-flight check + retry + delete-by-external-id | **Built** | `bulkops` (built in), `bulkops-retry` | This is the actual "push data into Salesforce" step — insert/update/upsert/delete via Bulk API 2.0. The pre-flight check catches typo'd/non-writable fields *before* burning a real API call; `bulkops-retry` lets you resubmit only the rows that failed instead of the whole load again. |
| 12 | Parquet file import | **Built** | `import-parquet` | Brings a Parquet file's data into SQL Server as typed columns — a second way to get source data in, alongside pulling directly from a Salesforce org. |
| 13 | Email Deliverability attestation gate | **Built** | `bulkops` (built in), hard rule 9 | Forces you to actually go check Setup's Email Deliverability setting before any insert/upsert that could send real email to real people, and pass what it shows as a flag. This is a required human confirmation, not an automatic check — Salesforce has no API to read that setting. |
| 14 | Load activity logging + analytics | Logging **Built** (opt-in); analytics not built | `enable-bulkops-logging`, `disable-bulkops-logging` | Optional, off-by-default record of every `bulkops` run (what, when, how many succeeded/failed) written to a SQL Server table, so you can look back at history instead of relying on console scrollback. Turn it on once per schema; it then logs automatically. |
| 15 | Dynamic batch sizing from org metadata review | **Built** — confirmed live against a real org (`D360_PLAYGROUND`): static/auto/none modes all produced the correct job counts and log entries | `recommend-batch-size`, `suggest-batch-heuristics`, `bulkops --batch-size` | Automatically start heavily-automated objects (Opportunity, CPQ/Billing, etc.) at a smaller batch size, adjusted further from this org's own automation and this project's own load history — full rationale printed, and a scripted value always overrides it. |
| 16 | Migration Run Book (manual + programmatic step tracking) | **Built** — structure mirrors a real client migration-status tab; `dbo.BulkOpsLog` tie-in also built | `generate-migration-run-book`, `add-migration-run-book-pass`, `update-migration-run-book` | A living, per-project Excel workbook: one unified table (Stage/Object/Dependency/Status/Critical/Person Responsible/Begin-End Time/Execution Time/JIRA Ticket Link/Notes/record counts) covering every phase, phases marked by a banner row — one tab per pass (Dev/UAT/PROD), each new tab copying the recipe forward while blanking result columns (Status reset to "Not Started") for a fresh run. Status/Critical use live Excel conditional-formatting colors, not a one-time paint. `update-migration-run-book` (or `bulkops --run-book`/`--run-book-tab` automatically) pulls new `BulkOpsLog` rows into the Load phase — fills in a pending placeholder or inserts a new row, idempotent via a per-tab watermark, never overwrites a human's own row. Recipe structure lives in `docs/MIGRATION_RUN_BOOK_TEMPLATE.md`, git-tracked and human-editable. Every tab also gets a header with Project/Source-Target Environment, hyperlinked Git repo/commit/scripts breadcrumbs, and an optional ticket-system project link. |
| 17 | Fuzzy matching / dedup | Deprioritized, not built | — | Idea: flag "these two records are probably the same person/company" for dedup — deliberately lower priority than everything else here for now. |
| 18 | Data Cloud (D360) query support | **Built** — all 5 findings researched, 4.5 confirmed live (Data Graph query-by-id/lookup-key is written but unverified — no test Data Graph exists yet) | `data-cloud-query`, `list-calculated-insights`, `query-calculated-insight`, `data-cloud-status`, `data-cloud-profile`, `list-data-graphs` | Query Data Cloud objects (DLOs/DMOs), Calculated Insights, Unified Profile data, Data Graph metadata, and check processing status for Data Streams/DSOs/Identity Resolution/Data Transforms/Calculated Insights/Data Graphs — all confirmed live against a real org (`D360_PLAYGROUND`), all real CLI commands now, not ad hoc scripts. |
| 19 | Data Cloud semantic model reference | Not built, depends on #18 | — | Idea: a reference for what a DMO's fields/relationships actually *mean* in business terms, the same way `dump-describe` documents a CRM object's schema today. Needs #18 first. |
| 20 | DSO refresh/error monitoring | **Built** — both the Data Stream (ingestion connector) and the DSO itself, confirmed as genuinely separate objects | `data-cloud-status data-stream`, `data-cloud-status dso` | Check whether a Data Cloud Data Stream or the DSO it feeds last refreshed successfully and whether either hit errors, before trusting the data behind it — confirmed live via plain SOQL, no Data Cloud tenant token needed. |
| 21 | DSO→DLO mapping read + auto-map | Not built — needs API research | — | Idea: read (and maybe suggest) how a DSO's fields map into a DLO — the Data Cloud version of what `auto-map` (#10) already does for CRM field mapping. |
| 22 | SQL-Server-backed local DSO ingestion (API-driven file-upload replacement) | **Dead end** for the actual ask — confirmed no REST API exists for Data Cloud's Local File Upload connector; the real Ingestion API is a heavier, separate path not being pursued | — | Wanted an API to drive Data Cloud's simple local-file-upload workflow directly — that connector type is browser-UI-only by design, no API surface to build against. See #44 for the direction being pursued instead. |
| 23 | Data Kit / Bundle documentation | Not built, depends on #18/#19 | — | Idea: document what's actually in a Data Cloud Data Kit for a data architect scoping a migration — the Data Cloud version of the mapping spreadsheet (#3). |
| 24 | Calculated Insight scripting + testing + CI/CD | Not built, depends on #18 | — | Idea: version Data Cloud Calculated Insight definitions in git and test them like code, instead of only building them by hand in Data Cloud Setup. |
| 25 | Web UI for less-technical users | Not built (future) | — | Idea: a browser-based front end so someone who isn't comfortable with a terminal or Claude Code could still use this framework's tools. |
| 26 | SSO / multi-user access control | Not built, depends on #25 | — | Idea: once a Web UI exists, this is "who's allowed to log in, and as whom." Not a concern today since it's just a CLI one person runs. |
| 27 | Open query in SSMS (stage + launch) | Not built, depends on #25 | — | Idea: write a query to a file and launch SSMS pointed at it, for someone who'd rather review/run it in SSMS's own editor than in this framework's console output. |
| 28 | Pluggable integration-hub backend — SQLite alongside SQL Server | **Built**; MongoDB still deferred | `SQL_BACKEND=mssql\|sqlite`, `sql_dialect.py`, `load_table_prep.py` | The real load engine (`replicate`, `bulkops` incl. activity logging/retry, hard rules 6/7, CSV ingestion) now works on either backend, keyed off the engine itself (`engine.dialect.name`). SQL-Server-only cleansing/matching functions and several data-architect tools stay SQL-Server-only, a deliberate scope boundary. MongoDB remains deferred — a genuinely different data model, not a mechanical syntax difference. |
| 29 | Shared/VM-hosted SQL Server for multi-user access | Not built, deliberately deferred — prototyping is single-user/local for now | — | Idea: for when more than one person needs to work against the *same* mirror database at the same time, instead of everyone having their own local SQL Server. |
| 30 | Additional migration source connectors (Snowflake, MongoDB, etc.) | Not built, deliberately deferred | — | Idea: pull source data from more systems (Snowflake, MongoDB), the same way this framework already pulls from a Salesforce org (`replicate`) or a flat file (`import-parquet`). |
| 31 | Target-count/scaled mock data generation | Not built, builds on #6 | — | Idea: say "keep generating mock Accounts until the org has 50,000 total" instead of a fixed count every run — useful for realistic load/performance testing. |
| 32 | Bulk test-data cleanup by filter | **Built** | `bulkops <Object> delete --where` (+ `--dry-run`) | "Delete every mock record I created for this test" as one command: a SOQL WHERE clause resolves the matching Ids into `<Object>_Purge` and deletes them through the normal `bulkops` path (batch sizing, logging, run-book sync all apply). `--dry-run` previews the matched count first; no delete-everything default; standard Recycle-Bin-recoverable delete only. |
| 33 | Scratch org lifecycle + auto-seeded test data | Not built, deliberately deferred | — | Idea: let this framework spin up a disposable Salesforce scratch org and automatically fill it with mock data, instead of assuming an org already exists. |
| 34 | Relationship-consistent subset replication | Not built, builds on #2 | — | Idea: pull a small, realistic *slice* of an org — e.g. 50 pilot Accounts and everything genuinely related to them — instead of either replicating everything or hand-coordinating a `--where` filter across every object yourself. |
| 35 | Relative date shifting utility | Not built | — | Idea: a helper that shifts old dates forward so migrated data still makes sense relative to today — e.g. a contract end date that's already in the past wouldn't make sense to a Flow expecting a future date. |
| 36 | RecordType DeveloperName resolution for cross-org migration | **Built**, hard rule 15 | `resolve-record-types <Object>` | Queries the target org's real RecordType rows and writes them into `dbo.RecordTypeMap`, a plain reference table the transform `JOIN`s against by `DeveloperName` to populate `RecordTypeId` — never a raw, org-specific Id hand-copied from the source. Deliberately a T-SQL reference table (chosen directly over automatic `bulkops` resolution), matching `AddBulkLoadSortColumn`'s convention. |
| 37 | CLI alternative to Data Cloud's Profile Explorer | **Built** — same command as #18's Unified Profile finding | `data-cloud-profile` | Look up Unified Profile data (a specific person's attributes) via one command instead of Data Cloud Setup's own multi-click Profile Explorer (pick a Data Space, then an entity, then an attribute, repeatedly) — no Data Space parameter needed at all, confirmed live. |
| 38 | Real-data anonymization for demos/scratch orgs | Not built | — | Idea: take a real client org's actual data and scramble the sensitive fields (names, emails, phones) into realistic-looking fakes — same relationships/volume, no real PII — for client demos or scratch-org seeding. Different from #6, which generates synthetic data from scratch rather than replacing real values. |
| 39 | Ticket system (JIRA or equivalent) read/comment integration | Not built, needs API research | — | Idea: post comments to a specific JIRA (or equivalent) ticket directly (e.g. load results), and cross-reference GitHub commits/PRs tied to that ticket — deeper than the Migration Run Book header's static project link (#16). |
| 40 | Configuration Workbook drift detection | Not built — blocked on a real template | — | Idea: read a team's existing "Configuration Workbook" (how developers document their build) and cross-check it against the actual deployed metadata — the same category of problem `check-mapping-balance` (#3) solves for mapping docs, applied to build documentation instead. Waiting on a real example template before this gets designed. |
| 41 | Per-object record counts via the recordCount API | **Built** | `record-counts` | One HTTP call for many objects' record counts instead of a SOQL COUNT() per object — fast rough triage across many objects, confirmed live to be an approximate/cached snapshot (can lag real inserts by more than a few seconds), so not a substitute for `profile-salesforce`'s exact count when validating a load actually landed. |
| 42 | Unit tests + CI for the pure-logic modules | **Built** | `tests/*.py` (pytest) + `.github/workflows/tests.yml` | 59 pytest cases over the no-org-required logic (batch-size ladder math, load-order toposort/cycle grouping, run-book template parsing + `_object_matches()`'s Order/OrderItem regression, mapping-doc INSERT-INTO regex + #56's duplicate-field detection, auto-mapper name normalization/matching, #50's `validate_external_id_field`, #46's script-column parsing/drift comparison + #56's duplicate-header check), run automatically on every push/PR via GitHub Actions (fixed to invoke via `python -m pytest`, not bare `pytest`, after every prior run silently failed on `ModuleNotFoundError`). Live org verification stays the standard for org-touching paths; this covers the logic underneath. |
| 43 | Salesforce GraphQL API | **Researched — not pursued (out of scope)** | — | Nested relationship traversal and small-batch mutations in one call — genuinely useful for a UI making many round-trips, but this framework's actual needs (bulk extraction, bulk DML) are already better served by SOQL/Bulk API 2.0. See write-up for the specific reasoning. |
| 44 | Native database connectors (SQL Server / MongoDB) as the Data Cloud source | Not built, needs research | — | Idea: let Data Cloud pull directly from the mirror DB (or MongoDB) via its own native connector types instead of this framework pushing data via API — no custom ingestion code needed, but network-reachability and schedule-vs-on-demand questions need answering first. |
| 45 | Data Transform authoring as code | Researched, real progress — blocked on more real examples before writing generation code | — | Idea: generate a Data Transform's JSON definition programmatically instead of building it by hand in the drag-and-drop canvas. Confirmed real (export/import round-trip works, JSON shape partly mapped, 11-node taxonomy documented) — not yet buildable with confidence since only one real example (3 of ~11 node types) has been seen. |
| 46 | Source directory ingestion + cross-pass structure validation | **Built** | `import-csv-directory <dir> --ticket <ref>` (+ `--rebuild`, `--run-book`) | Generalizes a real client's proven hand-built convention (all-`NVARCHAR(MAX)` staging via `BULK INSERT`, typed later via T-SQL) into a bulk, directory-wide command: generates a numbered, git-committed script per new file, reuses it unchanged on every later pass, and hard-stops a file (not the whole batch) if its CSV's current column list no longer matches the script's — comparing the full *ordered* list, since `BULK INSERT` maps columns positionally. Syncs into the Migration Run Book's Pre-Migration phase. |
| 47 | Pass-aware mapping/profiling workflow state | **Built** | `--reprofile` (profiling), automatic review-pass framing (`auto-map`) | Consults timestamp state that already existed (`FieldProfile.AnalyzedDate`, `SourceRegistry.AutoMappedDate`) rather than inventing new tracking: profiling now skips by default on an already-profiled object/table, and `auto-map` frames a second run as a review pass (already-decided vs. freshly-suggested counts) instead of a first-pass summary. |
| 48 | Auto-map autonomy boundary (real vs. mock data) + learning feedback loop | Boundary confirmed **Hard Rule 11**; learning-loop tooling not built | — | On real client data, auto-map only ever produces a first pass (profile/document/auto-map/notes) — humans finish it via workshop, always. On self-generated mock data, a full mapping can be completed autonomously for practice. Separately: after a human finishes a *real* mapping, ask (every time, never assumed) whether to contribute what was learned to the shared synonym thesaurus — staged for a human to review and commit later, never auto-written. |
| 49 | Migrate-flagged-but-unmapped field detection + suggestion | **Built**, refines #3/#10 | `check-required-mappings <Object> <MappingPath>` | Flags every mapping-doc row marked `Migrate Data = Yes` with no Target Field chosen, and attempts a `describe()`-driven suggestion via the same matching `auto-map` uses. Read-only — never writes into the doc; that's `auto-map`'s job. |
| 50 | Migration-key/External ID field validation against live describe() | **Built**, hardens rules 4/7 | `validate-external-id <Object> <Field>` (hard rule 12) | Confirms a named target field is genuinely `externalId`+`unique` in the live org's describe() before it's trusted as a migration key — explicit object+field parameters (same convention as `CheckLoadTableDuplicateKeys`/`--external-id`), not auto-detected from the mapping doc. Read-only, exits nonzero on failure so it can gate a script. Not this framework's job to create that field, just to gate on it being correctly in place. |
| 51 | Reference-record pull/compare tool | **Built** | `compare-reference-record <Object> <LoadTable> <RecordId> --migration-key <Field>` | Diffs a live, hand-created reference record against the Load table row its migration key corresponds to — matched by migration key (read off the live record), not `Id`, since a hand-created record was never loaded via `bulkops`. Read-only review aid; never writes back. |
| 52 | Mermaid process-flow diagrams from the Migration Run Book | **Built** | `generate-run-book-flowchart <path> --tab <name> --output <path.md>` | Generates a Mermaid flowchart from a run-book tab's Stage/Object/Dependency/Status structure as a `.md` file — renders natively on GitHub, and is already the right input format for a Lucid Chart import later. One subgraph per phase, edges only from real "After: X" dependency text (never fabricated), node color matching the workbook's own Status palette. Read-only, no Salesforce/SQL connection needed. |
| 53 | Supervised end-to-end load orchestrator | **Phase 1 built, tested, live-validated** — Phase 2 gated on a real UAT pass | `orchestrator-assess`, `enable-orchestrator-logging` | Deterministic tier assessment (`orchestrator.py`'s `assess_tier()`, `docs/ORCHESTRATOR_DESIGN.md`) live-validated against real `BulkOpsLog` history across all four tiers. Zero change to Hard Rule 2 — every `bulkops` call is exactly as `ask`-gated as before. The actual coarse-approval mechanism (Phase 2) isn't built yet, on purpose, until Stage 1 shadow mode runs against a real UAT-tier project. |
| 54 | Chat-driven human-in-the-loop alerting/control (Slack/Teams) | Not built — roadmap idea per explicit request | — | Idea: outbound alerts to Slack/Teams instead of email (low-risk, near-term), and further out, driving a production run from Slack itself — the latter needs a real architecture decision (listener vs. polling) that would require revisiting `docs/SECURITY_OVERVIEW.md`'s current "no network listener" trust model. |
| 55 | `REF_`-prefixed human-only audit columns, excluded from bulkops | **Built**, hard rule 13 | `--ref-prefix` (default `REF_`) | Raised directly from real DBAmp-era experience: a `REF_`-prefixed Load table column is a human-only SQL-side audit field, excluded from the auto-derived sent-column list and from the pre-flight "not a real field" check — never reaches the API, never aborts the load. |
| 56 | Duplicate target-field detection (scripts + spreadsheets) | **Built**, hard rule 14 | `check-mapping-balance` (extended), `import-csv-directory` | Raised directly: a single `CREATE TABLE`/`INSERT INTO` column list, or a single mapping-doc sheet, must never target the same field twice — different scripts/sheets doing so is fine and expected. `check-mapping-balance` reports both `duplicate_target_fields` and `duplicate_implemented_columns`; `import-csv-directory` refuses a CSV whose own header already repeats a column. |
| 57 | Data model ERD diagrams — source subject-area models + target model, SDMN-inspired | **Built** | `generate-target-data-model`, `generate-source-data-model` | Mermaid ERDs approximating Salesforce Data Model Notation (verified against the real SDMN guide — its per-entity color/border coding and diamond relationship symbol genuinely can't be reproduced in Mermaid; its solid-vs-dashed identifying/non-identifying line distinction can, and maps onto master-detail vs lookup). Target model relationships are real (`load_order.build_dependency_edges()`); source model relationships are a naming-convention guess only, always labeled and reported for review, never presented as confirmed. |
| 58 | Bidirectional convert: Data Transform JSON ↔ Code Extension Python | Not built — depends on #45 | — | Idea: JSON→Python translates the canvas Data Transform's `nodes`/`ui` export into an `entrypoint.py` against the `datacustomcode` SDK, for the node types #45 already confirmed (`load`/`formula`/`outputD360`) — safe today, since it's known structure to known SDK calls. Python→JSON is the harder direction: it inherits #45's own generation blocker (8/11 node types still unconfirmed) and only ever recognizes a constrained, canvas-representable subset of Python, refusing whatever falls outside it rather than guessing. |
| 59 | Migration brief intake / project bootstrap | **Built** | `bootstrap-project brief.yaml run_book.xlsx --tab Dev1` | A minimal YAML file (objects in scope, target org, ticket, per-object notes) that a discovery-AI session hands off, and one command that validates every named object against live `describe()`, runs `analyze-load-order`, and scaffolds the Migration Run Book — turning "discovery just finished" into a concrete first command sequence instead of a cold start. Never guesses mapping/field lists/transform logic. |
| 60 | Discovery question checklist generator | **Built** | `generate-discovery-checklist <Objects> [--output path.md]` | Given a candidate object list, generates the per-object questions an architect should ask the client — driven by real signals this framework already computes (active validation rules' `ErrorDisplayField`, `RecordTypeId` presence, out-of-scope lookup dependencies), not a generic template. Read-only, no engine dependency. |
| 61 | Bulk-load failure triage assistant | **Built** | `triage-failures <table> [--object] [--mapping-path]` | Groups a load's failures by normalized error signature (`_normalize_error_signature()`) and maps common Salesforce error codes (`DUPLICATE_VALUE`, `REQUIRED_FIELD_MISSING`, `STRING_TOO_LONG`, `INVALID_CROSS_REFERENCE_KEY`, etc.) to a likely root cause and which existing command to run next — turning "N rows failed" into "1 root cause, here's where to look." `--object`/`--mapping-path` enable real cross-references (mapping-doc/`ObjectAutomationRisk`) instead of static text alone. |
| 62 | Adversarial mock data generation | **Built** | `generate-adversarial-mock-data <Object> --count N --scenario scenario:field:rows` | A companion to `generate-mock-data` that deliberately provokes known failure classes (duplicate migration keys, oversized strings, invalid picklist values, missing required fields, bad lookup references) so validation-rule collisions surface during Dev testing, not during a real client load. Writes to `<Object>_Mock_Adversarial`, tagged via a `REF_`-prefixed column so the same table can go straight into a real `bulkops` call. |
| 63 | Reset-dev-cycle command | **Built** | `reset-dev-cycle --objects Account Contact [--purge-org-where Object:WHERE] [--dry-run]` | Codifies the manual reset ritual this project did by hand every dogfooding cycle: drops every `_Mock`/`_Mock_Adversarial`/`_Load`/`_Load_Result`/`_Load_Retry`/`_Purge`/`_Purge_Result` table for the given objects and clears their profiling rows (mirror-DB-only, always safe); `--purge-org-where` optionally also purges matching org test data via the same `bulkops delete --where` mechanism (#32) — hard rule 2 applies in full. No skill wrapper, same as `bulkops` itself. |
| 64 | Row-count reconciliation report | **Built** | `reconcile-load-counts <Objects> [--mapping-path] [--load-table Object=Table]` | Cross-checks source row count → Load table row count → `bulkops`' most recent submitted/succeeded/failed counts per object, flagging anywhere they don't reconcile (missing Load table, dropped rows, never loaded, or a stale prior run) — a data-completeness auditor, not a per-tool spot check. |
| 65 | Migration readiness score | **Built** | `assess-migration-readiness <Objects> [--migration-key Object=Field] [--mapping-path] [--load-table Object=Table]` | One aggregate READY/NOT READY view per object across hard rules 6/7/12, `analyze-org-risk` coverage, `check-mapping-balance`, Email Deliverability attestation, and #64's row-count reconciliation — a "not checked" gate never blocks the verdict by itself, only an explicit failure does. |
| 66 | Auto-drafted client-facing pass summary | **Built** | `generate-pass-summary <path> --tab <name> --output <path.md> [--load-table Object=Table]` | Drafts a plain-English "here's what happened this pass" summary from the Migration Run Book's own Load-phase results, ready to send a client stakeholder. `--load-table` optionally enriches any object's failures with a plain-language root cause via `triage-failures` (#61) instead of just a raw failed count — never guessed from the Run Book's own Object cell. |

Also load-bearing but not numbered above: `replicate` (org → SQL) and the
`sql/transformations/*.sql` transform pattern are the core migration
pipeline every other tool builds on — see `README.md`/`CLAUDE.md`, not
this roadmap, since they're not backlog items, they're the framework's
actual spine.

---

## 1. Reusable SQL function library

Source of inspiration: a personal archive of past migration projects
(`SQLFunctions_Migration`) had ~40 T-SQL functions worth cleaning up into a
generic, reusable set for this framework's `sql/` tree.

- **Utility belt** (lowest effort, highest reuse): number cleaning, ASCII
  stripping, HTML stripping, string splitting, init-cap, int validation,
  leap-year check, months-between-dates, XML entity escaping, Base64/URL
  encode-decode.
- **Name/email/address cleansing**: full-name → first/last name splitting
  (handles Mr/Mrs/Dr prefixes, Jr/Sr/II/III suffixes), email validation,
  role-based email detection (`info@`, `sales@`, etc.), postal address
  abbreviation expansion.
- **Fuzzy matching** (for dedup/match-merge across source vs. target):
  Jaro-Winkler, Metaphone, Soundex, N-gram comparison.
- **Reference lookups**: state/country name ↔ code tables — port as static
  data, no logic to clean up.
- **Explicitly NOT porting verbatim** — two files carry third-party
  copyright notices ("developed by Herb Whitacre, all rights reserved" and
  "Copyright Apps Associates 2018") — rewrite these from scratch off the
  public algorithm/spec instead of copying, since this repo is going MIT.
- **Rebuilt instead of ported — BUILT**: a legacy tool-coupled column/
  permission pre-flight stored procedure's concept (validate a load table's
  columns against the target object's createable/updatable fields before
  submitting) is now a live `describe()` check built directly into
  `bulkops.py`'s `bulk_op()` — see #11 for the full writeup.

## 2. Load-order dependency analyzer — BUILT (`load_order.py`)

Problem: migrations with many objects need inserts/updates run in an order
that respects lookup and master-detail relationships (parent before child).
Past practice at other tools was to document this by hand.

`python cli.py analyze-load-order Account Contact Opportunity ...`:
- Reads describe() for every object passed in.
- Builds a dependency graph from lookup/master-detail reference fields whose
  target is also in the requested set.
- Topologically sorts it (Kahn's algorithm) into load levels + a flattened
  sequence.
- Separates out self-referencing fields (e.g. `Account.ParentId`) as
  two-pass-load flags rather than letting them block ordering.
- Flags genuine multi-object cycles (e.g. A ↔ B) as unresolved rather than
  guessing which edge to break.
- Writes results to `dbo.ObjectDependency` (raw edges) and
  `dbo.ObjectLoadOrder` (computed order) in the mirror DB, so later scripts
  can query the graph instead of re-deriving it from describe() each time.

Not yet wired into `bulkops` run order automatically — still a
recommend-and-review step, not an auto-pilot one.

## 3. Field-mapping spreadsheet tool — BUILT (`mapping_doc.py`)

Column structure modeled on a real-world field-inventory-and-mapping
template reviewed for format only (structure/column names, not content):
one row per **source** field (not target — that was an earlier, wrong
orientation this tool started with and was corrected), a block of
migration-decision columns, then a blank Target block for a human to fill
in once a mapping is decided.

`python cli.py generate-mapping-doc <Object> <path.xlsx> <SourceTable>`:
- Header block (Source/Target object names), then one row per column in
  the named SQL source table: Source Object / Field API / Field Label /
  Data Type / Description / Data Profile Populated On / Data Profile % / Notes /
  Migrate Data / Migrate Field / Biz Review Req / Biz Decision / [spacer] /
  Target Object / Field API / Field Label / Data Type / Description / Notes.
  The Target block is left blank — does **not** guess the mapping (that's
  auto-mapping, a separate item below).
- If profiling data already exists for the source table (`profile-sql-table`),
  "Data Profile Populated On"/"Data Profile %" are pre-filled from it automatically.
- One shared workbook for the whole project (one tab per object) — reuse
  the same output path across objects. (Caught and fixed a real bug here:
  the first version overwrote the entire file per call via `pd.ExcelWriter`'s
  default mode, silently erasing every other object's sheet. Now appends/
  replaces just that object's sheet.)

`python cli.py check-mapping-balance <Object> <mapping.xlsx> <transform.sql>`:
- Diffs the mapping doc's Target block against the transform's actual
  `INSERT INTO` column list, in both directions — documented-but-not-
  implemented, and implemented-but-not-documented.
- Also cross-checks both sets against the object's live describe() and
  flags anything that isn't a real field at all, as its own top-priority
  category (a typo/removed/never-deployed field would otherwise only show
  up as an ordinary imbalance). Live-tested against the existing example
  transform (`010_account_load.sql`) and genuinely caught a real,
  pre-existing issue: it references `Legacy_Id__c`, a field that doesn't
  actually exist on this org (only `MigrationID__c` was ever deployed).

Auto-mapping into this doc (source→target suggestions) is now built — see
#10 below.

## 4. Solution document generator — BUILT (`solution_doc.py`)

`python cli.py generate-solution-doc <output.docx> <Object> [<Object> ...]`:
auto-drafts a migration solution/design Word document from data this
framework already has -- load-order analysis (#2), a filled-in mapping doc
(#3, optional via `--mapping-path`), and profiling data (#7) -- instead of
writing one by hand for every project. Sections: what's being built (the
object list, in load order), how it's being done (SQL-centric methodology,
in plain language -- replicate/transform/load, fingerprint-based result
mapping, sort/dedupe before load), a load-order table (flagging self-
references and unresolved cycles), one subsection per object (source
table, row count, field-mapping status, profiling summary), and an
optional appendix (`--appendix`) with the full field-by-field mapping
detail.

Load order is re-analyzed fresh on every run (cheap, describe()-only) so
it's never stale -- unlike profiling and mapping, which are deliberately
separate, more expensive steps the user controls, not auto-triggered here.

**No binary template is checked into git.** The default document is built
entirely from Python (`_build_default_docx` in `solution_doc.py`) --
reviewable, diffable content, the same principle auto_mapper.py's
thesaurus follows (git is the source of truth, not an opaque generated
artifact). A data architect at a different company who wants their own
branding doesn't need a code change: `--template <custom.docx>` renders
their own Word document instead, built with `docxtpl` (Jinja2 tags typed
into a real Word doc, styled however they like) against the identical
context dict the default path uses. If no template is given, falls back
to the default -- exactly the requirement that shaped this design (every
data architect has different requirements/branding; ship a working
default, let anyone override it without touching code).

Tested end to end: default template (cover page, all 5 sections, appendix)
against `Account` with a real auto-mapped sheet; a hand-built custom
`docxtpl`-tagged template rendering the same context correctly; and the
graceful-degradation paths (no `--mapping-path` given, no profiling data
for an object) -- both report the gap in plain language in the document
itself rather than erroring or silently omitting the section.

## 5. Org metadata risk analyzer — BUILT (`risk_analyzer.py`)

`python cli.py analyze-org-risk <Object> [<Object> ...] [--mapping-path <xlsx>]`:
cross-references the objects a migration touches against the target org's
*live* automation metadata — active validation rules, Apex triggers,
record-triggered Flows, legacy Workflow Rules, and approval processes —
before `bulkops` runs for real, instead of finding out from an unexplained
rejection or a cascading side effect.

**Scope, stated plainly** (the module docstring says the same thing):
this is an **object-level automation inventory**, not a field-level
formula parser. Reliably determining which specific fields a validation
rule's formula or a Flow's condition logic references would need either
brittle text-scanning of formula strings, or a much heavier Metadata API
retrieval per Flow — deferred, the same way `auto_mapper.py` deferred its
data-sampling "layer 4" until real usage shows it's needed. One concrete,
honest field-level signal *is* included cheaply, though: an active
validation rule's `ErrorDisplayField` is cross-referenced against
whichever target fields are actually being migrated (`--mapping-path`,
reading `Migrate Data == Yes` rows) and flagged as a **direct hit** — a
real signal using data already queryable, without pretending to parse
formula logic.

**Two Salesforce API surfaces, mixed up would fail silently rather than
error** — worth its own callout since this org runs a post-training-cutoff
API version and CLAUDE.md says not to trust stale assumptions here.
Verified live against a real org before shipping, not just read off old
docs:
- **Tooling API** (`sf.toolingexecute`): `ValidationRule`, `ApexTrigger`,
  `WorkflowRule` — all fail with `INVALID_TYPE` if queried through the
  standard REST API instead.
- **Standard REST Query API** (`sf.query`): `ProcessDefinition` (approval
  processes) and `FlowDefinitionView` — the latter is what actually makes
  "which Flows are record-triggered on this object" answerable at all
  (`TriggerObjectOrEventLabel`/`TriggerType` columns), which
  `docs/SOQL_QUERY_LIBRARY.md`'s older unfiltered `Flow` query couldn't do.
  Discovered `ProcessDefinition` is standard-API-queryable (not Tooling)
  by testing it directly after `ValidationRule`/`ApexTrigger`/
  `WorkflowRule` all confirmed Tooling-only — the two APIs were mixed
  within what the roadmap idea originally described as one undifferentiated
  "automation metadata" query surface.

Each per-object check is wrapped individually so one failing metadata
query (e.g. an API surface behaving differently on some org edition)
surfaces as a warning in the report rather than crashing the whole
analysis for every other object. Results also land in
`dbo.ObjectAutomationRisk` for later reference, same DELETE-then-INSERT-
per-object pattern as `dbo.FieldProfile`/`dbo.AutoMapSuggestions`.

Tested live against a real org: `Order` correctly surfaced its one active
record-triggered Flow (found via the org-wide `FlowDefinitionView` query
returning 128 real flows, then confirmed the `TriggerObjectOrEventLabel`
filter narrows correctly); `ApexTrigger`'s `EntityDefinition.QualifiedApiName`
filter was confirmed against real installed-package triggers. The
direct-hit cross-reference logic itself was verified with a monkeypatched
validation-rule list (this dev org has none active to test against
naturally) — confirmed inactive rules are excluded from the active count,
and only the field genuinely in scope is flagged as a direct hit.

**Bug found and fixed in a later repo-review pass**: `ValidationRule` rows
in `dbo.ObjectAutomationRisk` were getting the rule's opaque Salesforce
`Id` as `ItemName` (e.g. `03d...`), not anything human-readable — the
original SOQL never selected a name field. Confirmed `ValidationName` is
a real, queryable Tooling API field (verified live), added it to the
query, and used it as `ItemName` and in the CLI's per-rule console output.

**Deferred, not built**: `pandera`/`great_expectations`-style declarative
data-quality rules ("this field must be non-null," "must match regex X")
as a complement to `profiling.py`'s stats. Related in spirit but a
different kind of check (data content vs. org automation) — worth
revisiting as its own item if profiling's existing population/distinct-
value stats prove insufficient in practice.

## 6. Mock/demo data generation — Mockaroo integration BUILT and working (`mock_data.py`)

Three possible data-generation backends were scoped for this item;
Mockaroo is the only one built so far, and it's fully functional, not
partial — tested live end to end (schema derived from describe(), real
mock rows generated via Mockaroo's API, loaded into a mirror-DB table),
with three real bugs found and fixed along the way (a nonexistent
Mockaroo type name, a missing phone/email/url mapping, and a numeric
overflow on tightly-scaled decimal columns). Snowfakery and Faker (below)
are separate, unstarted ideas for *additional* backends, not gaps in the
Mockaroo path itself.

`python cli.py generate-mock-data <Object> --count N`:
- Derives a mock schema from the object's describe() — only createable
  fields (reference/multipicklist/base64/encryptedstring have no reasonable
  mock mapping and are skipped + reported, not silently dropped), picklists
  use their real valid values rather than random text.
- Calls Mockaroo's API (needs `MOCKAROO_API_KEY` in `.env` — free tier is
  200 requests/day, up to 5,000 records/request) and loads the result into
  `<Object>_Mock` in the mirror DB.
- Not yet wired into `bulkops` — loading `<Object>_Mock` into a sandbox org
  is a manual next step (build a `*_Load` table from it like any other
  transform), not automatic.
- **Deliberately skipped, by explicit policy, not just missing mappings**:
  - **Data.com-branded fields** (`Jigsaw` — labeled "Data.com Key" in
    describe() itself, `JigsawCompanyId`, `CleanStatus`) — this framework
    doesn't migrate Data.com data, and `Jigsaw` specifically has a real
    uniqueness constraint that generic mock text can collide with (found
    live during an end-to-end test: 5 of 100 mock Account inserts failed
    on `DUPLICATE_VALUE:...:Jigsaw` against pre-existing org records).
    Identified via each field's own describe() label, not name-guessing,
    per hard rule 5 — other D&B/firmographic-looking fields on Account
    (`DunsNumber`, `NaicsCode`, `Sic`, `Tradestyle`, etc.) have generic
    labels, aren't Data.com-branded, and are still mocked normally.
  - **Geolocation subfields** (`BillingLatitude`/`BillingLongitude`/
    `ShippingLatitude`/`ShippingLongitude`) — rarely populated by clients
    in practice, not worth reaching for Mockaroo's dedicated Latitude/
    Longitude generator types just to fill them. (These were originally
    mapped to a generic Number type, which produced values like `603.39`
    outside the real -90..90/-180..180 range and failed every row with
    `NUMBER_OUTSIDE_VALID_RANGE` the first time this was tested live —
    fixed forward by skipping the fields entirely rather than chasing a
    more "realistic" generator, per direct guidance: keep mock data to
    the basics, not a value in every field just to prove it can be done.)

**Snowfakery integration — BUILT (`snowfakery_data.py`)**: the
relationship-aware second backend, for generating e.g. 10 mock Accounts
each with 3 real Contacts that actually reference those specific
Accounts, instead of independently random rows per object.
`python cli.py generate-related-mock-data <Object> [<Object> ...] --count
NAME=N [--count NAME=N ...]` (or `NAME=N-M` for a randomized per-parent
count via Snowfakery's own `random_number()` — e.g. `Contact=1-2` for
"1 or 2 Contacts per parent", `Opportunity=0-1` for "roughly half the
parents get one"; a statistical split, not a guaranteed exact percentage
— confirmed live generating 100 Accounts / ~157 Contacts / 79
Opportunities):
- **Reuses this framework's own load-order dependency graph**
  (`load_order.build_dependency_edges`/`compute_load_order`) to decide
  which object nests inside which in the generated recipe, instead of
  re-deriving relationships from `describe()` a second time. Unresolved
  circular dependencies among the requested objects raise a clear error
  (same honesty `analyze-load-order` already has about cycles) rather
  than guessing; self-referencing fields (e.g. `Account.ParentId`) are
  skipped and reported, same two-pass-load gap already documented
  elsewhere in this framework.
- **An object with more than one in-scope parent** (two lookups to
  objects both in the requested set) gets its *primary* parent chosen as
  its **deepest** in-scope parent (highest load-order level, alphabetical
  tie-break), nested via real containment. Confirmed live: a nested
  `reference: <Object>` resolves up the *entire* ancestor chain, not just
  the immediate parent — so any additional parent that's already an
  ancestor of the chosen primary parent (the common "grandparent" case,
  e.g. `Case` having both `Account` and `Contact` in scope, where
  `Account` is already `Contact`'s own parent) gets an **exact** nested
  `reference:` too, not a random guess. Verified against a real three-
  object chain (`Account`→`Contact`→`Case`, 3/2/2 counts): all 12 Cases'
  Account reference matched their own Contact's Account exactly, checked
  via a live SQL join. Only a genuinely unrelated second parent (not an
  ancestor of the chosen primary — two objects with no real hierarchical
  relationship between them) falls back to Snowfakery's
  `random_reference`, which samples the *whole* object pool with no way
  to scope it to "only rows under the same primary parent" — a real,
  disclosed limitation in that specific case, not the common one. The
  CLI reports which kind each additional parent got (`exactly
  references`/`randomly references`), so this is never silently picked.
- **Auto-generates a starter YAML recipe**, written to `_stage/` for
  review or hand-editing (same "reviewable starting point" pattern as
  `generate-mapping-doc`) — not a hand-authored-recipe-only tool. Field
  mapping mirrors `mock_data.py`'s `_mockaroo_field` approach but targets
  Snowfakery's `fake:`/`random_choice:` syntax, and reuses the *exact
  same* Data.com/Latitude-Longitude skip policy `mock_data.py` established
  (imported directly, not duplicated), so both backends agree on scope.
- **Loads into `<Object>_Mock`** — same table-naming convention as the
  single-object path, via pandas (Snowfakery's JSON output, not its own
  SQL writer), reusing the same length-truncation logic (extracted into
  `mock_data.truncate_to_field_lengths`, shared by both backends rather
  than duplicated). A child's parent linkage is a synthetic
  `_ParentMockRef` column (Snowfakery's own internal row id, not a real
  Salesforce Id, since none exist yet) — building the real `*_Load`
  transform, including assigning an actual unique migration key, is still
  a manual next step, the same boundary the single-object backend
  already documents.

**Real syntax specifics confirmed live** (Snowfakery 4.2, not assumed
from docs alone) that shaped the implementation: a parameterized fake
value is `fake.RandomInt: {min: 0, max: 1000}` (dotted key), not
`fake: {RandomInt: {...}}`, which raises `DataGenNameError`; a child
object nested under a parent's `fields:` key causes the *parent's own*
record in Snowfakery's flat JSON output to get a spurious field named
after the nesting key holding just the child count (not a list) — this
implementation always prefixes nesting keys `_children_<ChildObject>` so
they're trivially droppable rather than mistaken for a real field.

**Found and fixed one real bug during end-to-end testing**: Snowfakery's
combined JSON output merges every requested object type's columns into
one flat array (NaN-filled per row where irrelevant to that row's actual
object type). The first implementation attempt filtered each object's
columns by "does this name exist anywhere on this object's own
describe()" — which let Account's `Name`/`Type` values leak into
`Contact_Mock`, since those names coincidentally also exist (non-
createable) on Contact's own describe(). Fixed by threading the exact
field list `build_recipe()` actually generated for each object through to
the loading step, rather than re-deriving "does this name exist on this
object at all" a second, less precise way.

Tested live end to end against a real org: `Account`/`Contact` (5
Accounts, 2 Contacts each) — confirmed `Account_Mock` got 5 rows,
`Contact_Mock` got 10, every `Contact_Mock` row's `_ParentMockRef`
resolved to one of the 5 real `Account_Mock` rows (verified via a live
`LEFT JOIN ... GROUP BY` count), and no cross-object column leakage
after the fix above. Also confirmed the missing-`--count` validation
raises clearly rather than silently defaulting. A follow-up three-object
chain test (`Account`/`Contact`/`Case`, 3/2/2 counts — `Case` has both
`Account` and `Contact` in scope) is what surfaced the `random_reference`
scoping gap in the first place (a Case's Account reference didn't match
its own Contact's Account) and confirmed the ancestor-chain fix above:
all 12 generated Cases' Account reference matched their own Contact's
Account exactly after nesting `Case` under `Contact` instead of `Account`.

**Found and fixed three more real bugs via a full end-to-end dogfood run**
(bootstrap-project through a live `bulkops` load, not a synthetic test):
Snowfakery's combined JSON output unions every requested object type's
columns into one flat DataFrame, and `run_recipe()`'s own column-keeping
logic checked only "is this column present after filtering to this
object's rows" — which doesn't drop columns, so it kept ANY
`_SecondaryParentRef_<X>`/`_ParentType` column present anywhere in the
merged data, not just the ones this specific object actually has. A
polymorphic child's (`Task`) own cohort-only columns leaked into a plain
child (`Contact_Mock`) as entirely-NULL columns. Fixed by threading
`build_recipe()`'s own `primary_parent`/`secondary_exact_parents`/
`secondary_random_parents`/`polymorphic_children` return values through to
`run_recipe()`, so each object's bookkeeping columns are computed from
real recipe structure, not column presence. Two knock-on effects of that
same union: (1) an entirely-NULL leaked int column, and separately (2) a
legitimate `_ParentMockRef`/`_SecondaryParentRef_*` value that's NaN for
some OTHER object's rows anywhere in the union, upcasts that WHOLE column
to `float64` even after filtering — e.g. `_ParentMockRef=1` round-trips as
the Python float `1.0`, not the int `1` — which broke mssql's
`fast_executemany` parameter binding against a real `INT` column (`Invalid
character value for cast specification`); fixed by casting these
bookkeeping columns to pandas' nullable `Int64` before insert. (3) A
`datetime`-typed field (e.g. `Contact.EmailBouncedDate`) was still a plain
Python string after `_fix_snowfakery_datetime_strings()`'s separator fix
(that function only reformats the string, never the dtype) — binding a
plain string against a real `DATETIME2` column via `fast_executemany`
breaks the same way, confirmed via a minimal repro; fixed by parsing it to
a genuine, tz-naive pandas `datetime64` column
(`_parse_datetime_fields_to_real_datetime64()`) before insert, since
`sql_dialect.py`'s own `MssqlDialect.normalize_datetime_columns()` is a
documented no-op that assumes exactly that dtype already. All three only
ever surfaced against the real `mssql` backend (SQLite has no strict
column typing to violate) — a genuine argument for occasionally dogfooding
this module against SQL Server directly rather than only via its SQLite
integration tests.

**A fourth real bug, in `bulkops.py` itself, only surfaced once the mock
data actually reached a live `bulkops` insert**: fixing bug (3) above (a
real `datetime64` column, not a string, so mssql's `fast_executemany`
would accept it) created a genuine regression on the *outbound* side —
`bulk_op()`'s own `payload.to_csv(csv_path, index=False)` had no datetime
formatting at all, so a real `datetime64` column read back from SQL Server
serialized via pandas' own default (space-separated, no `T`) straight into
the Bulk API CSV, which Salesforce's XSD dateTime parser rejected on every
submitted row (`Contact.EmailBouncedDate` — "is not a valid value for the
type xsd:dateTime"). This is a pre-existing gap in `bulk_op()`, not
specific to Snowfakery — any load table with a genuine `datetime`/
`datetime2` source column, from any project, would hit the same failure;
the Snowfakery path just exposed it for the first time. Fixed by
reformatting any `datetime64`-dtype column to the XSD `T`-separated string
right before `to_csv()`, using the exact same convention
`sql_dialect.SqliteDialect.normalize_datetime_columns()` already uses on
the inbound side.

That fix then surfaced a **second, pre-existing and already-documented**
gap in `bulk_op()`'s own docstring (Hard Rule 4, fingerprint result
mapping): the default fingerprint uses every `sent` column, and "a single
echoed-back column that Salesforce reformats, e.g. a datetime field,
otherwise breaks matching for the whole row." Confirmed live: the first
Contact insert attempt (before the CSV fix) failed all 8 rows uniformly,
and fingerprint matching worked fine (failures apparently echo the
submitted value back verbatim). Once the CSV fix let the same 8 rows
actually succeed on retry, **every** row's fingerprint failed to match
(`succeeded: 0, failed: 0` reported, though all 8 real Contacts were
confirmed created live) — Salesforce evidently echoes a *successful*
row's datetime field back reformatted (e.g. with milliseconds/`Z`), unlike
a failed one. `cli.py bulkops` already has the documented escape hatch for
exactly this (`--fingerprint-columns`, "the migration key column alone is
normally the safest choice") — used for the remaining Opportunity/Task
loads in this same dogfood run, both of which succeeded cleanly first
try. Worth calling out here since this is genuinely easy to trip on the
first time a load table sends any datetime field at all, not just under
Snowfakery: **any object with a sent datetime-typed field should pass
`--fingerprint-columns <migration key>` up front**, not just after hitting
this the hard way.

`Faker` (the library Snowfakery itself wraps) is a lower-priority
alternative worth knowing about too as a *standalone* backend — no API
key, no rate limit, works fully offline — for whenever Mockaroo's
200-requests/day free tier becomes the actual bottleneck rather than a
theoretical one. Not pursued now since Snowfakery already provides Faker-
backed generation with relationships, which is the harder problem this
item actually needed solved.

**Reviewed CumulusCI's own data tooling directly**
(cumulusci.readthedocs.io/en/stable/data.html) to check for anything
worth adding here — CumulusCI is Snowfakery's own origin project, so
worth a direct look, not assumed irrelevant. Its `extract_dataset`/
`load_dataset`/mapping-YAML system solves a similar-sounding problem
(org-to-org data movement, upsert keys, cycle-aware lookups via an
`after` directive) but is a genuinely different architecture — YAML-
driven mapping steps with SQL as a mostly-opaque intermediate, not this
framework's foundational "T-SQL transforms are the reviewable source of
truth" identity (`CLAUDE.md`). Adopting it wholesale would be the same
kind of "second parallel mode" question already flagged for a different
backend in #28, not an incremental improvement — not pursued for that
reason. Two narrower ideas worth keeping on the radar without adopting
the whole system are scoped as their own items: target-count-driven
generation (#31, mirroring CumulusCI's `generate_and_load_from_yaml`)
and WHERE-clause bulk test-data cleanup (#32, mirroring `delete_data`).
CumulusCI has no Data Cloud/DSO-specific capability at all, so it doesn't
change anything about #22's local DSO ingestion gap — Snowfakery itself
(already built here, independent of CumulusCI) remains the natural
mock-data source once that item's API research unblocks. Scratch-org
lifecycle (CumulusCI's `dev_org`/`qa_org` flows auto-loading sample data)
is scoped separately as #33, since it's a new capability area for this
framework, not an extension of mock-data generation itself.

## 7. Data profiling toolset — BUILT (`profiling.py`)

Problem: before deciding what to migrate, you need field-level stats —
population counts, min/max, distinct counts, null/blank breakdowns, and
picklist value distributions — the standard best-practice profiling pass.
Past practice was a DBA-built SQL tool (`sys.tables`/`sys.columns`-driven)
for source-system tables, plus a separate tool used directly against
Salesforce directly, with results reviewed in Excel.

`python cli.py profile-salesforce <Object>` / `profile-sql-table <Table>`:
- **Salesforce path**: describe()-driven, batched aggregate SOQL queries
  (population count, distinct count, min/max, picklist/boolean value
  distributions). Divide-and-conquer retry isolates a single field that
  breaks a batch (SOQL's aggregate restrictions are field/org-specific and
  not fully predictable up front — e.g. `IsDeleted` on this org rejects
  `COUNT()` outright, and boolean fields return 0 for a `!= null` check
  even though they're never actually null). Long-text/binary field types
  are skipped entirely — SOQL has no aggregate path for them at all.
- **SQL table path**: one dynamic aggregate query over `INFORMATION_SCHEMA.
  COLUMNS`, works on any table regardless of origin (replicated Salesforce
  mirror table or a legacy source table loaded some other way) — this is
  the "common thread" that makes one profiling engine cover both cases.
  Adds blank-vs-null distinction and min/max text length, which aren't
  available from the SOQL side.
- Both write to shared `dbo.FieldProfile` / `dbo.FieldProfileValues`
  tables (re-profiling an object replaces only that object's prior rows).
- `python cli.py export-profile-excel <path.xlsx>` — one sheet per object
  plus a companion `_Values` sheet for picklist/low-cardinality
  distributions, for reviewing what's worth migrating.

## 8. Ad hoc Query Tool — BUILT (`query_tool.py`)

The first item from the "Data Architect toolbelt" discussion — replacing
the daily need for an external ad hoc query tool with something built into
this framework.

`python cli.py query "<SOQL>"`:
- Runs via the REST Query API (`sf.query`/`sf.query_all`), not Bulk API —
  built for quick lookups/troubleshooting, not large extracts (`replicate`
  is for that).
- Flattens relationship fields (e.g. `Account.Name` on a Contact query) to
  dotted keys for display.
- Defaults to a single page with a clear "not all records fetched" notice
  if there's more; `--all` paginates everything via `query_all()`.
- Results print to console, or export via `--csv`/`--excel`.
- Scoped to CRM objects for now — Data Cloud/D360 objects use a genuinely
  different query surface (Data Model Objects via the Data Cloud Query
  API, not standard SOQL) and aren't supported yet; a possible phase 2.

## 9. Console output polish — BUILT (`rich` in `cli.py`)

`query` and `profile-salesforce`/`profile-sql-table` render results as
`rich` tables instead of raw pandas `to_string()` output (which silently
truncated wide values) or, for profile, no data at all (previously just a
summary count). Long values wrap onto multiple lines rather than getting
cut off. The profile preview is deliberately narrow — field/type/populated
%/distinct count, the four columns that matter for an at-a-glance "is this
worth migrating" call — full detail stays in `dbo.FieldProfile`/
`FieldProfileValues` and `export-profile-excel`, not crammed into a
console table.

## 10. Auto-mapping — BUILT (`auto_mapper.py`)

Suggests source→target field mappings and writes them into an existing
mapping doc's Target block/Notes/Migrate Data columns (`python cli.py
auto-map <Object> <mapping.xlsx> <SourceTable>`). Designed around a few
hard requirements, not just "match names":

- **Profiling is a hard prerequisite, not just a recommended order.**
  `ensure_source_profiled()` raises a clear error if the source table has
  no `dbo.FieldProfile` rows — auto-mapping without knowing how populated a
  field actually is would be guessing at half the picture. A field can
  match a target field's name perfectly and still be useless to migrate if
  the source barely captured it.
- **Layered matching, most-confident first**: (1) exact/normalized name
  match, (2) a synonym thesaurus, (3) fuzzy string matching
  (`difflib.SequenceMatcher`, threshold 0.82) as a conservative fallback —
  deliberately tuned to leave genuinely ambiguous fields unmatched rather
  than force a low-confidence guess. A future (4) — data-aware reasoning
  that actually samples row values, not just metadata — is deferred until
  real usage shows what layers 1–3 miss.
- **Thesaurus lives in git, not SQL Server**: `reference/field_synonyms.json`
  is the versioned, always-committed source of truth (concept keys like
  `BillingPostalCode` mapped to aliases like `zip`/`postal`/`postcode`).
  SQL Server (`dbo.SourceRegistry`, `dbo.AutoMapSuggestions`) is a deploy/
  execution target for per-project results only — mirrors the same
  git-is-truth principle `sql/transformations/*.sql` already follows.
  Every human correction during a real mapping session is meant to become
  a new alias here, so the thesaurus improves across migrations instead of
  staying static.
- **Data-quality gate overrides a clean name match.** Every suggestion —
  matched or not — is run through the existing profiling data
  (`PopulatedPct`, `DistinctCount`). Below 5% populated: "No". Below 20%:
  "Review". 100% populated but only one distinct value (e.g. a constant
  flag column): "No", with the actual value quoted in the rationale. A
  clean thesaurus match on a field that's 2% populated still gets
  downgraded — the name match doesn't get the final word.
- **Every suggestion carries a rationale**, not just a yes/no — the point
  is to make review "scan and approve," not "re-research from scratch."
  A field with no name match but also degenerate data reports both facts
  together (e.g. *"No confident match found... Also: Only 100.0%
  populated, and every populated row has the same value ('X')..."*)
  rather than just the unhelpful "no match."
- **Never overwrites a human decision** — `apply_auto_map_suggestions()` in
  `mapping_doc.py` skips any row where the mapping doc's Target Field API
  is already filled in.

Tested against two cases: `Account_Mock` → `Account` (trivial — that
mock table's schema is derived directly from Account's own describe(), so
every match is exact) and a purpose-built `LegacyCRM_Companies` test table
with deliberately different naming (`co_name`, `zip`, `tel`,
`yearly_revenue`, `staff_count`, `weird_flag_9`) to actually exercise the
thesaurus and fuzzy layers. Found and fixed three real bugs during that
testing, all confirmed via live re-test against SQL Server:
1. The "single distinct value" rationale hardcoded "100% populated"
   regardless of the field's real population rate.
2. The most-common-value lookup picked up `FieldProfileValues`'s NULL
   group instead of the actual repeated value (SQL Server's `GROUP BY`
   treats NULL as its own group) — surfaced as the misleading literal
   string `"None"` in a rationale until fixed by explicitly excluding NULL.
3. Unmatched fields never ran the data-quality gate at all, so a field
   with no name match *and* junk data (constant-value `weird_flag_9`) only
   reported "no match," missing the more useful "no match, and also not
   worth migrating" signal the user's original design ask called for.

## 11. Bulk load pre-flight check + retry helper — BUILT (`bulkops.py`)

Two additions to `bulk_op()`/`bulkops`, picked over the bigger, riskier #25/
#26 UI work as the next concrete step -- both slot directly into the load
workflow every migration already goes through, no new subsystem needed.

**Pre-flight check** (the rebuild-instead-of-port item from #1):
`_preflight_check()` validates every column about to be sent against the
target object's *live* `describe()`, before `bulk_op()` ever calls the Bulk
API:
- **Not a real field** on the target object, or **not writable** for the
  operation (`createable` for insert, `updateable` for update/upsert) --
  either one raises a `ValueError` and aborts the whole call. Salesforce
  would reject it for the identical reason anyway, just after spending a
  real batch (and the 10-minute-per-batch window) to find out.
- **Required field not sent** (insert only) -- reported as a warning in the
  result dict (`preflight_warnings`), not a hard stop, since automation
  could still default it and this pre-flight has no way to know that.
- Schema/permission check only, not a data-content one -- duplicate/NULL
  migration keys are still `CheckLoadTableDuplicateKeys`' job (hard rule 7).

Verified live against a real org (read-only `describe()` calls, no actual
Bulk API call needed to test the check itself): a deliberately typo'd field
and a non-writable field (`CreatedDate` on update) were both caught
correctly, and a genuinely bad load table (`insert` with an unknown column)
was confirmed to raise and abort **before** `bulk_op()` ever reached
`sf.bulk2`, not just report a bad result afterward.

**Retry helper**: `bulkops-retry <table>` (`build_retry_table()`) copies
only the failed rows (`Error` populated) from a load table or its
`_Result` table into a fresh `<table>_Retry` table -- the pattern already
named as a gap in `docs/MIGRATION_PLAYBOOK.md` §6. Deliberately does *not*
resubmit anything itself; that's a separate, normally-confirmed `bulkops`
call against the new table, same as any other load. Tested against a
synthetic mixed-result table (2 succeeded, 1 failed) -- correctly copied
only the failed row; a table with an `Error` column but zero failures
reports "nothing to retry" instead of creating an empty table; a table
that's never been through `bulkops` at all (no `Error` column) raises a
clear error rather than silently copying everything.

**Delete by external id** (`bulkops <Object> delete <table> --external-id <field>`):
Bulk API 2.0's delete operation only ever accepts the real Salesforce Id —
confirmed against Salesforce's own docs ("bulk deletion requests can
include only the Id field"), unlike update/upsert, which do accept an
external id via `externalIdFieldName`. So this doesn't send the external
id to the API directly; it resolves those values to real Ids via a SOQL
query first (`_resolve_external_ids_to_sf_id`, chunked at 200 values per
query), then runs a normal Id-based delete against whatever resolved. A
value with no matching org record never reaches the API at all (nothing
to delete) — it gets a clear, locally-generated "no matching record found"
error written back on that row, the same shape as any other failure,
rather than being silently dropped or erroring out the whole batch.
Update/upsert already supported external id-based matching natively
(that's what `upsert` *is*) — this closes the one real gap, which was
delete specifically.

Tested live: the SOQL resolution step itself, confirmed correct via real
(read-only) `Account` records — resolved every real value to its actual
Id and correctly omitted a deliberately fake one. The all-unresolved path
was verified end to end against a synthetic load table where every
external id value was fake: confirmed **zero live Bulk API calls were
made** (the code path skips calling `sf.bulk2` entirely when nothing
resolved) and both rows got the clear local error written back correctly.
The mixed resolved/unresolved case was **not** tested live, since that
would require an actual delete against a real org record — deliberately
not run "to test," per hard rule 2; the resolved-rows and unresolved-rows
code paths were each verified independently instead (resolution mapping,
and the all-skip writeback path), and combine via ordinary boolean
row filtering.

## 12. Parquet file import — BUILT (`parquet_import.py`)

`python cli.py import-parquet <path.parquet> <table> [--append]`: imports
a Parquet file into a typed SQL Server table in the mirror DB — a second
entry point alongside `replicate.py`'s org-sourced path for getting source
data into SQL Server, for the case where the source is a columnar file
rather than a live org (`docs/MIGRATION_PLAYBOOK.md`'s "Data Extraction
from Source Systems" already covers flat files/JSON generally; this adds
Parquet specifically as its own typed path).

Unlike `replicate.py`'s Salesforce path — Bulk API 2.0 always returns text
CSV, so every value needs coercing back to a native type (see
`type_map.py`'s `typed_value_coercers`) — Parquet is already a typed
columnar format. `pyarrow` hands back real int/float/datetime values
directly, so there's no coercion step here, just a schema-inference-to-
SQL-Server-DDL step (`_arrow_type_to_sql`), mirroring `type_map.py`'s
`sf_type_to_sql` for the Salesforce side. Reads via
`pyarrow.parquet.ParquetFile.iter_batches()` rather than
`pd.read_parquet()` in one call, so a large file doesn't need to fit in
memory at once — the same chunked-append pattern `replicate.py` already
uses. Drops/recreates the target table by default; `--append` adds rows
to an existing, schema-compatible table instead (e.g. loading a second
file into the same table).

Tested end to end against a synthetic Parquet file covering string,
float, int, boolean, date, and datetime columns with NULLs mixed in:
confirmed every column landed as the correct SQL Server type (`BIGINT`
for a 64-bit int column, `FLOAT`, `BIT`, `DATE`, `DATETIME2`, `NVARCHAR
(MAX)`) with NULLs preserved correctly, and confirmed `--append` adds
rows to the existing table instead of dropping it.

New dependency: `pyarrow` (Parquet read support).

**Not built**: the imported table still needs the same
profiling → mapping → transform pipeline as any other source table before
it's ready for `bulkops` — this only solves getting the file's data into
SQL Server, not any downstream step.

## 13. Email Deliverability attestation gate — BUILT (`bulkops.py`, CLAUDE.md hard rule 9)

Requested directly: a permanent check before any load that could trigger
outbound email externally, stopping if deliverability allows it, warning
and continuing if it's internal-only.

**Research finding that reshaped this before any code was written**:
Salesforce has no supported API to *read* the org's Email Deliverability
setting. Confirmed two ways, not assumed: retrieved
`EmailAdministrationSettings` live via `sf project retrieve` against this
framework's own connected org (19 real settings came back, none of them
deliverability-related), and cross-checked Salesforce's own Metadata API
field reference for that type (no such field documented either). The
strongest corroborating signal: the only tool found that can even *set*
this value programmatically (`sfdx-deliverability-access`, a community
plugin) does it by driving a **headless browser against the Setup UI** —
exactly the kind of fragile screen-scraping this framework's whole
approach avoids, and a strong sign no real API exists to automate around.

Given that, an automated "validate and stop" check as originally
described isn't honestly buildable. Built instead, with the user's
explicit sign-off on this specific shape: a **required human attestation**
built into `bulk_op()` for `insert`/`upsert` (the operations that can
create new records and trigger real outbound email) —
`--email-deliverability no-access|system-email-only|all-email` must be
passed, based on someone actually having checked Setup first; omitting it
raises before the API is ever touched. `all-email` requires an additional
`--confirm-external-email-risk`, since that's the one state that can
genuinely send real mail to real people — a deliberate override, not a
default. The confirmed value is echoed back in the load's own result
output either way, so "internal-only confirmed, continuing" or "external
email risk explicitly accepted" is always visible in what the load
actually reported, not just implied.

No interactive terminal prompt was used deliberately — `bulkops` runs as a
Bash tool call from Claude Code, which isn't a real interactive terminal,
so a blocking `input()`/`click.prompt()` call risked hanging rather than
actually gating anything. A required, explicit CLI flag achieves the same
"can't proceed without a human having looked" guarantee without that risk.

Tested: all six logic paths verified directly (missing value raises,
`all-email` without confirm raises, `all-email` with confirm passes,
`system-email-only` passes without confirm, update/delete are correctly
exempt, an invalid value raises) — and confirmed live in the full
`bulk_op()` pipeline that the check fires and raises before the function
even attempts to read the SQL Server load table, let alone call the API.

## 14. Load activity logging + analytics — logging BUILT (`bulkops.py`), analytics not built

Problem: right now a `bulkops` run's outcome lives only in the console
transcript and the load table's own `Id`/`Error` columns — there's no
durable, queryable record of *what ran, when, and how it performed*
across a whole project's worth of loads.

**Built, opt-in only — the same configure-once, per-database logging
convention established commercial migration tools use** (requested in
exactly those terms): never on by default, and never a per-call flag
either — an architect turns it on once per schema
(`enable-bulkops-logging --schema <schema>`),
which creates `<schema>.BulkOpsLog`. From then on, every `bulk_op()` call
against that schema logs itself automatically: action
(insert/update/upsert/delete), object, source table, record counts
(submitted/succeeded/failed/ambiguous/external-id-not-found), job count
(number of Bulk API 2.0 jobs the file was split into), the Email
Deliverability attestation (#13) if applicable, start/end/duration, and
the OS user who ran it. `disable-bulkops-logging` drops the table (and
its history) for that schema.

Two deliberate design choices, both directly requested:
- **Per-schema, not per-database.** This framework only ever connects to
  one physical database (`SF_Migration`, hard rule 1) but already uses
  `--schema` to separate logical areas (source/staging/dbo, same concept
  every other generated table in this framework already uses) — so
  `source` and `staging` schemas can each independently have logging on
  or off, matching the "source could have a logging table, staging could
  have a logging table" ask without opening a second physical database
  connection anywhere in the codebase.
- **Presence-gated, not flag-gated.** Whether `<schema>.BulkOpsLog`
  exists *is* the on/off switch — the same pattern `bulk_op()` already
  uses for the `[Sort]` column and `key_column` writeback. A logging
  failure never fails the underlying load (the real Salesforce operation
  and its writeback have already completed by the time logging runs);
  it's surfaced as `logging_error` in the result instead of silently
  swallowed or allowed to undo a real result.

Deliberately never logs `query_tool.py` reads — scoped strictly to
`bulkops` writes (insert/update/upsert/delete), per the original ask.

**Tested live end to end, real org**: 100 Mockaroo-generated mock Accounts
(`generate-mock-data Account --count 100`) taken through the full standard
workflow (profile → mapping doc → auto-map → describe-confirmed transform
→ dupe-check) and inserted into a real target org with logging enabled.
Found and fixed two real bugs along the way, neither specific to logging
itself:
1. `mock_data.py`'s generic `double` handling had no special case for
   Geolocation subfields (`BillingLatitude`/`BillingLongitude` etc.) --
   Mockaroo generated values like `603.39`, which Salesforce correctly
   rejected with `NUMBER_OUTSIDE_VALID_RANGE` (real latitude range is -90
   to 90) on all 100 rows the first time this ran. Fixed by mapping
   fields whose name ends in `latitude`/`longitude` to Mockaroo's own
   dedicated `Latitude`/`Longitude` generator types instead of the
   generic precision/scale-based `Number` mapping.
2. `bulkops.py`'s `_fingerprint()` crashed (`TypeError: sequence item ...
   expected str instance, float found`) the first time a real failed-
   records CSV came back with a blank cell in an echoed numeric column --
   `_read_result_csv` reads everything as `dtype=str`, but a genuinely
   empty cell still surfaces as a real NaN float that `.astype(str)`
   alone didn't reliably stringify before the row-wise join. Fixed with
   `.fillna("")` before `.astype(str)`.

After both fixes, a clean re-run inserted 100 fresh mock rows: 95
succeeded, 5 failed on a real, unrelated `DUPLICATE_VALUE` (Jigsaw/
Data.com ID uniqueness) -- confirmed correctly written back into
`Account_Load`'s `Id`/`Error` columns, and confirmed live in the org
(`SELECT COUNT(Id) FROM Account WHERE MigrationID__c LIKE 'MOCKACCT-%'`
returned 95). `dbo.BulkOpsLog` correctly captured one row for the run
(100 submitted / 95 succeeded / 5 failed / 1 job / ~32s duration),
confirming the opt-in logging path works against a real load, not just
the enable/disable DDL path.

**Not built**: the "build actual analytics on top of it" half (trends
across sandbox/UAT/prod runs, which objects are slowest/most
error-prone, batch-time regressions) — deliberately deferred as its own
second step now that the raw log table exists to analyze, not
speculatively built before there's real logged data to analyze.

## 15. Dynamic batch sizing from org metadata review — BUILT (`batch_advisor.py`)

Problem raised directly: Bulk API 2.0 has **zero server-side adaptivity**
— confirmed against the installed `simple-salesforce` source (1.12.9,
matching this repo's own requirements floor) directly, not assumed: it
mechanically splits submitted data and never inspects org automation to
size anything. So the "start heavily-automated objects smaller" common
sense every established migration tool's users eventually learn through
trial and error has to live entirely client-side. What we confirmed
actually exists to build on: `simple_salesforce`'s bulk2 handler exposes
a real `batch_size` parameter on insert/update/upsert/delete (splits the
submitted CSV into that many records per ingest job) and a `concurrency`
parameter defaulting to 1 (serial submission — left untouched here;
exposing parallelism was an explicit non-goal).

**Three layers, in order, each named in the printed rationale rather
than hidden behind a bare number** — the explicit ask was to pass
knowledge to a new data architect, not just compute a value:
1. **Seed knowledge** (`reference/batch_size_heuristics.json`, git-
   tracked and human-curated like `field_synonyms.json`) — exact-name
   seeds for OOTB-heavy objects (`Opportunity`, `OpportunityLineItem`,
   `Case`, `Order`, `CampaignMember`, ...) and managed-package prefix
   seeds (`SBQQ__`, `blng__`, `vlocity_cmt__`, `npsp__`), each with a
   `why` string. The CPQ/Billing "≈50" guidance already in
   `docs/MIGRATION_PLAYBOOK.md`'s batching section became the seed for
   those two prefixes directly — confirmed that guidance's exact wording
   before citing it, not assumed.
2. **This org's own automation** (`dbo.ObjectAutomationRisk`, written by
   `analyze-org-risk` — #5) — active Apex triggers, record-triggered
   Flows, and validation rule counts each step the recommendation down a
   rung past a threshold. If the object was never scanned, the rationale
   says so and suggests running `analyze-org-risk` rather than silently
   skipping the signal.
3. **This project's own load history** (`dbo.BulkOpsLog` — #14, which
   gained `BatchSize`/`BatchSizeSource`/`LockErrorCount` columns for
   this) — a prior run's `UNABLE_TO_LOCK_ROW` errors step the size down;
   consecutive clean runs step it up cautiously. This is the trial-and-
   error feedback loop, automated and remembered instead of re-discovered
   by hand on every project.

All recommendations snap to a **fixed ladder** of 8 sizes (50, 100, 200,
500, 1000, 2000, 5000, 10000) rather than an arbitrary computed number —
directly requested, so a recommendation is always one of a small,
memorable set of comparable values, not something like "743."

**The override/toggle, exactly as requested**: `bulkops --batch-size`
defaults to `auto` (the three-layer recommendation above, rationale
printed before the load runs). An explicit integer is honored verbatim
forever and never second-guessed — a scripted value always wins and
stays, the same hardcode-it-in-the-script norm every established
migration tool's users already follow, just with a smarter starting
point than a blank page. `none` submits one unchunked job (today's
original, pre-#15 behavior) as an explicit escape hatch.

**`suggest-batch-heuristics`** reads this project's own converged load
history and prints candidate `object_seeds` edits for
`reference/batch_size_heuristics.json` — it never writes the file
itself; a human reviews and commits deliberately, the exact same
git-is-truth principle `auto_mapper.py`'s thesaurus workflow already
established. This is the cross-project persistence the user asked for:
what one migration's trial-and-error converges on becomes the next
migration's starting seed, once someone commits it.

**A real bug found via live testing, not assumed**: the first
implementation of the history layer queried `BatchSize`/`LockErrorCount`
unconditionally and crashed with "Invalid column name" against this
project's own pre-existing `dbo.BulkOpsLog` (created before these
columns existed). Fixed by checking column existence first and telling
the architect to re-run `enable-bulkops-logging` to upgrade the table in
place (history preserved) — the same idempotent-upgrade pattern
`enable_bulkops_logging()` itself already uses for its own schema
changes.

**Verified live against a real mirror DB**: seed lookup (`Opportunity` →
200, `SBQQ__Quote__c` → 50 via prefix match, `Account` → the 2000
default with no seed), the automation-risk step-down (synthetic active
Apex trigger + 3 record-triggered Flows: 2000 → 500), the lock-error
step-down (synthetic `UNABLE_TO_LOCK_ROW` history: 500 → 100), the
clean-run step-up (two synthetic clean runs: 500 → 1000), and
`suggest-batch-heuristics` correctly surfacing the converged test
object. All synthetic rows cleaned up afterward.

**Verified live end-to-end against a real org** (`D360_PLAYGROUND`,
mock Account inserts): `--batch-size 3` against 10 rows produced exactly
4 Bulk API jobs (`ceil(10/3)`) and logged `BatchSize=3`/
`BatchSizeSource=static`; the default `auto` mode printed its full
rationale, resolved to 2000, and logged `BatchSizeSource=auto`; a second
clean run correctly stepped the recommendation 2000 → 5000 per the
history rule; `--batch-size none` submitted a single unchunked job.
`dbo.BulkOpsLog`'s `JobCount` column confirmed each mode's actual
chunking behavior, not just the recorded setting. Test Accounts deleted
afterward.

**Not built (explicit v1 non-goals, not gaps)**: no mid-run adaptive
backoff between chunks of the *same* load (a phase-2 idea, worth its own
future item if this proves insufficient); no exposure of Bulk API 2.0's
`concurrency`/parallelism knob; `suggest-batch-heuristics` never writes
the seed file automatically, by design.

## 16. Migration Run Book (manual + programmatic step tracking) — BUILT (`migration_run_book.py`)

Problem raised directly: today, nothing tracks the *human* side of a
migration — every manual and programmatic step taken during a full load
(sandbox, UAT, prod), who did it, start/end/elapsed time, errors hit,
retries done — the actual "recipe" of a migration, not just what a script
did. Explicitly framed as high-stakes ("this is what can make or break a
migration") and as something to track per main full load, not per script.
Unblocked when the user described their real Migration Run Book template directly
(Item/Notes/Person Responsible/Start/End/Total Time for Pre-/Post-Migration;
Script #-Name/Dependency/row counts/errors for Script/Transformations;
critical steps like Email Deliverability colored red) instead of dropping a
file into `_stage/`.

**The recipe structure lives in `docs/MIGRATION_RUN_BOOK_TEMPLATE.md`**, git-tracked
and human-editable directly — deliberately Markdown rather than a
`reference/*.json` tuning file, since a data architect needs to *read* this
structure as much as `migration_run_book.py` needs to parse it (contrast
`mapping_doc.py`'s `_HEADERS`, which are hardcoded Python, not sourced from
a checked-in template). One `## Heading` + one Markdown pipe-table per
section (Pre-Migration, Script / Transformations, Post-Migration); editing
the file changes what every new project's first Migration Run Book tab starts with.

**One continuous worksheet holds one full end-to-end pass** — confirmed
directly against the initial "separate tab per section" idea: "One sheet
should hold everything for a full end to end data load." Multiple **tabs in
the same workbook** track the project's life across passes instead (a
couple of Dev test tabs, then UAT/mock-go-live, then PROD). A new pass is
created by *copying the previous tab's recipe forward* — `add-migration-run-book-pass`
duplicates Item/Script name/Dependency/Critical-flag columns verbatim
(including anything a human added by hand since generation) while blanking
every execution-result column (who, when, errors, row counts) for the fresh
run — "the copy is the recipe, the blank values are the who/when/errors/
rows," in the user's own words.

**Recipe vs. result columns**, the split that drives what copies forward vs.
blanks: Pre-/Post-Migration recipe = `Item`, `Critical`; result = `Notes`,
`Person Responsible`, `Start`, `End`, `Total Time`. Script/Transformation
recipe = `Script # / Name`, `Dependency`; result = everything else. Both
`generate-migration-run-book` and `add-migration-run-book-pass` **refuse to overwrite an
existing tab name** — unlike `mapping_doc.py`'s regenerate-in-place
convention, a Migration Run Book tab holds live, manually-entered operational history
that must never be silently clobbered.

**Auto-fills what's already known, doesn't guess**: `generate-migration-run-book
--objects` populates the Script/Transformation section from `load_order.py`'s
(#2) `dbo.ObjectLoadOrder`/`dbo.ObjectDependency` — load order, and a
`Dependency` cell naming real parent objects or "parallel with" siblings at
the same load level, with self-referencing fields (e.g. `Account.ParentId`)
correctly excluded from that (a real bug found live: an early version
double-counted self-references as bogus duplicate parents of themselves,
e.g. "After: Account, Account" for `Account` itself — fixed by filtering
`child == parent` edges and deduping with a set). Best-effort matches an
existing `sql/transformations/*.sql` filename containing the object name to
prefill `Script # / Name`.

**Explicit scope boundary, from the user's own follow-up message**:
`dbo.BulkOpsLog` (#14) can never see manual steps (there's no API trace of
someone unchecking a Setup toggle) — Pre-/Post-Migration result columns will
*always* need a human filling Person/Start/End/Notes, this isn't a gap to
fix. Tying `BulkOpsLog` data into the Script/Transformation section's result
columns automatically is the explicit next phase, not built now — the
spreadsheet, not the log table, is the enduring single "bigger picture"
across the whole migration.

**A second real bug found via live testing**: the first implementation of
`add_migration_run_book_pass()`'s result-column blanking silently did nothing —
`openpyxl`'s `cell(value=None)` is a no-op indistinguishable from omitting
`value` entirely, so populated Person/Start/End/row-count cells survived
the copy unchanged. Confirmed by populating a tab with real values, copying
it, and finding the values still present; fixed by setting `.value`
directly instead. A related labeling bug (Pre-Migration and Post-Migration
share an identical column list, so section-matching by columns alone always
labeled both "Pre-Migration") was also fixed, using the bold title row
directly above each header row as the reliable section name instead.

**Not built (explicit v1 non-goals)**: no automatic `dbo.BulkOpsLog`
tie-in yet (the stated next phase); "practices on scripts" (dev/test runs
short of a real pass) are deliberately out of scope — only real full loads
against sandbox/UAT/prod get a tab.

**Follow-up: header block with environment/Git/ticket breadcrumbs.**
Feedback on the first build: it was missing an area answering "what is
this, where did it come from, what's it tied to." Every tab now gets a
fixed-height header (rows 1-7, so `add_migration_run_book_pass()` can refresh values
in place without shifting the sections copied below it) — Project, Source/
Target Environment, a Git Repository link, the exact commit/branch this
pass's scripts came from, a link to those scripts at that commit, and
(when configured) a link to the ticket system's project. Hyperlinks are
real (`cell.hyperlink`), not just blue text. Clarified directly that the
ticket link is header-level only — one link to the project, not a per-row
column, since specific-story tickets belong in the SQL comment rule below,
not the spreadsheet.

Git breadcrumbs are pinned at generation/copy time, not just "whatever's
current when someone opens the file": `_git_info()` shells out to
`git remote`/`git rev-parse`, `_github_url()` normalizes an https or SSH
GitHub remote (a non-GitHub host degrades to plain commit-SHA text, no
hyperlink — a known v1 limitation). Matched Script/Transformation rows
also get a real hyperlink to that exact file at the pinned commit.
`add_migration_run_book_pass()` always **recomputes** Commit/Branch and the
Scripts-link to the *current* Git state (each pass records what actually
ran for it, not the original tab's snapshot) and **never** silently
carries Target Environment forward (Dev/UAT/PROD are different Salesforce
orgs) — but Project/Source Environment/Git Repository/ticket link do carry
forward from the source tab unless explicitly overridden, so a later pass
isn't retyping things that don't change. New `TICKET_SYSTEM_LABEL`/
`TICKET_SYSTEM_URL` settings in `config.py`/`.env.example` give a project-
wide default (not a credential — no token, just a base URL/label);
`--ticket-url`/`--ticket-label` override per project.

**A real bug found via live testing**: an early version of the header
write used `openpyxl`'s built-in "value=None means don't touch this cell"
behavior (the same gotcha already found once in this item's build) when
computing hyperlink-only cells, and separately, the fixed-row design was
adopted specifically *because* an early draft that skipped absent header
fields entirely produced a different header height per tab, which would
have silently misaligned `add_migration_run_book_pass()`'s already-copied section
rows on refresh — caught during design, not live, by tracing through what
a variable-height header would do to a fixed-position copy operation.

**New Hard Rule 10** (`CLAUDE.md`): every new file under
`sql/transformations/` must have its ticket reference (JIRA story/bug
key, or whichever system a project actually uses) hardcoded in a header
comment when first built — never invented; ask if one hasn't been given.
This is the per-script, per-story counterpart to the Migration Run Book header's
project-level ticket link.

**Follow-up: rewritten to mirror a real client's migration-status tab —
supersedes the column model described above.** The user pointed at a
real, in-production file (a real client engagement's own tracking
workbook, "PROD Migration Status" tab) and asked the build to mirror it
as closely as possible. Inspecting it directly (structure only — column
names/layout, never its actual content) showed a genuinely different,
better design than the verbally-described one built first:

- **One unified table**, not a different column set per section. A
  single header row — `Stage, Object, Dependency, Status, Critical,
  Person Responsible, Begin Time, End Time, Execution Time, JIRA Ticket
  Link, Notes, Total Records, Success Records, Failed Records, Success
  Percent, Error Details` — covers every phase (`_COLUMNS` in
  `migration_run_book.py`). Phases are marked by a single full-width,
  dark-navy (`0D2C39`)/white-font banner row, matching the real file's
  own styling exactly — the column header itself is never repeated. The
  old per-section `Item`/`Script # / Name` split is gone; `Object` now
  holds the step/task/script name either way (kept as the literal header
  name to match the real file, even though it isn't necessarily a
  Salesforce object API name).
- **Status is a real dropdown** (`Not Started, N/A, In Process, Completed,
  Issue` — the user's own stated list, not the real file's literal
  `Error` value) driven by genuine Excel conditional-formatting rules
  (`openpyxl.formatting.rule.CellIsRule`), not a one-time paint — colors
  update live if a human changes the dropdown later, exactly like the
  real file's own mechanism. Confirmed one exact color match directly
  from the real file's own differential-style XML: `In Process` = pure
  yellow (`FFFF00`). `N/A` = light green (`C6EFCE`), `Completed` = a
  darker green (`375623`), `Issue` = a stronger red (`FF0000`) than
  `Critical`'s existing fill, so the two flags stay visually distinct.
  Both rule sets are over-provisioned to row 1000, matching the real
  file's own `D3:D1062`-style ranges, so rows added later still pick up
  the coloring.
- **A per-row `JIRA Ticket Link` column** was added back — the earlier
  session's "header-level only" decision didn't hold up against the real
  file, which has both a per-row ticket link *and* would benefit from a
  project-level one; both now coexist (header = project, per-row =
  specific story/bug), and `JIRA Ticket Link` is a **recipe** column
  (carried forward on a new pass), not a result.
- **`Begin Time`/`End Time`/`Execution Time` are three separate,
  informally human-entered fields** ("21sec", "11:26", "4 hours" in the
  real file) — the previous `Total Time` Excel formula assumed clean
  datetimes it could subtract; real usage evidence says people don't
  enter them that way, so the formula was dropped in favor of a plain,
  human-entered `Execution Time` field.
- **User decision, kept deliberately un-mirrored**: the real file has no
  separate `Critical` column at all (importance is just called out in
  free-text Notes, e.g. "CRITICAL to be done"). Kept anyway — Critical
  flags ahead-of-time risk; Status = Issue flags something that already
  went wrong. Different signals, worth keeping distinct even though it
  diverges from an exact mirror.
- `Zuora Download and Load` (a real Stage value in the source file) is
  that client's own billing/CPQ tooling, not universal — flagged directly
  and generalized to **`Source Download and Load`** for this template's
  generic starter phases, so it doesn't bake in one client's stack as if
  every migration has it.
- `add_migration_run_book_pass()` simplifies accordingly: one shared
  schema everywhere means no more per-section column-list matching — a
  phase is just "banner row, then data rows until the next banner,"
  identified by whether `Object` is populated (a banner row only ever
  populates column 1).

**Not built (still, and now more explicitly)**: no automatic
`dbo.BulkOpsLog` tie-in into the Load phase's result columns; Excel
row-grouping/outline levels (no evidence the real file used them,
skipped); the real file's literal client-specific phase names (`Build
Data Lake Data Sources`, `Install Functions`, etc.) — only the
*mechanism* was mirrored, not that project's specific instance data.

**Follow-up: `dbo.BulkOpsLog` tie-in — the "not built" item right above,
now built.** Two things requested: an on-demand command to pull new log
entries in, and a recommendation for making it automatic. Delivered both
off one reusable function, `migration_run_book.sync_run_book_from_log()`:
`update-migration-run-book` for on-demand/retroactive syncing, and an
opt-in `bulkops --run-book`/`--run-book-tab` pair that calls the same
function right after that load's own `BulkOpsLog` row is written (the
natural "end of the bulk job" moment) — opt-in, not automatic by default,
so `bulkops` doesn't silently touch a spreadsheet file on every run
against a real org.

Two hard requirements, both solved by the same mechanism:
- **Never reprocess already-synced log entries** — a per-tab "Last
  Synced Log Id" watermark (row 8 of the breadcrumb block, extending it
  from 7 rows to 8) tracks the highest `LogId` already pulled in.
  Deliberately **not** carried forward by `add_migration_run_book_pass()`
  (same treatment, and the same reason, as Target Environment) — a fresh
  pass hasn't had any of its own runs logged yet.
- **Never overwrite a row a human is using** — a new log entry only ever
  fills in an existing Load-phase row if it's still a genuinely
  unresolved auto-fill placeholder (`Object` matches, `Status` is blank
  or the auto-fill default `"Not Started"`, `Total Records` is blank).
  Otherwise (already resolved from an earlier run — e.g. a retry — or
  never pre-populated) it inserts a brand-new row via `ws.insert_rows()`
  right after the Load phase's last existing row, never touching
  anything outside that phase's own range. Existing conditional-
  formatting/data-validation ranges are already absolute (`D11:D1000`-
  style), so an inserted row is automatically covered without
  re-applying anything.

**Two real bugs found via live testing** (100 mock Accounts generated
with Snowfakery, inserted into `D360_PLAYGROUND`, twice — the second an
intentional retry that Salesforce's own duplicate detection rejected
outright, a genuine "Issue" result to verify against):
1. The pending-placeholder check treated `Status == "Not Started"` as
   "already resolved" (only truly blank was accepted), because
   `_load_order_rows()` had been changed earlier to set that value
   explicitly rather than leave it blank — so every sync update fell
   through to "insert a new row" instead of filling in the real
   placeholder. Fixed by treating blank *and* `"Not Started"` as
   unresolved.
2. The same `openpyxl` `cell(value=None)` no-op gotcha found twice
   already this session — writing `None` to the new watermark row via
   `ws.cell(..., value=None)` silently failed to clear it when
   `copy_worksheet` had already populated it from the source tab, so
   `add_migration_run_book_pass()` was carrying the watermark forward
   despite the code saying otherwise. Fixed by setting `.value` directly.
   Worth remembering as a standing gotcha for this codebase, not just a
   one-off: `cell(value=None)` never clears an already-populated cell.

**A small, genuinely reusable side addition**: `generate-related-mock-data
--count` now accepts a `NAME=N-M` range (e.g. `Contact=1-2`,
`Opportunity=0-1`), translated to a Snowfakery `random_number()` count
expression — a statistical split per parent row, not a guaranteed exact
percentage, but real enough for realistic test data (confirmed live:
100 Accounts, ~1.57 Contacts/Account average, ~50% Opportunity coverage
weighted toward multi-Contact Accounts). Snowfakery's own `count` field
already accepted a template-expression string; this was just exposing it
through `--count`'s existing flat-integer syntax rather than requiring a
hand-edited recipe.

**Not built**: per-row `Error Details` text (would need reading the
separate `_Result` writeback table alongside `BulkOpsLog`, not done here).

**Review follow-up (2026-07-09 full repo review) — four fixes**:
1. **Sync matching false positive (real correctness bug)**: the
   log-row-to-placeholder match was a naive substring check, so an
   `Order` log entry matched an `OrderItem` placeholder (`"order"` is
   inside `"030_orderitem_load.sql"`) and would have written Order's
   results onto OrderItem's row — and Order/OrderItem is exactly the
   pairing this framework's own batch heuristics expect together.
   Replaced with `_object_matches()`: exact cell match preferred, else
   the object name as a whole delimited token (underscore counts as a
   delimiter, required for the filename convention to match at all —
   which leaves one disclosed residual edge: standard `Quote` still
   matches inside `sbqq__quote__c_load.sql`). Ten-case matrix verified
   including the original bug case.
2. **Dead "safety" code removed**: `_apply_conditional_formatting()`
   "cleared" prior data validations via `ws._data_validations = []` — an
   attribute that doesn't exist in openpyxl 3.1.5, so a silent no-op
   masquerading as idempotency. Harmless in practice only because
   `copy_worksheet()` was separately confirmed to not carry conditional
   formatting or data validations at all (which is why re-applying on
   every new pass is required, not optional).
3. **Template row-width drift**: every starter row in
   `docs/MIGRATION_RUN_BOOK_TEMPLATE.md` carried an extra 17th empty cell
   against the 16-column schema, silently truncated by `zip()` — correct
   output by luck. Fixed the rows and taught `_parse_template()` to
   validate data-row width the same way it already validated the header,
   so this errors loudly instead of misaligning silently.
4. **Locked-file UX**: saving any run-book workbook that's open in Excel
   raised a bare `PermissionError` traceback; now a clear "close it in
   Excel and re-run" error (`_save_workbook()`), since a run book is
   exactly the kind of file someone has open while working.

Also from the same review: the committed demo workbook had been generated
from real test runs and embedded the operator's OS username (via
`BulkOpsLog.RunBy` → Person Responsible) and real org alias — regenerated
as a sanitized example, and `docs/SECURITY_OVERVIEW.md` §5 now calls out
run-book workbooks as PII-bearing generated artifacts explicitly.

## 17. Fuzzy matching / dedup (deprioritized, not built)

Explicitly lower priority than everything else in this "not yet started"
tier — there's real value in "free, runs as a SQL Server + Python job"
versus paying for a commercial dedup tool, but matching rules, merge
survivorship, and a review UI are a deep enough rabbit hole that it
competes for time against things with clearer immediate payoff.
`sql/functions/matching/` already has Jaro-Winkler/Soundex/N-gram T-SQL
functions from the SQL function library port. If this ever gets picked up
in earnest, `recordlinkage` or `dedupe` (Python) are worth evaluating
against hand-rolled T-SQL matching before building more of the latter —
`rapidfuzz` specifically for a fast Levenshtein-family option if T-SQL's
`JaroWinklerDistance` turns out too slow at scale.

## 18. Data Cloud (D360) query support — BUILT (`data_cloud.py`)

`query_tool.py` is explicitly scoped to CRM objects via the standard REST
Query API today (see its own docstring) — Data Cloud objects (DLOs, DMOs,
Calculated Insights, Unified Profile) use query surfaces this framework
doesn't touch at all yet. Current Salesforce docs (as of this research
pass) call the product **Data 360** now, not Data Cloud — same platform,
newer name; both terms are used interchangeably in this section since
that's what the docs themselves currently do.

**Original hard blocker, now resolved**: the org this framework was
connected to at the time had **zero Data Cloud objects provisioned** --
`sf.describe()` returned no `__dlo`/`__dlm` objects at all, so every
finding below was originally verified only against current
`developer.salesforce.com` docs, not a live call. A Data Cloud-licensed
Trailhead Playground org (with Agentforce also enabled) is now connected
(alias `D360_PLAYGROUND`) and does have at least one real DMO
provisioned — unblocking live verification of both findings #1 and #2
below.

**Research finding: this splits into (at least) two genuinely different
API surfaces, not one** — the same lesson `risk_analyzer.py`'s build
already taught (guessing which endpoint a metadata type needs fails
silently or errors outright, never partially works):

1. **Basic DLO/DMO querying is plain SOQL, no separate auth — CONFIRMED
   LIVE.** DLOs (`__dlo` suffix) and DMOs (`__dlm` suffix; fields use the
   ordinary `__c` suffix) are queryable through the *same* core-org REST
   endpoint and access token `query_tool.py` already uses (`sf.query()`).
   Originally confirmed only via Salesforce's own REST API Developer
   Guide (e.g. `SELECT PartyId__c FROM ContactPointEmail__dlm WHERE
   EmailAddress__c='jjones@email.com' LIMIT 100`); now verified against a
   real org (`D360_PLAYGROUND`) using this framework's own existing
   `describe`/`query` commands, completely unmodified — no new code was
   even needed to prove this:
   ```
   python cli.py describe StaticCurrencyRates_Home__dlm
   python cli.py query "SELECT Id, FromISOCurrencyCode__c, ToISOCurrencyCode__c, RateNumeratorNumber__c FROM StaticCurrencyRates_Home__dlm LIMIT 5"
   ```
   Both worked exactly like any standard CRM object — `describe()` listed
   the DMO's real fields, and the query returned real rows (one static
   USD→USD rate row, `RateNumeratorNumber__c`/`RateDenominatorNumber__c`
   both `1.0`). This means basic DLO/DMO querying is **not gated on
   building anything new** — extending `query_tool.py`'s own docstring to
   stop saying Data Cloud objects "aren't supported yet" (it already
   works, today, for basic lookups) is now just a documentation update,
   not new auth plumbing or new code.

2. **Complex cross-object queries (joins/aggregations/window functions
   spanning DLO+DMO+Calculated Insights together) need a separate Data
   Cloud tenant, CONFIRMED LIVE** — a genuinely different instance URL
   and access token, not the core org's. Token exchange: `POST
   {core-org-instance-url}/services/a360/token` with `grant_type=urn:
   salesforce:grant-type:external:cdp` and the core org's own access
   token as `subject_token` (`subject_token_type=urn:ietf:params:oauth:
   token-type:access_token`), returning `access_token` + `instance_url`
   for the Data Cloud tenant (a genuinely different host, e.g.
   `<tenant-id>.c360a.salesforce.com`, not the core org's domain at all).
   Queries then go to that tenant's own **`/api/v2/query`** — not `/api/
   v3/query` as originally guessed from docs alone, a real correction
   from live testing — as a POST with `{"sql": "<ANSI SQL string>"}` in
   the body. Verified end to end against `D360_PLAYGROUND`: queried
   `StaticCurrencyRates_Home__dlm` through this exact path and got back
   real rows (`[["USD","USD","1.000000000000000000"]]`) plus a
   `metadata` dict describing each column's real type (`VARCHAR`,
   `DECIMAL`) by position — a proprietary array-of-arrays response shape,
   **not** SOQL's list-of-dicts, so any real integration needs to zip
   `data` against `metadata`'s column order to get usable field names.
   This confirms the harder half of Data Cloud querying works too, not
   just basic SOQL lookups (finding #1) — both tiers of the architecture
   this research originally described are now proven, not theoretical.

   **What it actually took to get here, since none of it was obvious**:
   the `sf` CLI's own default connected app has no Data Cloud OAuth
   scopes, so the core-org token it produces can't do this exchange at
   all (`invalid_scope: the requested scope is not allowed`) regardless
   of the user's own Data Cloud permissions — this is an app-scope
   problem, not a permissions problem. Fixed by creating a dedicated
   **External Client App** (Salesforce disabled creating new *legacy*
   Connected Apps starting Spring '26 — confirmed live via web search,
   not assumed from training data, since this org runs a
   post-training-cutoff release) with OAuth + JWT Bearer Flow enabled,
   the generated certificate uploaded, and `api` + `refresh_token` +
   `cdp_query_api` (plus other `cdp_*` scopes for future testing)
   selected. Two non-obvious gotchas hit live, both worth remembering:
   - The Policies tab's "assign a permission set" picker only offered
     locally-created permission sets — a managed/license-bundled one
     (`GenieAdmin - Data Cloud Architect`, already on this user) never
     showed up as assignable. Fixed with a fresh, empty custom
     permission set created just to carry this app's assignment.
   - Even though JWT bearer flow doesn't literally use a refresh token,
     Salesforce's login endpoint still rejected the JWT assertion with
     `refresh_token scope is required...` until that scope was added to
     the app anyway — a real, slightly surprising requirement, not a
     misconfiguration on our end.
3. **Calculated Insights** have their own dedicated endpoint (`GET
   /api/v1/insight/calculated-insights/{ci-name}`) supporting SQL-style
   dimensions/measures/filters and pagination (limit/offset/order by,
   default cap 4,999 rows/call) — not plain SOQL, not the same surface
   as #2 either.
4. **Unified Profile — CONFIRMED LIVE, both paths.** Has a dedicated
   Profile API (`GET /api/v1/profile/{dataModelName}`) *and* is
   separately reachable via plain SOQL against Unified DMOs directly
   (same #1 mechanism) — both verified working against
   `D360_PLAYGROUND` after running a real Identity Resolution ruleset
   ("Individual Match," 1,052 source Leads → 1,052 Unified Individuals,
   see #18's own writeup below) to actually produce Unified Profile data
   to test against. Real dataModelName confirmed: the DMO's full API
   name works directly (`UnifiedssotIndividualIndv__dlm`), not a
   shortened alias like the generic docs example (`Individual__dlm`)
   suggested. `filters` is genuinely **required** by the API — omitting
   it entirely fails with a missing-parameter error regardless of
   dataModelName, confirmed by testing four different name guesses that
   all failed identically until a filter was added — so this is a
   profile *lookup* API (find a known person), not a bulk browse
   endpoint. Filter syntax `[Field=Value]`, equality only, AND-combined
   either as `[FieldA=X,FieldB=Y]` or `[FieldA=X],[FieldB=Y]` (both
   confirmed to work identically). No Data Space parameter needed in the
   API at all, unlike the Setup UI's Profile Explorer, which makes you
   pick one even when "default" is the only option that exists.
5. **Data Graphs — metadata endpoint CONFIRMED LIVE, query endpoints
   still unverified.** Metadata discovery (`GET /api/v1/dataGraph/
   metadata`) uses the same Data Cloud tenant token as findings #2-#4 —
   confirmed live against `D360_PLAYGROUND` (returns `{"metadata": []}`,
   same empty-until-configured shape Calculated Insight metadata showed
   before one existed). Query-by-id (`GET /api/v1/dataGraph/
   {dataGraphEntityName}/{id}`) and query-by-lookup-key (`GET /api/v1/
   dataGraph/{dataGraphEntityName}?lookupKeys=[...]`) are built in
   `data_cloud.py` (`query_data_graph`) but **not yet live-tested** —
   this org has zero Data Graphs configured, and building one (a primary
   DMO + related/participating DMOs + levels) is a heavier Setup lift
   than a Calculated Insight's SQL paste or an Identity Resolution
   ruleset was. A third, independent surface from findings #1-#4, same
   as originally scoped — just now partially rather than fully
   unverified.

Sources consulted (all current as of this research pass, not relied on
from training knowledge): [Query API Reference](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-queryservices-overview.html),
[SQL Query APIs](https://developer.salesforce.com/docs/data/data-cloud-query-guide/guide/dc-sql-query-apis.html),
[OAuth Token Exchange Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_token_exchange_overview.htm),
[Query Data Cloud via standard REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_cdp_query.htm),
[Calculated Insights API](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-ci-call-overview.html),
[Profile API](https://developer.salesforce.com/docs/atlas.en-us.c360a_api.meta/c360a_api/c360a_api_profile_call_overview.htm),
[Data Cloud object suffixes](https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_concepts_data_cloud_objects.htm),
[Data Graphs API](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-data-graphs-overview.html).

**Built (`data_cloud.py`), turning today's ad hoc scripts into real,
reusable commands** — the explicit ask once findings #1-#3 were verified
live: a different data architect picking up this repo later just runs a
command, no need to hand-derive the token exchange or already know which
standard object holds which status.

- **`data-cloud-query "<SQL>"`** — finding #2's tenant token exchange +
  `/api/v2/query`, for complex/cross-object Data Cloud SQL. Basic
  single-DLO/DMO lookups still just use the existing `query` command —
  this one is specifically for what that can't do.
- **`list-calculated-insights`** / **`query-calculated-insight <name>`**
  — finding #3, live: `GET /api/v1/insight/metadata` to discover what
  exists, `GET /api/v1/insight/calculated-insights/{name}` for its actual
  computed data.
- **`data-cloud-status <type> [name]`** — status checks across four
  standard core-org objects, **all confirmed to need only plain SOQL, no
  Data Cloud tenant token at all** (a genuinely useful discovery in its
  own right — these aren't gated behind the harder auth path): `calculated-insight`
  (`MktCalculatedInsight`), `data-stream` (`DataStream`, covering the DSO
  refresh/error monitoring #20 was originally scoped around), `identity-resolution`
  (`IdentityResolution` — its *resulting* Unified DMO rows are a plain
  DMO like any other, query those with `query`/`data-cloud-query` once
  you know the name, not a separate feature), and `data-transform`
  (`MktDataTransform`).

**A real bug found and fixed via live testing, not assumed from docs**:
`/api/v2/query` and the Calculated Insight data endpoint do **not** share
one response shape. `/api/v2/query` returns `{"data": [[...]], "metadata":
{"col": {"placeInOrder": N}}}` — a positional array needing `metadata` to
know column order. The Calculated Insight endpoint returns `{"data":
[{...}], "metadata": {}}` — rows are already plain dicts, metadata is
empty. The first implementation assumed the positional shape for both,
which silently produced empty `{}` records for Calculated Insight data
(zipping real dict keys against an empty column list). Fixed by
detecting which shape actually came back rather than assuming one.

**Verified end to end**: built a real Calculated Insight (`RateCount__cio`,
count of `StaticCurrencyRates_Home__dlm` rows grouped by
`FromISOCurrencyCode__c`) via Data Cloud's SQL authoring mode — its own
real syntax rules turned out to differ from generic ANSI SQL in three
ways discovered live: columns must be `table.column`-qualified using the
*real* DMO name (bare aliases aren't recognized — a bare alias like `a`
gets misread as an attempted second DMO reference, failing with `DMO a
is not listed in factTables`), and every output attribute (dimensions
included) needs an explicit `AS` alias ending in `__c`. Watched it
progress from `PROCESSING` to `SUCCESS` via `data-cloud-status
calculated-insight`, then confirmed `query-calculated-insight` returned
the real computed row once done.

**Built (`data_cloud.py`): `data-cloud-profile <dataModelName> <filter>
[--fields] [--limit] [--offset] [--orderby]`** — finding #4, turned into
a real command the same way #1-#3 were. This is also roadmap #37's
answer (a CLI alternative to Data Cloud's own Profile Explorer) — one
command instead of clicking Data Space → entity → attribute repeatedly.

**Built (`data_cloud.py`): `list-data-graphs`** — finding #5's metadata
endpoint, confirmed live (`{"metadata": []}`, none configured in this
org yet). `data_cloud.query_data_graph()` (query-by-id or query-by-
lookup-key) is written but genuinely **not yet live-verified** — the
one piece of `data_cloud.py` still in that state, since building even a
minimal real Data Graph needs more Setup work (primary + related DMOs,
levels) than the other findings' test artifacts did. No CLI command
wired up for it yet for that reason — code exists, hasn't earned "real
command" status by this module's own dogfooding standard.

**Note (not a reason to redo any of the above)**: `forcedotcom/sf-skills`
(Salesforce's official Agent Skills library, discovered while building
#57) has a `data360-query` skill covering similar Retrieve-phase ground
via an external `sf data360` CLI plugin. `data_cloud.py` here talks to
the REST APIs directly — a different, already-working, already-verified
approach for this framework's own use, not something to swap out.

**A new, genuinely low-effort candidate found the same way**: unlike the
rest of the `data360-*` family, `data360-schema-get` does **not** wrap
the external plugin at all — it hits plain SSOT REST endpoints (`GET
/services/data/v64.0/ssot/data-lake-objects` and `/data-model-objects`),
same no-external-dependency shape `data_cloud.py` already uses
everywhere else. It gives something `describe()` doesn't today: category,
status, and record count for **every** DLO/DMO in one call, the same
"one call for many objects" value `record-counts` already provides on
the CRM side (see the canonical-commands note on that command). Not
built yet — a plausible `list-dlos`/`list-dmos` command, same shape as
`list-data-graphs` above, whenever this gets picked up.

## 19. Data Cloud semantic model reference (not built, depends on #18)

Idea: understand and expose the semantic model (the layer that gives DMOs
and their relationships business meaning beyond raw schema) as a reference
data architects can query against — both the data and the metadata *about*
it — the same spirit as `metadata.py`/`dump_describe()` does for CRM
objects today, but for Data Cloud's own metadata layer. Needs real API
research first (see #18's caution); likely depends on #18 existing first
since both need the same Data Cloud API access.

**Reference for whenever this (and #22/#24) gets picked up**: the user
pointed at Salesforce Developers' public Postman workspace
(`postman.com/salesforce-developers/salesforce-developers`), which has
folders for several Data 360 APIs — Ingestion API, Data Graph API,
Metadata API, Query Unified Record Id — flagged for later review, not
yet dug into. `WebFetch` can't render Postman's workspace pages (JS SPA,
returns only the static shell); when it's actually time to review these,
either ask for an exported collection JSON or go straight to
developer.salesforce.com's own docs/blog posts for the same API, which
is what worked cleanly for #22's Ingestion API research.

**Check `forcedotcom/sf-skills` before building this** (Salesforce's
official Agent Skills library, discovered while building #57) — its
`data360-harmonize` skill (DMOs, mappings, relationships, identity
resolution, unified profiles, data graphs) and `data360-schema-get`
(DLO/DMO schema via the SSOT REST API) may already cover a meaningful
chunk of this item's own scope. Requires an external `sf data360` CLI
plugin (not vendored, a different dependency model than this framework's
own direct-REST-API approach in `data_cloud.py`) — worth weighing that
before treating it as a drop-in replacement rather than a reference.

**Concrete schema found, not just a pointer to check later** — read in
full: `data360-orchestrate`'s `assets/definitions/relationship.template.json`
gives the actual DMO relationship shape the semantic model is built from:
a `relationships[]` array of `sourceObjectName`/`targetObjectName`/
`cardinality` (e.g. `ManyToOne`)/`sourceFieldName`/`targetFieldName`/
`relationshipOwner`. That's real, usable ground truth for what "the
relationship layer" actually looks like as data — closer to answering
this item's own question than the earlier "check the skill" note was.
`dmo.template.json` (developerName/label/category/`fields[]`) is the DMO
definition shape those relationships connect. Still gated on the same
external-plugin dependency question above before deciding whether to
consume this via that plugin or reverse it into `data_cloud.py` directly.

## 20. DSO refresh/error monitoring — BUILT (`data_cloud.py`)

Problem: before trusting data pulled from a DSO (Data Source Object — the
raw ingested layer, see #21), a data architect needs to know when it last
refreshed and whether its last ingestion run had errors — silently working
off stale or partially-failed ingested data is a real risk specific to the
Data Cloud pipeline (source → DSO → DLO → DMO), distinct from anything
`profiling.py` checks about the *content* of already-landed data.

**Built and confirmed live**: `data-cloud-status data-stream [Name]`
queries the standard `DataStream` object via plain core-org SOQL (no
Data Cloud tenant token needed, same discovery as #18's status checks) —
`DataStreamStatus`, `ImportRunStatus`, `LastRefreshDate`,
`TotalNumberOfRowsAdded`, `LastDataChangeStatusErrorCode`,
`ExternalStreamErrorCode`. This answers the practical question this item
was raised about ("when did this last refresh, were there errors")
directly.

**The DSO-specific object is also confirmed, and it's genuinely distinct
from Data Stream** — `data-cloud-status dso` queries
`DataLakeObjectInstance` (labeled "Data Lake Object" in Setup — the
actual DSO, the raw ingested layer), not a rename of `DataStream`. Its
own fields: `DataLakeObjectStatus`, `SyncStatus`, `HydrationStatus`,
`LastRefreshDate`, `TotalRecords`, `ExternalObjectErrorStatus`,
`ExternalObjectErrorCode`. Verified live while a real Data Bundle (the
Sales bundle) was mid-deploy against `D360_PLAYGROUND`: all 7 DSOs it
created (`Lead_Home`, `User_Home`, `Account_Home`, `Contact_Home`,
`Opportunity_Home`, `OpportunityContactRole_Home`, plus the earlier
`Static Currency Rates Home`) showed `ACTIVE`/`Hydrated` with no errors —
`TotalRecords: 0` on the CRM-sourced ones reflects this playground
having little real Account/Contact/Opportunity data yet, not a failure.
Both this and Data Stream monitoring are now built and confirmed
separately — this item's real-world need (and then some) is satisfied.

## 21. DSO→DLO mapping: read, then auto-map (not built)

Problem raised directly: "can you read the data mapping from DSO to DLO,
and is it possible to update it?" Conceptually well understood — a DSO's
fields get mapped/transformed into a DLO's fields, which then map again
into canonical DMO fields (see Salesforce's own "Data Objects in Data
Cloud" docs) — but the *specific* API/metadata object that exposes this
mapping programmatically, and whether it's writable outside Data Cloud's
own Setup UI, is **not yet confirmed** and needs real API-doc research
(plus a live probe against this org) before answering definitively, let
alone building against it.

If reading turns out to be possible, extending `auto_mapper.py`'s
approach (thesaurus + fuzzy matching + a data-quality gate) to suggest
DSO→DLO mappings is a natural, well-precedented next step — the matching
*logic* built for CRM field mapping should mostly transfer; what's unknown
is only the metadata read/write surface on the Data Cloud side.

**Check `forcedotcom/sf-skills` before doing the API research above** —
`data360-prepare` (streams, DLOs, transforms) is described as owning
exactly this DSO→DLO territory. Same external-plugin-dependency caveat as
noted on #19.

**Partial answer found, via the plugin's own command surface** — reading
`data360-harmonize`'s full skill content (not just its frontmatter) shows
it wraps real `sf data360 dmo mapping-list` and `dmo map-to-canonical`
subcommands, and `data360-orchestrate`'s `assets/definitions/
mapping.template.json` gives the concrete field-mapping payload shape
those commands read/write: `sourceObjectName`/`targetObjectName`/
`fieldMappings[]` of `sourceFieldName`/`targetFieldName` pairs. That's a
real, positive signal that this mapping layer **is** readable and
writable — just through the external `sf data360` plugin's own command
surface, not yet confirmed as a directly-callable REST endpoint this
framework's own `data_cloud.py` could hit without that plugin installed.
The plugin-vs-direct-REST distinction from #19 is the remaining open
question, not "is this possible at all" anymore.

**`data360-prepare`'s own gotchas, read in full, are relevant here too**:
it explicitly owns "the handoff from connector setup into a live
stream" and DLO/transform management, and separately confirms (matching
what's already noted on #44 rather than contradicting it) that "some
external database connectors can be created via API while stream
creation still requires UI flow" — the same known partial-automation
gap, now corroborated from a second, independent source rather than
resting on this framework's own research alone.

## 22. SQL-Server-backed local DSO ingestion — DEAD END for the actual ask; a heavier alternative exists but isn't being pursued

Idea, raised directly: build something equivalent to Data Cloud's local
CSV upload path for a DSO, but sourced from SQL Server instead of a local
file — the same "SQL Server as the integration hub" principle this whole
framework is built around, applied to Data Cloud ingestion instead of CRM
`bulkops`. Real payoff called out directly: this would make `mock_data.py`
(already built, Mockaroo-backed) useful for **Data Cloud** testing too, not
just CRM object testing — generate mock rows into a SQL Server table, then
push them into a DSO locally for testing without touching a real source
system.

**The specific ask — an API that drives Data Cloud's local file-upload
workflow itself — is a confirmed dead end.** Data Cloud's "Local File
Upload Connector" (the thing under Data Cloud Setup → Other Connectors,
shown as a connector named `UploadedFiles`) is **browser-UI-only, by
design**: Salesforce's own Beta announcement describes it as a manual
drag-and-drop/file-picker feature for one-off files under 10MB, and
confirms data streams built from it "cannot be scheduled or refreshed."
Confirmed across multiple independent sources (Salesforce's own blog +
several third-party Data Cloud implementer write-ups, cross-checked, not
assumed) that **no REST endpoint exists for this connector type at all**
— there's nothing to call instead of clicking the button. This isn't a
missing-code gap; there's no API surface to build against.

**A materially different, heavier path is real but explicitly not being
pursued right now.** The separate, full **Ingestion API** *does* have a
genuine REST surface (confirmed live research below) — but it means
adopting an entirely different connector type per object (author an
OpenAPI schema, create a dedicated Ingestion API connector + Data Stream,
grant an extra OAuth scope), not a lightweight bolt-on to the simple
file-upload flow. Told directly this isn't the direction wanted, so this
path stays researched-and-parked rather than built — the design notes
below are kept for the record in case that changes later, not as a
current plan. S3/SFTP connectors were also considered and ruled out for
the same core reason: both are Data-Cloud-initiated, schedule-based
*pulls*, not something this framework could trigger on demand the way
`bulkops` triggers a CRM load today.

**What was confirmed about the (currently unpursued) Ingestion API path**,
against Salesforce's own Data 360 Integration Guide and a July 2023
Salesforce Developers blog walkthrough (not assumed, per this repo's
post-training-cutoff rule):

**A one-time manual setup step in Data Cloud Setup is required per
object, before any code can run** — this is the actual answer to the
roadmap's original open question ("local/manual upload" vs. "a
configured Data Stream from a real connector"): **it turns out to be the
latter.** The Ingestion API *is itself* a connector/Data Stream type
("Ingestion API connector"), not a bypass of that model:
1. Author an OpenAPI 3.0 YAML schema defining the target object's fields
   (`components.schemas.<object>.properties`), and upload it in Data
   Cloud Setup → Ingestion API → Connect.
2. Create and deploy a Data Stream from that connector — pick the
   object, a category (Engagement/Profile/Other), map the primary key
   and (for Engagement) an event-time field.
3. The connected app / External Client App needs the `cdp_ingest_api`
   OAuth scope granted, **in addition to** the `cdp_query_api` scope
   `data_cloud.py`'s existing tenant-token exchange already needs (§18) —
   a real, disclosed gap: today's app almost certainly doesn't have this
   scope yet, since nothing in this repo has requested it.

**Two ingestion patterns, and Bulk is the right fit for this framework,
not Streaming**:
- **Bulk (CSV, job-based)** — matches this framework's existing shape
  almost exactly (the same "stage a CSV, submit a job, poll/complete it"
  pattern `bulkops.py` already uses for Bulk API 2.0):
  `POST /api/v1/ingest/jobs` (`{"object": "<name>", "operation":
  "upsert"|"delete"}`) → `PUT /api/v1/ingest/jobs/<id>/data` (raw CSV
  body) → `POST /api/v1/ingest/jobs/<id>/actions/complete` → job closes
  (auto, or `PATCH .../jobs/<id>` `{"state": "Closed"}`). CSV up to
  150MB/file, but rate-limited to 20 requests/hour, 5 concurrent — fine
  for periodic test-data pushes, not a high-frequency path.
- **Streaming (JSON)** — `POST /api/v1/ingest/sources/<connector>/
  <object>` with `{"data": [...]}`, capped at 200KB/request, built for
  small real-time incremental updates. Wrong shape for "push N mock rows
  from a SQL Server table" — noted for completeness, not the build target.
- Both hang off the tenant instance URL from the *same* Data Cloud
  session exchange `data_cloud.py`'s `get_data_cloud_session()` already
  does (`grant_type=urn:salesforce:grant-type:external:cdp`) — this is
  additive to that module, not a new auth mechanism.

**Design once someone actually configures a test connector+Data Stream**
(this step needs a human with Data Cloud Setup access; nothing here can
do it programmatically): a `dso_ingest.py` mirroring `bulkops.py`'s own
shape — `ingest_dso(sf, engine, source_table, object_name, operation,
schema="dbo", stage_dir="_stage")`: stage the SQL Server table to CSV
(reusing the exact CSV-staging convention already in `bulkops.py`),
create the bulk job, `PUT` the CSV, mark complete, poll job status until
`Completed`/`Failed`, return a summary — same shape as `bulk_op()`'s own
return dict, for CLI/reporting consistency. `generate-mock-data`/
`generate-related-mock-data` (#6) are natural sources once this exists —
mock rows into a SQL Server table, then this pushes them into the DSO,
neither backend is CumulusCI-dependent (CumulusCI has no Data Cloud/DSO
capability at all, confirmed reviewing its data docs) so nothing about
that changes.

**Not built, and not currently planned to be** — parked in the
researched-not-pursued sense (see the "Scope" note at the top of this
file), specifically because the lightweight version that motivated this
item doesn't exist, and the real alternative is a heavier lift than
wanted right now. Revisit if the appetite for the full Ingestion API
setup changes; see #44 for the direction actually being pursued instead.

## 23. Data Kit / Bundle documentation (not built, depends on #18/#19)

Idea: surface what's in a Data Cloud Data Kit/Bundle that's actually
relevant to a data architect scoping a migration, and document it the same
way `generate-mapping-doc` documents CRM field mappings — one spreadsheet,
reviewable structure, not a wall of raw metadata. Depends on #18/#19
existing first (need real Data Cloud metadata access before there's
anything to document).

**Check `forcedotcom/sf-skills` first** — `data360-orchestrate` explicitly
covers "data spaces and data kit management" as part of its cross-phase
scope. Same external-plugin caveat as #19.

## 24. Calculated Insight scripting + testing + CI/CD (not built, depends on #18)

Idea, raised directly: script Calculated Insight definitions (DMQL) here
in the repo — versioned, reviewable, the same principle
`sql/transformations/*.sql` already applies to CRM transform logic — write
query-based tests against them, then deploy the resulting definition via a
CI/CD pipeline rather than hand-building Calculated Insights in Data Cloud
Setup each time. Depends on #18 (Data Cloud querying) existing first, to
actually run the "query tests" part; the CI/CD deployment side would need
its own research into how Calculated Insight metadata is deployed
programmatically (Metadata API component type, if one exists, vs. Setup UI
only today).

**Check `forcedotcom/sf-skills` first** — `data360-segment` explicitly
covers "manages calculated insights" already. Same external-plugin
caveat as #19; the CI/CD-pipeline half of this idea (git-versioned,
tested like code) still looks like a genuine gap even if their skill
covers the interactive scripting side.

## 25. Web UI for less-technical users (not built)

Problem: everything so far assumes an operator comfortable with a terminal
and Claude Code. A data architect isn't always the only person who needs
to see this framework's output, and not everyone is going to run a CLI.

Idea: a lightweight local web console -- not a rebuild of Salesforce's own
UI (deliberately out of scope; Setup UI stays Setup UI), but a friendlier
front end for *this* framework's own surface:
- An environment/connection picker (which SQL Server, which Salesforce org
  alias) instead of editing `.env` by hand.
- A SQL Server browser + query window with a real results grid (not flat
  console text).
- A "skills menu" -- reflect `.claude/commands/*.md`'s own descriptions into
  buttons, each shelling out to the same CLI verb this framework already
  has. No new logic, just a friendlier way to trigger it.
- A flat-file loader: upload a CSV/Excel file in the browser, land it in a
  SQL Server table -- the same `pandas`/`SQLAlchemy` path `replicate.py`
  already uses, just fed from an upload instead of the org.
- A chat pane. Explicitly **not** a from-scratch reimplementation of an
  agent tool-use loop -- that's Claude Code's own job. If this gets built,
  it should wire in the Claude Agent SDK for a scoped assistant, or embed/
  launch Claude Code itself, rather than duplicate it.

Candidate stack: Streamlit (Python-native, matches this repo's stack
already; built-in file-uploader widget covers the CSV loader almost for
free) plus `streamlit-aggrid` for a real spreadsheet-style results grid.
Evaluated and set aside for now: Retool/Appsmith-style low-code app
builders (real capability, but add a self-hosted server and more moving
parts than a single Streamlit script justifies at this stage); Gradio (more
ML-demo-shaped than data-grid-shaped).

**This is a bigger step than it looks.** Today this framework is a CLI one
already-credentialed operator runs at a terminal -- no listening network
port, no session/auth boundary of its own. A web UI is a new, listening,
possibly-multi-user surface, which is a genuinely different trust model,
not just a new feature. See `docs/SECURITY_OVERVIEW.md` §8 -- building this
requires a fresh security review pass, not an incremental patch to the
existing one. Single sign-on and any real multi-user access control belong
here too once this is picked up (tracked as #26, not folded into this item,
since SSO is its own scoping exercise even once a UI exists to put it in
front of).

## 26. SSO / multi-user access control (not built, depends on #25)

Problem: once #25 exists, "who can open this web console, and as whom"
becomes a real question for the first time -- today the CLI has no
independent auth boundary at all (whoever can run it, can use it, same as
`sqlcmd` or Data Loader). A browser-accessible tool changes that.

Idea, roughly in order of how this is typically layered rather than a
committed design: start with an identity-provider-backed reverse proxy
(e.g. an OAuth2 proxy in front of Streamlit) rather than hand-rolling
session/auth code -- consistent with this framework's general preference
for well-established components over custom security-sensitive code (see
`docs/SECURITY_OVERVIEW.md` §9's supply-chain stance). Scope should include
at minimum: who can authenticate, whether different users get different
Salesforce/SQL Server credentials or share the tool's own service
credentials (the latter needs its own audit-trail story), and whether
this needs to plug into an org's existing SSO (Okta, Azure AD, etc.) rather
than manage its own user directory.

Also worth tracking here once scoped: whether tighter Salesforce-side
security (permission sets, sharing rules, a dedicated API-only migration
user per hard rule 8's note) needs its own roadmap treatment as adoption
broadens beyond a single trusted operator -- likely an expansion of #5
(org metadata risk analyzer) rather than a new item, since it's the same
"what could this touch that it shouldn't" question applied to access
control instead of automation conflicts.

## 27. Open query in SSMS (stage + launch) (not built, depends on #25)

Raised directly: can this framework force SSMS open and hand it a query to
run against the mirror DB, instead of only showing results in the console
(#8) or a chat reply? Checked directly — **there is no SSMS command-line
switch to auto-execute a query on open**; `Ssms.exe -S <server> -E
<path.sql>` (or `-d <database>`, `-U`/`-P` for SQL auth) opens SSMS
connected to the right server with a `.sql` file already loaded in a new
query editor tab, but a human still has to hit F5 themselves. That's a
real, if partial, capability — not nothing — but it only stages a query
for review, it doesn't run it unattended.

Given that ceiling, this fits better as a companion action to the SQL
Server browser + query window already scoped under #25 (Web UI) than as
its own standalone CLI verb: an "Open in SSMS" button next to a query
result there would write the current query to a `.sql` file and shell out
to `Ssms.exe` with the right connection args, giving a user who prefers
SSMS's full editor/grid a one-click handoff from this framework's own
query tool into it, without duplicating SSMS's own execution/results UI.
Also keeps with this framework's "reviewed hands" model (`CLAUDE.md`) —
staging a query for a human to knowingly execute in SSMS, rather than this
framework executing it invisibly on their behalf.

## 28. Pluggable integration-hub backend — SQLite alongside SQL Server (built); MongoDB still deferred

Originally raised as "don't want this framework permanently locked into
one tool as the integration hub" with MongoDB named as the concrete
alternative to keep open. **SQLite is what actually got built**, raised
directly for a real reason rather than speculatively: a coworker doing
similar migration work chose SQLite and was loading via raw CSV/Excel
without a proper SQL staging layer — it "blew up" at volume, exactly the
failure mode this framework's SQL-centric design exists to avoid. Making
the real load engine work against SQLite lets that project get this
framework's actual value (a proper staging DB, row-level error tracking,
activity logging) without requiring a SQL Server install.

**Why SQLite was a tractable ask where MongoDB (still) isn't.** The
original caution about a "second hub mode" being a bigger ask than a
driver swap remains true for a genuinely different data model (a document
store, no relational `JOIN`, no `sql/transformations/*.sql` equivalent).
SQLite doesn't have that problem — it's still SQL, still relational, still
has real `JOIN`/`GROUP BY`/window functions. The actual gap was narrower:
SQL-Server-only system functions (`OBJECT_ID`/`COL_LENGTH` existence
checks), bracket-quoted identifiers, `SELECT ... INTO`, `TOP (n)`, and
`IDENTITY` columns — all mechanical syntax differences, not a data-model
mismatch.

**Explicit, deliberate scope boundary, agreed directly rather than
assumed**: the SQL-Server-only cleansing/matching function library
(`sql/functions/cleansing|matching|lookups` — Jaro-Winkler, Soundex,
postal cleansing; genuine T-SQL-only tricks like `master..spt_values`/
`FOR XML PATH` with no SQLite equivalent) stays SQL-Server-only,
permanently — "kept in flavors by db, only where they work," an accepted
gap, not a blocker. Several data-architect tools that use the same
`OBJECT_ID`/bracket-quoting patterns but aren't part of the load engine
itself — `profiling.py`, `risk_analyzer.py`, `auto_mapper.py`,
`migration_run_book.py`, `mock_data.py`/`snowfakery_data.py`,
`solution_doc.py`, `load_order.py`, `mapping_doc.py`, `parquet_import.py`,
`record_types.py`, `reference_record.py` — are **SQL-Server-only for now**,
confirmed safe to exclude (nothing in `bulk_op()`'s or `replicate()`'s
call graph reaches them) and portable later, incrementally, via the same
seam whenever a real SQLite project actually needs one of them.

**What shipped**:
- `sql_dialect.py` — a `SqlDialect` ABC (`MssqlDialect`/`SqliteDialect`)
  keyed off `engine.dialect.name` (not a separately-threaded backend flag,
  which could silently drift from what the engine actually is): existence
  checks, identifier quoting, `SELECT INTO`/`CREATE TABLE AS SELECT`,
  `TOP`/`LIMIT`, autoincrement PK DDL, and a per-backend Salesforce-field-
  to-SQL-type mapping (`type_map.py` for SQL Server; a much simpler
  TEXT/INTEGER/REAL mapping for SQLite's type *affinity* system).
- `sql_client.py` — `SQL_BACKEND=mssql|sqlite`. SQLite mode uses
  `SQL_SQLITE_DIR` (a directory) and `SQL_SQLITE_SCHEMAS` (comma-separated)
  — one `<schema>.db` file per declared schema, real `ATTACH DATABASE`'d
  under its own name on every connection (not a name-prefixing scheme,
  which was considered and rejected — it breaks per-schema `DROP`/
  discovery and doesn't match what pandas' `schema=` kwarg already means
  on SQLite). This makes every existing `schema=schema` call site work
  **unchanged** across both backends. Also sets `PRAGMA journal_mode=WAL`/
  `synchronous=NORMAL` once per connection — the real lever for SQLite
  write throughput at volume (a `method="multi"` `to_sql()` optimization
  was considered and rejected: SQLite's bound-parameter limit can overflow
  with a wide load table, a real failure mode at exactly the volume this
  is for).
- `replicate.py`, `bulkops.py` (writeback, retry, opt-in `BulkOpsLog`
  activity logging), and `batch_advisor.py`'s two existence-checks
  (confirmed **not optional** — `bulk_op()`'s default `batch_size="auto"`
  path calls them unconditionally, so this was the one fix that would
  have broken the very first default SQLite call otherwise) all migrated
  to `sql_dialect.py`.
- Hard rules 6/7 (`AddBulkLoadSortColumn`/`CheckLoadTableDuplicateKeys`)
  **retired as stored procedures entirely** — confirmed the only 2 in the
  whole repo — replaced by `load_table_prep.py` + real `cli.py` commands
  (`add-bulk-load-sort-column`/`check-load-table-duplicate-keys`) running
  backend-appropriate inline SQL directly. A genuine improvement, not just
  a port: these were the only hard-rule tools still requiring a human to
  hand-run raw T-SQL via `sqlcmd` instead of a real command.
- `source_ingestion.py` gained a SQLite staging path — `BULK INSERT` is
  T-SQL-only, so SQLite gets a paired DDL-documenting `.sql` script plus a
  chunked pandas `read_csv`+`to_sql` Python step for the actual data load,
  same numbered/git-committed/drift-checked artifact philosophy either way.

**Real bugs found via live verification against both backends, not just
assumed correct**: a bare `RowCount` column alias raised a real SQL Server
syntax error ("Incorrect syntax near the keyword 'RowCount'") in
`load_table_prep.py`'s verification query — the same reserved-word
collision `source_ingestion.py`'s own `SourceIngestionLog.[RowCount]`
column already had to work around, just missed on this new query until
tested against a real instance. Also: Python 3.12 deprecated `sqlite3`'s
default datetime adapter — fixed by registering explicit ones in
`sql_client.py` rather than letting a future Python version silently break
`BulkOpsLog`/`SourceIngestionLog`'s timestamp columns.

**A more significant pair of bugs, found in a later real-volume test, not
SQLite-specific**: running a genuine end-to-end load (Snowfakery-generated
mock data, 1000+ Accounts through Contacts through Opportunities) surfaced
that `bulk_op()` never excluded the `[Sort]` column (hard rule 6) from
what gets sent to Salesforce — any real load table with a Sort column
would fail pre-flight on its very first insert with "not a real field:
['Sort']", on **either** backend, not just SQLite. `key_column` (e.g.
`LoadId`) had the identical gap on update/upsert — already correctly
excluded on insert, but not there. Both fixed, and each now has its own dedicated regression test in
`tests/test_bulkops_sqlite_integration.py` — one builds a real Sort column
via `add_bulk_load_sort_column()` then confirms `bulk_op()` insert still
succeeds; the other confirms an update sends `Id` but not `key_column`.
Worth calling out on its own: this is a correctness bug in `bulk_op()`
itself, unrelated to the SQL backend work that happened to be underway
when it was found.

**Verification**: a real end-to-end flow (`replicate.create_table()` →
load table → `bulk_op()` against a stub Salesforce client → writeback
confirmed via a fresh connection → `build_retry_table()` → hard rules 6/7)
run against both a real local SQL Server instance and a real SQLite file,
not mocked. Promoted into `tests/test_bulkops_sqlite_integration.py`
(the suite's first test file touching a real engine — every other test is
pure-function/isolated) once proven out via a scratch script first.

**MongoDB stays deferred, unchanged from the original reasoning** — a
document store is still a genuinely different data model, not a mechanical
syntax difference, and the security considerations already raised (a
different auth model entirely, a well-known history of internet-exposed
unauthenticated MongoDB instances from insecure defaults) still apply.
Revisit only when there's a concrete reason, same as before.

## 29. Shared/VM-hosted SQL Server for multi-user access (not built, deliberately deferred)

Raised directly: today's model assumes one architect on one local
machine with a local SQL Server Developer Edition instance (`README.md`'s
whole one-time setup section). If a team needs multiple people working
against the *same* mirror DB concurrently — not just multiple separate
projects/orgs, but shared state — a VM-hosted SQL Server instance becomes
a real requirement, envisioned directly as the likely next step.

Worth tracking once this becomes real, not yet scoped in detail:
- **Connection concurrency and locking** — this framework's transforms
  and `bulkops` loads already do real `DROP`/`CREATE`/`INSERT` against
  shared tables (`Account_Load`, `dbo.BulkOpsLog`, etc.); two people
  running different transforms against the *same* schema at the same
  time is a genuinely different concurrency story than today's
  single-user-local assumption.
- **Credentials** — per-user SQL logins vs. a shared service account
  (the latter needs its own audit-trail story, the same tension hard
  rule 8's note already raises for a dedicated API-only Salesforce user).
- **Network exposure** — VPN/private-network-only access to the VM,
  never a publicly reachable SQL Server port; this needs its own
  `docs/SECURITY_OVERVIEW.md` treatment once real, the same way #28 would.
- **Backup/restore practice** for a shared instance holding multiple
  people's in-progress work, versus today's "it's disposable, just
  re-run `replicate`" local-instance assumption.

Related in spirit to #25/#26 (Web UI + SSO) but genuinely independent of
whether a Web UI ever ships — even today's CLI/Claude Code users could
collide if pointed at the same shared VM database concurrently, so this
is a database-layer question, not only a UI-layer one. **Deliberately
deferred** — prototyping today is single-user/local on purpose; revisit
once a real multi-user engagement actually needs it.

## 30. Additional migration source connectors: Snowflake, MongoDB, etc. (not built, deliberately deferred)

Raised directly, alongside #28/#29, as part of the same "don't lock
ourselves into one tool" theme — but this is a different layer than #28.
#28 asks whether the *integration hub* itself (today: SQL Server) could
be something else. This item asks whether more *source* systems (where
data originates *before* landing in that hub) could feed into it, the
same "many sources, one hub" pattern `parquet_import.py` already
established as a second entry point alongside `replicate.py`'s
org-sourced path (`README.md`'s repository-structure section already
frames this precedent explicitly).

Idea, not yet scoped in detail: Snowflake (via `snowflake-connector-
python`, itself SQLAlchemy-compatible — likely the closer-shaped addition
to today's `sql_client.py` pattern, relational, SQL-queryable) and MongoDB
(via `pymongo` — a genuinely different shape, since flattening documents
into tabular rows for the SQL Server mirror DB is a real design question
of its own, not just a new connection string) as the two named candidates,
with the door left open for others as real engagements call for them.

**Deliberately deferred** — prototyping today only needs the org and
flat-file paths already built. Revisit once a real source system other
than Salesforce or a flat file actually needs migrating from.

## 31. Target-count/scaled mock data generation (not built, builds on #6)

Problem: `generate-mock-data`/`generate-related-mock-data` (#6) always
generate a fixed count specified per run — there's no way to say "keep
generating mock Accounts until the org has 50,000 total" for realistic
bulk-load volume/performance testing (exercising `bulkops`' batching
behavior, making dynamic batch sizing (#15) meaningful to actually tune
against, or stress-testing a target sandbox before a real cutover).

Surfaced reviewing CumulusCI's `generate_and_load_from_yaml` task
directly (cumulusci.readthedocs.io/en/stable/data.html) — it wraps
exactly this: Snowfakery's own `target_number`/`--run-until-records-in-
org` scaling, confirmed directly in Snowfakery's own Python API
(`generate_data(..., target_number=(20, "Employee"), ...)`, already
referenced when building #6's Snowfakery backend) — it re-runs a recipe
as many times as needed to reach a target count for a named object, not
just a hardcoded loop count.

Idea: extend `build_recipe`/`run_recipe` in `snowfakery_data.py` to
optionally accept a target total (e.g. `--target Account=50000` instead
of/alongside `--count`), passing Snowfakery's own `target_number` through
rather than reinventing repeat-until-count logic. Low implementation
cost — Snowfakery already does the heavy lifting; the work here is
CLI/recipe plumbing, not a new generation engine.

## 32. Bulk test-data cleanup by filter — BUILT (`bulkops.py`)

Problem: repeated migration-testing cycles (generate mock data → `bulkops`
insert → validate → reset → repeat) needed a hand-built load table with a
key column to drive `bulkops <Object> delete` — no quick way to purge
previously-inserted test records by a WHERE-clause-style filter. The
motivating evidence was this project's own history: one working session
did the manual query → CSV → purge-table → delete dance **three separate
times** cleaning up the same test org. Originally surfaced reviewing
CumulusCI's `delete_data` task, which does exactly this.

**Built as the roadmap sketched it**: `bulkops <Object> delete --where
"<SOQL WHERE clause>"` (`purge_by_filter()` in `bulkops.py`). Matching
Ids are resolved via `sf.query_all_iter()` (transparent pagination),
materialized into `[schema].[<Object>_Purge]` — an auditable, inspectable
mirror-DB table, consistent with the framework's SQL-centric shape — and
then **delegated to the existing `bulk_op()` delete path**, so dynamic
batch sizing (#15), `BulkOpsLog` activity logging (#14), result writeback
(`<Object>_Purge_Result`), and the Migration Run Book sync hook (#16) all
apply identically to a purge with zero parallel code. Extending `bulkops`
rather than adding a new verb was deliberate: it's the one gated
org-writing entry point, so `.claude/settings.json`'s existing ask-list
rule covers purge mode automatically — a destructive filter delete can
never run without the same explicit human approval as any other org write.

Safety posture, all deliberate:
- **`--dry-run` first**: reports the matched count and sample Ids
  without touching SQL Server or Salesforce — the preview step for a
  destructive command.
- **No delete-everything default**: `--where` is required and never
  defaulted; purging an entire object means writing `"Id != null"`
  yourself, explicitly and on purpose.
- **Zero matches short-circuit**: nothing is sent to the API, reported
  plainly rather than submitting an empty job.
- **No hard-delete (v1 non-goal, not a gap)**: CumulusCI offers a
  Recycle-Bin-bypassing hard delete behind its own org permission; a
  standard, Recycle-Bin-recoverable delete is the right default for a
  *cleanup* command, where "oops, wrong filter" should be survivable.

**Verified live** (D360_PLAYGROUND): 5 mock Accounts inserted, `--dry-run`
reported matched=5 + sample Ids with the org untouched, the real purge
deleted 5/5 through the normal path (batch rationale printed, BulkOpsLog
row written, `_Purge`/`_Purge_Result` tables produced), post-purge SOQL
count = 0, a no-match filter returned the zero-summary without an API
call, and all four CLI misuse combinations (`--where` with insert, delete
with neither source, both at once, `--dry-run` without `--where`) produce
clear usage errors.

## 33. Scratch org lifecycle + auto-seeded test data (not built, deliberately deferred)

Raised directly: should this framework take on any scratch-org-related
functionality, the way CumulusCI does (`dev_org`/`qa_org` flows that
auto-load sample datasets into freshly created scratch orgs via
`capture_sample_data`/`load_sample_data`)?

This framework currently assumes an org already exists and is authed
(`sf org login web`) — it has no concept of creating, deleting, or
refreshing a scratch org itself, which is a genuinely different
capability area, not an incremental extension of anything built so far.

Idea, not yet scoped in detail: wrap `sf org create scratch`/`sf org
delete` for a "spin up a clean, disposable test org on demand" workflow,
then auto-load mock data (built via this framework's own
`generate-mock-data`/`generate-related-mock-data`, #6) into it via a
lightweight `bulkops` call — built entirely on this framework's own
tooling, not a CumulusCI dependency. Scratch orgs are lower-risk than a
real sandbox (ephemeral, Dev Hub-scoped, easy to throw away), but hard
rules 2 and 9 (org/auth confirmation, Email Deliverability attestation)
still apply the moment `bulkops` touches one — a scratch org is still a
real org from the API's point of view, not a special case.

**Deliberately deferred** — this is a new capability surface (org
lifecycle management), not something to bolt onto the existing
single-org-assumed model without dedicated scoping. Revisit if/when
disposable, pre-seeded test orgs become a real recurring need rather
than a nice-to-have.

## 34. Relationship-consistent subset replication (not built, builds on #2)

Problem: `replicate` pulls each object independently (optionally
filtered by `--where`), with no way to say "pull a representative slice
of Account and only the Contacts/Opportunities/Cases that actually
belong to that slice." A scoped or phased migration rehearsal (e.g.
"migrate the first 50 pilot Accounts and everything genuinely related to
them") currently requires hand-writing consistent `--where` clauses
across every object, with real risk of an orphaned child row if the
filters don't line up exactly.

Surfaced reviewing CumulusCI's `capture_sample_data`/
`generate_dataset_mapping` heuristics, which do exactly this for
scratch-org seeding — pick a representative subset while preserving
relationship integrity across objects.

Idea, and arguably the most broadly useful thing surfaced by this
review — not just a testing convenience, genuinely useful for real
phased/pilot migrations: reuse this framework's own
`load_order.build_dependency_edges`/`compute_load_order` (the exact same
dependency graph `analyze-load-order` and `snowfakery_data.py` already
reuse) to replicate a root object's subset first (by `--where` or a
row-count cap), then automatically constrain every child object's
`replicate` call to `WHERE <ParentLookupField> IN (<the root subset's
real Ids>)` — one command producing a genuinely consistent,
relationship-intact subset across the whole object graph, instead of
manually-coordinated per-object `--where` clauses that are easy to get
subtly wrong.

## 35. Relative date shifting utility (not built)

Problem: migrated historical data can carry dates that were meaningful
relative to *when* they were created in the source system, but become
stale or nonsensical relative to a new go-live date in the target — an
`Opportunity.CloseDate` from years ago, or a trial/contract end date
that's already passed, can trip validation rules/Flows in the target org
that assume forward-looking dates, or simply misrepresent the data's
real-world timing once migrated.

Surfaced reviewing CumulusCI's `anchor_date` concept — it keeps relative
date spacing constant in *test* recipes regardless of when they're run.
The pattern worth borrowing here is the same idea applied to *real*
migrated data, not test data.

Idea: a reusable T-SQL function (fits the existing utility-belt pattern
in `sql/functions/`, alongside `AddBulkLoadSortColumn.sql`) that shifts a
batch of date/datetime columns by a computed offset relative to a chosen
anchor date — e.g. "shift every date in this load table so the latest
`CreatedDate` becomes today, preserving every other date's relative
spacing to it." An opt-in transform-time utility, not automatic — a data
architect decides per-object/per-field whether relative-date
preservation is actually the right call for that migration, since some
fields genuinely should stay historically accurate.

## 36. RecordType DeveloperName resolution for cross-org migration (built, hard rule 15)

Problem: a `RecordTypeId` column carried over from a source system (or a
different org entirely) almost never matches the *target* org's real
RecordType Ids — RecordType Ids are org-specific and not portable, unlike
(say) a picklist API name. Migrating a `RecordTypeId` value today means
either hand-building a per-migration Id-mapping table in T-SQL, or —
more commonly — it silently gets dropped or wrong without a data
architect specifically catching it. A common, easy real-migration
mistake, not a hypothetical one.

Surfaced reviewing CumulusCI's data-mapping docs — it resolves this
automatically by `DeveloperName` whenever `RecordTypeId` is in its
mapping. A well-established migration pattern in general, just not built
here yet at the time this was raised.

**Design decision, asked directly**: the idea originally floated two
designs — automatic resolution inside `bulk_op()` (matching CumulusCI's
own approach, the same "resolve to a real Id via a query first" pattern
`_resolve_external_ids_to_sf_id` already established for delete-by-
external-id, #11), or a plain T-SQL reference table the architect JOINs
against directly (matching `AddBulkLoadSortColumn`/
`CheckLoadTableDuplicateKeys`'s convention of a utility the transform
calls explicitly, not new automatic `bulkops` behavior). **Chosen: the
T-SQL reference table** — simpler, at the accepted cost of no built-in
unresolved-value guard; catching an unmatched `DeveloperName` is the
transform's own responsibility (a `LEFT JOIN` surfacing it as a visible
`NULL`, not an `INNER JOIN` silently dropping the row).

**What shipped**: new module `record_types.py`,
`resolve_record_types(sf, engine, object_name, schema="dbo")` — queries
the target org's real `RecordType` rows for the object
(`SELECT Id, DeveloperName, Name, IsActive FROM RecordType WHERE
SobjectType = '<object>'`) and writes them into a shared
`dbo.RecordTypeMap` table (one table across every object in the project,
like `dbo.FieldProfile` — not a `<Object>_Mock`-style per-object table),
replacing only that object's prior rows. Wired up as `cli.py
resolve-record-types <Object>` — read-only against Salesforce, writes
only to the mirror DB, no confirmation gate needed. New **hard rule 15**
requires this before building any transform that populates
`RecordTypeId`, added as a new step in the Standard Workflow (between
confirming target field names and building the transform).

## 37. CLI alternative to Data Cloud's Profile Explorer — BUILT (`data_cloud.py`)

Raised directly: Data Cloud's own Profile Explorer (Setup UI for
browsing Unified Profile data) is genuinely annoying to click through —
pick a Data Space (almost always just "default," but you still have to
pick it every time), then an entity, then an attribute, one at a time,
to see a single unified person/account's actual data.

**Built**: `data-cloud-profile <dataModelName> <filter> [--fields]
[--limit] [--offset] [--orderby]` — the exact same command as #18's
finding #4, since building that already produced this item's real
answer. One shot instead of several clicks — and confirmed live that
**no Data Space parameter is needed in the API at all**, unlike the
Setup UI, which makes you pick one even when "default" is the only
option that exists.

**Unblocked by building a real Identity Resolution ruleset live**: this
playground org (`D360_PLAYGROUND`) had no Identity Resolution configured
at first (confirmed via `data-cloud-status identity-resolution` — zero
rows), so there was no Unified Profile data to test against. Ran a real
one ("Individual Match," `Status: PUBLISHED`) via `data-cloud-status
identity-resolution` polling (`PUBLISHED` → `IN_PROGRESS` → `SUCCESS`)
— 1,052 source Leads in, 1,052 Unified Individuals out
(`ConsolidationRate: 0.0`, meaning none matched as duplicates — expected
for this seed data). That real Unified Individual data
(`UnifiedssotIndividualIndv__dlm`) is what `data-cloud-profile` was
verified against.

## 38. Real-data anonymization for demos/scratch orgs (not built)

Raised directly: a real-migration-adjacent capability distinct from #6's
mock data — take a *real* client org's actual data (via `replicate`,
already built) and scramble the sensitive fields enough to look
realistic without being real, for client demos, scratch-org seeding, or
sales/pre-sales environments where the real volume, shape, and
relationships of a client's data matter but the actual PII can't be
shown. Different problem from #6: that's synthetic data from scratch;
this is real data with sensitive values *replaced*, keeping the same
row count, distribution, and (critically) relationships intact — the
same Contact should scramble to the same fake name every time, not a
different one per query, so a demo stays internally consistent.

**Correcting an assumption before scoping further**: CumulusCI does
**not** appear to have a built-in anonymization feature either (called
out explicitly as a gap during this same review pass, #6's writeup) —
so this isn't "adopt a CumulusCI capability," it's a genuinely new
build, even though CumulusCI's ecosystem (Faker, Snowfakery) is exactly
the toolkit that would do the actual value-scrambling. The reusable
building blocks already exist in this repo: `replicate.py` for the real
extraction, and the same describe()-driven field-type → Faker-provider
mapping already built twice (`mock_data.py`'s `_mockaroo_field`,
`snowfakery_data.py`'s `_snowfakery_field`) — a third variant here would
replace an *existing* real value with a fake one of the same shape
(name→name, email→email, phone→phone), keyed deterministically per
source row (e.g. a hash of the real value or record Id as the Faker
seed) so the same input always scrambles to the same output across
re-runs, rather than generating brand-new independent rows.

Ties into #33 (scratch org lifecycle) as a second seeding option once
both exist — a scratch org auto-seeded with scrambled *real* data
(realistic volume/shape) rather than purely synthetic mock data, for
whichever a given demo actually needs.

## 39. Ticket system (JIRA or equivalent) read/comment integration (not built, needs API research)

Raised directly, off the Migration Run Book's (#16) header getting a link to the
ticket system's project: today that link is just a static URL a human
clicks through to. The actual idea is deeper — being able to *read and
update* a specific ticket's comments from here (post a comment to a JIRA
story/bug directly, e.g. "load completed, 4,982/5,000 rows, 18 errors —
see Migration Run Book tab UAT"), plus cross-referencing GitHub commits/PRs tied to
that same ticket, so the ticket, the code that closed it, and the
migration run that used it are all visible from one place.

Idea, not yet scoped: JIRA's REST API (`/rest/api/3/issue/{key}/comment`
for posting, `/rest/api/3/issue/{key}` for reading) would need a new
credential type (API token + base URL) — document in
`docs/SECURITY_OVERVIEW.md` *if and when* this gets built, per that file's
own "update alongside any change that adds a credential type" convention.
The GitHub side likely means either searching commit messages/PRs for a
ticket key via GitHub's own API, or relying on an existing Atlassian-
GitHub smart-commit integration if the org already has one configured —
needs research before committing to an approach. Generalizes the same way
Hard Rule 10's ticket-comment convention does: "JIRA" is the assumed
default, but whatever system a given engagement actually uses should slot
into the same shape.

## 40. Configuration Workbook drift detection (not built, blocked on a template)

Raised directly, off building the Migration Run Book's (#16) header: many
teams keep a separate "Configuration Workbook" — a spreadsheet developers
already use to document what they built (custom fields, automation, etc.)
as they build it. The idea is to read that workbook and cross-check it
against the actual deployed build, catching drift where the documented
config and the real org disagree — the same category of problem
`check-mapping-balance` (#3) already solves for a mapping doc vs. a real
`sql/transformations/*.sql` transform, just for a different document
against different ground truth (the org's live metadata/describe(), not
a SQL file).

**Blocked on a real example** — same pattern already used for the run
book before its template was described directly: drop a real Configuration
Workbook into `_stage/`, reviewed for structure/format only (column names,
what it tracks), never content, before designing the comparison logic.
Don't scope this further until that template exists to react to.

## 41. Per-object record counts via the recordCount API — BUILT (`metadata.py`)

Raised directly: Salesforce's `/limits/recordCount` REST resource returns
every requested object's record count in a single HTTP call, instead of a
SOQL `SELECT COUNT()` per object — confirmed against Salesforce's own REST
API docs (not assumed, per this repo's post-training-cutoff rule): GET
`{base_url}limits/recordCount?sObjects=Account,Contact,...` (omit
`sObjects` for every object in the org), API v40.0+ (this org runs v67.0),
needs "View Setup and Configuration."

`record_counts(sf, object_names=None)` in `metadata.py` wraps it directly
via `requests` (the same raw-REST pattern `data_cloud.py` already
established) — no new dependency. `record-counts <Objects...>`/
`--all-objects` is the CLI command; `--all-objects` is opt-in rather than
the default (an unfiltered response can be huge for a real org — confirmed
live: ~90 objects back for a fresh Trailhead Playground with essentially
no custom data yet).

**Review follow-up (2026-07-09 full repo review)**: the initial
implementation shipped without a `timeout=` on its `requests.get` -- a
regression against this repo's own no-timeoutless-HTTP standard (every
call in `data_cloud.py`/`mock_data.py` has one, added in an earlier review
pass precisely because `requests`' default is to wait forever). Fixed.

**The critical caveat, confirmed live, not just quoted from docs**:
Salesforce's own documentation calls this "a cached snapshot in time that
may not accurately represent the number of records," and testing this
directly proved it, concretely: inserted 3 real Accounts, confirmed via
`SELECT COUNT(Id) FROM Account` that they genuinely existed (returned 3),
then called `record-counts Account` immediately after — it came back
completely empty (the API appears to omit zero-and-stale-cached objects
from the response rather than returning `count: 0`). **This means the
API is unsuitable for the specific "validate a load I just ran actually
landed its rows" use case** raised alongside this request — that already
has an authoritative path (`profile_salesforce_object()`'s own
`COUNT(Id)`, deliberately left untouched, or a direct `query` COUNT()),
and this roadmap item doesn't replace it. What this genuinely is good
for: a fast, cheap **rough triage** across many objects at once (e.g.
"how big are these 50 objects, roughly, before deciding what to profile
deeply") where a several-minutes-stale cache doesn't matter. Also excludes
deleted/archived records and associated objects (`History`/`Feed`/`Share`/
`ChangeEvent`).

## 42. Unit tests + CI for the pure-logic modules (built)

Raised by the 2026-07-09 full repo review: every verification in this
project is live and manual — thorough and well-documented in this file's
own BUILT write-ups, but unrepeatable, and nothing protects a future
collaborator (or a future refactor) from silently breaking logic that was
only ever verified once by hand. The same review found bugs that a small
test suite would have caught mechanically: the run-book sync's
Order-vs-OrderItem substring false-positive, the template's 17-cells-vs-
16-columns drift, and the openpyxl `cell(value=None)` no-op (bitten
*three separate times* this project — it's this codebase's single most
repeated gotcha).

Scoped to the pure-logic, no-org-required surfaces, matching the review's
own framing — nothing here needs a live SQL Server connection or
Salesforce org, which is what keeps the CI job runnable on a bare GitHub
Actions runner:
- `batch_advisor._ladder_index`/`_step`/`_seed_lookup` — ladder math and
  rung stepping, using the real committed `reference/batch_size_
  heuristics.json`.
- `load_order.compute_load_order`/`_group_cycle_members` — topological
  sort, self-reference detection, and unresolved-cycle grouping.
- `migration_run_book._object_matches`/`_is_separator_row`/
  `_parse_template` — including the exact Order-vs-OrderItem regression
  case as a named test, plus the header/cell-count drift protection.
- `mapping_doc.extract_insert_columns`/`_safe_sheet_name` — INSERT INTO
  regex matching (case-insensitivity, bracket-stripping, table-name
  selection) and Excel sheet-name sanitizing.
- `auto_mapper._normalize`/`_match_target` — name normalization (`__c`
  stripping) and exact/thesaurus/fuzzy/no-match resolution.
- `metadata.validate_external_id_field` (new in #50) — tested against a
  small stub object exposing `.describe()`, no real org needed.

43 test cases total (`tests/test_*.py`), all passing. `.github/workflows/
tests.yml` runs them on every push/PR: checkout, Python 3.11, an
`apt-get install unixodbc` step (defensive — `pyodbc`'s wheel dynamically
links `libodbc.so.2` at import time, which a bare `ubuntu-latest` runner
doesn't ship), `pip install -r requirements.txt`, then `pytest tests/ -v`.
Live end-to-end verification against a real org stays the standard for
the org-touching paths (that's a genuine strength of this project's
process, not something tests replace) — this covers the logic underneath
it.

## 43. Salesforce GraphQL API (researched — not pursued, out of scope)

Asked directly: what could this framework do with Salesforce's GraphQL
API? Researched against Salesforce's own current docs and Developer
Relations content, not assumed — GraphQL mutations were only added
Spring '26, after this session's training cutoff, so this genuinely
needed checking rather than recalling.

**What it actually offers**: a single `POST
.../services/data/v{version}/graphql` endpoint returning nested
parent-to-child data in one call (e.g. an `Account` with its related
`Contacts` in one response, each scalar field wrapped in `{ value: ... }`
rather than a flat row), aggregate functions (`avg`/`count`/
`countDistinct`/`min`/`max`/`sum`, with or without `groupBy`), and — new
this Spring — mutations (`insert`/`update`/`delete` via the `Mutation`
operation type). Its real selling point, per Salesforce's own framing,
is cutting REST round-trips for apps (especially LWC, which has a
dedicated wire adapter for it) that would otherwise make several
separate calls.

**Measured against this framework's actual scope (see "Scope" at the top
of this file), not against "is the API interesting"**:
- **Bulk extraction** (`replicate.py`): wants flat, independent per-object
  rows to land in SQL Server tables for T-SQL to join/transform later.
  GraphQL's nested `edges → node → { value }` response shape would need
  *more* flattening work to become tabular than SOQL's already-flat REST
  response — a regression for this specific job, not an improvement.
- **Related-record lookups** (`query`/`query_tool.py`): GraphQL's
  headline "parent + children in one call" benefit is something plain
  SOQL already does today via subqueries (`SELECT Id, (SELECT Id FROM
  Contacts) FROM Account`) — the specific advantage GraphQL advertises
  isn't actually a gap in what this framework already has.
- **Bulk DML** (`bulkops.py`): GraphQL mutations are shaped for
  single/small-batch writes (an LWC saving one record), not the
  high-volume batch DML a real migration load needs — Bulk API 2.0 stays
  the right tool for that, unchanged.

**Conclusion**: no gap in this framework's actual data-movement or
remediation needs that GraphQL fills better than what's already built.
Recorded here specifically so it isn't re-researched or re-proposed
without this reasoning being visible first — the "Scope" section above
is the general version of this same judgment call.

## 44. Native database connectors (SQL Server / MongoDB) as the Data Cloud source (not built, needs research)

Redirected here directly off #22's dead end: rather than push data *to*
Data Cloud via an API from this framework's own code, use Data Cloud's
own native database connector types (SQL Server, MongoDB, and whatever
else is available in this org's connector list — the user confirmed
these show up as real connector options alongside S3/SFTP/Ingestion API)
so Data Cloud *pulls* from the mirror DB (or a MongoDB instance) directly
as a real, schedulable Data Stream — closer to how a production data
source would actually feed Data Cloud, and no custom ingestion code
needed on this framework's side at all.

Needs its own research pass before scoping further: what connection info
a SQL Server connector actually needs (does it require inbound network
access to the local mirror DB from Salesforce's side — a public
endpoint, a secure agent/tunnel? — given `SF_Migration` is a local/on-prem
instance today per `docs/SECURITY_OVERVIEW.md` §1), what a MongoDB
connector needs by comparison, refresh/schedule behavior versus an
on-demand trigger, and whether this framework's role becomes just
"prepare well-shaped tables for the connector to find" (mock data,
transformed staging tables) rather than any ingestion code at all. Given
`docs/SECURITY_OVERVIEW.md` already treats "no listening network port"
as a stated trust-model fact (§7) about this framework itself, a real
inbound-reachable SQL Server requirement on Data Cloud's side would be a
genuinely new consideration worth surfacing there too if this gets built.

**Checked `forcedotcom/sf-skills` — this one is a genuine gap, not
redundant.** `data360-connect` manages *existing* connections/connectors
(discovery, testing, browsing) — it doesn't add a new native connector
*type*. Building SQL-Server-as-a-Data-Cloud-source specifically is still
this item's own, real work; the official skill is prior art for the
*workflow* (how connector setup/testing is normally scripted), not a
substitute for the missing connector itself.

## 45. Data Transform authoring as code (researched, real progress — blocked on more real examples)

Raised directly, alongside the same pain point for Calculated Insights
(#24) and field mapping (#21): building a Data Transform by hand in Data
Cloud's drag-and-drop canvas is slow, and the goal is to generate its
definition programmatically instead — write the transform as code, hand
over something ready to drop in, the same spirit `auto_mapper.py` and
`snowfakery_data.py`'s recipe-builder already apply elsewhere in this
framework.

**Confirmed real, not assumed — the export/import round-trip works.**
The user confirmed directly (has done it many times as a DT backup
mechanism): a Data Transform can be exported to JSON and re-imported.
Import requires a container to import *into* — either **Create New** or
**open an existing DT** — and then Upload **overwrites** whatever's
already there. So the realistic workflow is a small, bounded manual
bookend (create or open a DT) with the entire body fully scripted after
that — not literally zero-touch, but close, and still a large win over
building the whole thing by hand.

**The JSON shape, from one real example** (reviewed for structure only —
generalized here, the actual field/object names in that export were
client-specific and aren't reproduced): top-level `version` (API version)
+ `nodes` + `ui`. `nodes` is a DAG — each entry has an `action`,
action-specific `parameters`, and `sources` (upstream node names, the
dependency edges). Three action types confirmed directly: `load` (pull a
DMO/DLO by name with an explicit field list — just a field list, the same
shape `describe()` already gives this framework for CRM objects),
`formula` (adds computed fields; `expressionType: "SQL"` — the *same*
SQL-flavored authoring surface DMQL already uses for Calculated Insights,
confirmed live in #18 — a real internal-consistency signal, not a
coincidence), and `outputD360` (a flat `sourceField`/`targetField`
mapping array to write into a target DLO — structurally identical to
what `auto_mapper.py` already generates for CRM field mapping, just a
different target). `ui` holds node position/label/connector-line data for
the canvas — confirmed by the user to encode literal layout coordinates,
cosmetic/rendering-only rather than semantically required, but still a
real requirement for the humans who'll review anything generated: a
degenerate `ui` block would import fine but look wrong on screen.

**No public schema reference or example library exists.** Searched
directly — nothing on developer.salesforce.com, no GitHub examples repo,
no sample gallery for this specific JSON format. It appears to be an
internal/undocumented format Salesforce doesn't formally publish a spec
for. The org's own real exports are the best available source of truth,
not a stand-in for missing documentation.

**Salesforce's own Trailhead documentation for the underlying node
builder gives real, detailed ground**, cross-referenced against the one
confirmed example rather than taken alone. Eleven node types documented,
each with real UI-configurable options:

| Node | Purpose | Configurable options |
|---|---|---|
| Data Source | Load a DMO/DLO as a starting dataset | Source object, field selection, related-object lookups + aliases |
| Join | Combine two nodes on a related field | Join type (Inner/Left Outer/Right Outer/Outer), two source nodes, join field mapping, output field selection |
| Filter | Keep only matching rows | Source node, filter condition/operator, hardcoded value or input variable, multiple conditions |
| Append | Stack rows from multiple matching-structure nodes | Multiple source nodes, field matching |
| Group and Aggregate | Group + summarize | Group-by fields (Text/Date/Date-Time), aggregation function (sum/avg/count/etc.) |
| Formula | Add a computed field | Field alias, data type, format, the SQL-flavored expression itself |
| Hierarchy | Resolve a parent-child path | Parent field, hierarchy path output |
| Slice | Keep only selected fields, drop the rest | Fields-to-keep list |
| Forecast | Predict future values from history | Source data, time period, historical range |
| Writeback Object | Push results into an object | Target object, operation (create/update/upsert), field mapping |
| Composite Writeback | Coordinate multiple Writeback nodes in one transaction | Container of Writeback nodes |

**A real open question, flagged rather than assumed away**: that
Trailhead content documents the "Data Processing Engine," and it isn't
yet confirmed that's the *identical* builder/schema behind Data Cloud's
Data Transform feature specifically, versus a closely related engine
with partial overlap. This would explain the user's own observation that
"Output has many pieces to manually configure" — there may genuinely be
**two different output concepts**, not one node with many options:
`outputD360` (write to a DLO/DMO, confirmed directly from the real
example) versus "Writeback Object" (reads like it targets a core CRM
object instead — a materially different destination and likely a
different JSON shape).

**Not building generation code yet, deliberately.** Only one real example
has been seen, covering 3 of the 11 documented node types (`load`/
`Data Source`, `formula`/`Formula`, `outputD360`/part of `Output`). Writing
a generator off inference for the other 8 node types (`Join`, `Filter`,
`Append`, `Group and Aggregate`, `Hierarchy`, `Slice`, `Forecast`,
`Writeback Object`, `Composite Writeback`) — and resolving the Output
question above — risks building against a guess rather than a fact,
exactly the mistake #22's research was built to avoid. **Next step**: more
real exported DTs (ideally exercising Join/Filter/Aggregate/Writeback),
reviewed for structure only same as this one, before any generation code
gets written.

**Check `forcedotcom/sf-skills` before gathering more examples the hard
way** — `data360-prepare` explicitly owns "transforms," and
`data360-code-extension-generate` is a full init/run/scan/deploy workflow
for **Python Code Extensions** (custom DLO/DMO transformations) specifically.
Neither is confirmed to solve the exact blocker here (the other 8 DT
canvas node types' JSON shape) — Code Extensions may be a parallel
authoring surface to canvas-based Data Transforms rather than the same
thing wearing a different name — but this is real, current, official
material worth reading closely before spending more effort reverse-
engineering exports by hand. Same external-plugin caveat as #19.

**Confirmed, from reading the full `data360-code-extension-generate`
skill: Code Extensions are a genuinely separate, parallel authoring
surface, not the same JSON format under another name.** No `nodes`/`ui`
canvas DAG at all — instead a Python project (`payload/entrypoint.py`)
against a real SDK (`datacustomcode.Client`: `read_dlo`/`write_to_dlo`/
`read_dmo`/`write_to_dmo`), scaffolded and deployed through the plugin's
own `script init` → `scan` (auto-detects DLO/DMO read/write permissions
from the code itself) → `run` (tests locally against real, not mocked,
Data Cloud data) → `deploy` (needs Docker; ships a versioned, rollback-
able deployment) workflow. Own dependency stack, on top of the `sf
data360` plugin already noted elsewhere: SF CLI plugin
`@salesforce/plugin-data-codeextension`, Python 3.11 specifically, and
the `salesforce-data-customcode` PyPI package.

**Practical implication for this item's actual blocker**: this doesn't
solve "generate the canvas JSON for Join/Filter/Append/Aggregate/
Hierarchy/Slice/Forecast/Writeback" — it sidesteps it. A transform too
complex or too undocumented to safely reverse-engineer from one example
can be written as plain Python instead of guessed-at canvas JSON. Worth
keeping both paths open rather than treating this as the same research
track: keep gathering real DT exports for the canvas-JSON path (per the
"next step" above), but Code Extensions are already a viable escape
hatch today, with a real, documented workflow, for anything currently
blocked on missing canvas node examples.

## 46. Source directory ingestion + cross-pass structure validation (built)

Raised directly as the actual start of a real project: a client hands
over a directory of CSV files (or this is a later pass — e.g. a UAT
reload — of a directory shaped like one seen before). Nothing read a whole
directory at once and turned it into a Source SQL Server database in one
step; `import-parquet` (#12) only ever handled one file at a time.

**Design pivot from the original idea, based on a real, separate client
engagement's proven convention** (reviewed for technique only — no
client-specific names, paths, or field names carried in): the original
framing above (extending `import-parquet`'s typed-inference approach from
Parquet's own schema to CSV, "types have to be sniffed") turned out to be
the wrong instinct. A real client's hand-built migration scripts
consistently stage every CSV column as `NVARCHAR(MAX)` via `BULK INSERT`
and type/transform it later via T-SQL — deliberately never sniffing types
off ambiguous CSV text (a leading-zero id, an ambiguous date format, a
numeric-looking string are exactly what naive inference gets wrong). That
matches this framework's own established philosophy (`replicate.py`
already needs an explicit `type_map.py` coercion step for Bulk API 2.0's
text CSV extracts, rather than inferring) more closely than the original
idea did — real precedent overriding a speculative earlier framing.

**What shipped** (`source_ingestion.py`, `cli.py import-csv-directory`):
- **New file**: derive the table name from the sanitized filename, read
  only the CSV's header row (column names, no data scan), generate a
  numbered `BULK INSERT` script under `sql/source_ingestion/` — git-
  committed, human-readable, independently `sqlcmd -i`-runnable, the real
  artifact of record for the project (hard rule 10 — `--ticket` required).
- **Existing file, later pass**: the script is **reused unchanged, never
  silently regenerated**. Its current CSV's header is checked against the
  script's declared column list before anything loads — comparing the
  **full ordered list, not just set membership**, since `BULK INSERT` maps
  columns positionally, so a same-name column reorder is exactly as
  dangerous as a rename and has to be caught the same way. Any drift hard-
  stops *that file* (the rest of the directory's batch still proceeds) —
  only `--rebuild <table>` explicitly regenerates the script, always a
  deliberate architect decision, never automatic.
- **Bulk by design**: one directory, one command, however many files —
  the actual ask ("dozens of files... be prepared for this to be a bulk
  process").
- **Timed and auditable**: an opt-in `SourceIngestionLog` (same
  `enable-bulkops-logging`-style convention) records every run — including
  a drift-blocked one, with the exact diff — and syncs into the Migration
  Run Book's existing **Pre-Migration** phase (not "Source Download and
  Load Steps" as originally assumed; corrected directly by the user).
  `migration_run_book.py`'s phase-matching helpers were generalized to a
  `phase_prefix` parameter so this reuses the same fill-placeholder-or-
  insert sync mechanism `sync_run_book_from_log` already established for
  the Load phase, with its own independent watermark so the two syncs
  never interfere.

## 47. Pass-aware mapping/profiling workflow state (built)

Raised directly: mapping and profiling are **first-pass** activities,
not repeated every time. A second or third pass (UAT, a mock go-live,
etc.) means *reviewing and polishing* the existing mapping doc against
newly-arrived source data — confirming it's still accurate — not
generating a new one from scratch, and profiling (#7) by default only
happens once unless the architect explicitly asks for it again.

**Key finding from building this: no new state table was needed.**
"Has this object's mapping already been done for this project" already
existed implicitly — `dbo.FieldProfile.AnalyzedDate` (set by every
`profile-salesforce`/`profile-sql-table` run) and
`dbo.SourceRegistry.AutoMappedDate` (already upserted by every `auto-map`
run) — it just wasn't ever *consulted* to change default behavior. A much
smaller fix than inventing new tracking.

**What shipped**: `profiling.is_already_profiled()` and
`auto_mapper.was_already_auto_mapped()`, each a cheap read of the existing
timestamp. `profile-salesforce`/`profile-sql-table` now skip re-profiling
by default when one already exists for that object/table in the schema
(printing the date, still showing the current profile preview) —
`--reprofile` forces a refresh. `auto-map` checks the state *before*
calling `suggest_mappings()` (so the check reflects prior runs, not this
one) and frames a second pass as a review — "N field(s) already decided by
a human, M still blank, freshly suggested" — instead of the first-pass
summary. The underlying safety net (`apply_auto_map_suggestions()` never
overwriting a human-filled Target field) is unchanged either way; only the
console framing differs.

## 48. Auto-map autonomy boundary (real vs. mock data) + learning feedback loop, gated behind explicit consent (not built, builds on #10; boundary is now Hard Rule 11)

Raised directly, and it turned out to be a bigger, more foundational
point than "gate the synonym-learning loop" — it's the actual autonomy
boundary for auto-mapping (and any similar first-draft-generation tool)
itself, now **Hard Rule 11** in `CLAUDE.md`, not just a note here:

- **Real client data**: mapping is iterative and workshop-driven with the
  client, humans are always in the loop, and this framework's job is to
  *speed that up*, not replace it — profile, document, auto-map, add
  notes, then stop. A human takes that first pass and polishes it. Only
  once *they've* finished does anything move further. No exceptions, no
  autonomous "finishing" of a real mapping.
- **Mock/test data this framework generated itself** (`generate-mock-
  data`/`generate-related-mock-data`): the ground truth is already known
  (we made it up), so a mapping *can* be carried all the way to complete
  autonomously — for practice, testing new tooling, and dogfooding
  ("we have to build it before we can dogfood it"). This is the
  deliberate, narrow exception, never extended to a real engagement.

The **narrower piece this item was originally about** still stands as a
real idea layered on top of that boundary: after a human finishes a real
mapping, their corrections are learning that could improve `reference/
field_synonyms.json` for every future migration — the **one** exception
to "most of what happens on a real engagement is client-specific and
never touches the shared repo." Design constraints, stated directly and
non-negotiable:
- **Never shared without asking, every single time** — not a
  once-per-architect standing preference, a fresh, explicit question
  each migration: "this mapping session taught us these things — want to
  contribute them to the shared thesaurus?"
- **Default is no.** Silence or a "no" means nothing leaves this project.
- **If yes, still never auto-commits.** Same "git is truth, a human
  merges deliberately" principle `suggest-batch-heuristics` (#15) already
  established for the batch-size knowledge base — candidate synonym
  additions get staged somewhere durable and reviewable (there's
  explicitly **no SQL Server session backing this decision point**, per
  the user directly — the learning has to be captured in a form that
  survives to be deployed later, not dependent on the live project
  database still existing), not written into `reference/field_synonyms.
  json` directly.

## 49. Migrate-flagged-but-unmapped field detection + describe()-driven suggestion (built, refines #3/#10)

Partially covered already — `check-mapping-balance` (#3) already flags a
transform that populates an undocumented field, or documents a field the
transform doesn't populate, and cross-checks both against live
`describe()` for `not_a_real_field`. What it didn't do: catch this **in
the mapping doc itself, before any transform is written** — a row where
`Migrate Data = Yes` but the Target Field cell is still blank.

**What shipped**: `mapping_doc.find_unmapped_required_fields(mapping_path,
object_name)` reads the sheet directly for exactly that gap.
`auto_mapper.py`'s target-lookup-building loop (describe() → createable/
non-compound fields → normalized-name/label dict) was extracted into a
shared `_build_target_lookup()` so the new
`suggest_for_unmapped_required_fields()` reuses the exact same
exact/thesaurus/fuzzy matching `suggest_mappings()` already uses, rather
than duplicating it. Wired up as `cli.py check-required-mappings <Object>
<MappingPath>` — deliberately **read-only**, same spirit as
`check-mapping-balance`: it alerts and suggests, but never writes into
the mapping doc itself (that's `auto-map`'s job, and it already has its
own human-decision protections).

## 50. Migration-key / External ID field validation against live describe() (built, hardens rules 4/7)

Hard rules 4 and 7 (plus `CheckLoadTableDuplicateKeys`) already validate
that a load table's migration-key column is unique and non-null **in SQL
Server** — but nothing confirmed the *target* field it's mapped to is
actually flagged `externalId: true` and `unique: true` in the live org's
own `describe()`. Raised directly, in the strongest terms used in this
whole conversation: "the target will always need to be unique and
external. No exceptions... we should not load until it is fixed."

**Design decision**: the field's own name can't be assumed (`MigrationID
__c` is this project's own convention, not guaranteed to match whatever a
given build team actually created), and the mapping doc has no dedicated
"this is THE migration key" column — `mapping_doc.py`'s own `_HEADERS`/
`fields_in_scope_from_mapping()` only track generic "Migrate Data == Yes"
fields, not which one specifically serves as the key. Rather than invent
a new mapping-doc convention, this follows the codebase's existing
pattern for migration-key info elsewhere: an **explicit parameter**, never
auto-detected (`CheckLoadTableDuplicateKeys '<LoadTable>',
'<MigrationKeyColumn>'`, `bulkops --external-id <field>`).

**What shipped**: `metadata.validate_external_id_field(sf, object_name,
field_name)` — reads live `describe()`, confirms the field exists and is
flagged both `externalId` and `unique`, returning every problem found
(not real / not externalId / not unique) so nothing is silently assumed.
Wired up as `cli.py validate-external-id <Object> <Field>` (read-only, no
confirmation needed, exits nonzero on failure so it can gate a script) and
`/validate-external-id`. New **hard rule 12** requires this check before
any `bulkops insert`/`upsert`/external-id-resolved delete, inserted into
the Standard Workflow between the Sort (rule 6) and Dupe-check (rule 7)
steps. Explicitly **not this framework's job to create that field if it's
missing** — that's a different team's responsibility; this is a
pre-flight gate that blocks a load until someone else has fixed it, not a
tool that fixes it itself.

## 51. Reference-record pull/compare tool for architect-provided known-good Ids (built)

Raised directly: sometimes an architect creates a record by hand through
the Salesforce UI (to see how the org's real automation shapes a record)
and can hand over its Id for review. Already possible today in an ad hoc
way via `query` — the gap was a dedicated command that pulls that record
and **diffs it field-by-field against what this project's own load
script would have produced**, instead of a human eyeballing two field
lists side by side every time.

**Design decision**: the Load table's own `Id` column (`bulk_op()`'s
writeback) only ever gets populated for records actually loaded through
`bulkops` — a hand-created reference record was never loaded, so it can't
be matched by `Id`. It's matched by the **migration key** instead (e.g.
`Legacy_Id__c`), read directly off the live record rather than asked for
separately — the architect only needs to have set that field when
creating the record by hand, which is a natural, deliberate thing to do
specifically to enable this comparison.

**What shipped**: new module `reference_record.py`,
`compare_reference_record(sf, engine, object_name, load_table, record_id,
migration_key_field, ...)` — reads the Load table's real columns
(`INFORMATION_SCHEMA.COLUMNS`, same pattern as
`mapping_doc.generate_mapping_workbook`), validates every one against
live `describe()` first (same pre-flight discipline `bulk_op()` already
uses, applied here to a read), pulls the live record, extracts the
migration key's value, finds the matching Load table row, and diffs field
by field. Wired up as `cli.py compare-reference-record <Object>
<LoadTable> <RecordId> --migration-key <Field>` — read-only, a review/
debugging aid; never writes anything back.

## 52. Mermaid process-flow diagrams from the Migration Run Book — BUILT (`migration_run_book.py`)

Generates a Mermaid flowchart from a Migration Run Book tab's own
structure (phases → steps → dependencies, straight off the Stage/Object/
Dependency columns #16 already tracks) as a `.md` file. Deliberately
simple for v1, per the user's own framing — "for now, you would just
create mermaid" — emits the Mermaid syntax itself and stops there; GitHub
(and most modern Markdown renderers) already render ` ```mermaid ` code
fences as real diagrams natively, no additional tooling required to get
a visual result out of this. Lucid Chart itself supports importing
Mermaid syntax directly (paste-to-import), so plain Mermaid is also
already the right foundation for handing a diagram to Lucid later,
without needing to build a direct Lucid API integration to get value
from this. Building/saving a *polished*, styled diagram elsewhere remains
a named future stretch, explicitly not part of this item.

`generate_run_book_flowchart(path, tab_name)` in `migration_run_book.py`
(`cli.py generate-run-book-flowchart`) reads the tab's own banner rows
(phase boundaries) and data rows the exact same way
`_iter_load_phase_rows()` already does elsewhere in that module — one
`subgraph` per phase, one node per step labeled from the Object column.
Edges come only from the Dependency column's real "After: X, Y" text
(the shape `_load_order_rows()` itself writes for the Load phase) —
never fabricated top-to-bottom chaining for phases with no known
dependency (Pre-/Post-Migration items render as standalone nodes, which
is honest: the Run Book genuinely doesn't know their order). A parent
name is resolved against every other row's Object value via
`script_numbering.matches_token()` — the same whole-token match already
used to resolve a real script filename against a bare object name
elsewhere in this module, since a Load-phase Object cell is often a
script filename ("010_account_load.sql"), not the bare name a Dependency
cell names ("After: Account"). An unresolved dependency mention (no
matching row in this tab) is dropped, not guessed at, and reported back
in the summary dict rather than silently disappearing — same "visible
gap, not a silent guess" philosophy as #36's unmatched-`DeveloperName`
NULL. Node color reuses the workbook's own Status conditional-formatting
palette (Not Started/In Process/Completed/Issue/N/A), so the diagram
agrees visually with the spreadsheet instead of inventing a second
meaning for color. Read-only, no Salesforce/SQL connection needed — just
the local `.xlsx` file — so it's safe to run without confirmation.

Found in a later ruthless-review pass: a non-blank Dependency cell that
doesn't match the "After: X" shape at all (a plausible hand-filled
free-text note on a Pre-/Post-Migration row) used to be silently
indistinguishable from a genuine "no dependency" row — both produced an
empty parent list with no signal either way. `_is_unparseable_dependency_note()`
now catches this case specifically, surfaced in the summary dict as
`unparsed_dependency_notes` — kept distinct from `unresolved_dependencies`
(which means "found a real 'After:' mention, just no matching row"),
since these two represent genuinely different gaps.

## 53. Supervised end-to-end load orchestrator — Phase 1 built, Phase 2 gated on a real UAT pass

Full design lives in `docs/ORCHESTRATOR_DESIGN.md` (built collaboratively,
per the original ask below — not scoped solo). All five open design
questions there are resolved. Real constraints that narrow this a lot
from "automate the whole thing," confirmed directly and unchanged since
the original design pass:

- **UAT and PROD passes only.** Not dev, not earlier test iterations —
  those stay exactly as manual and per-step-confirmed as they are today,
  unaffected by this item. Full orchestration is specifically for the
  later, higher-stakes passes where the sequence is already well-worn.
- **An aspiration to earn over many projects, not a switch to flip.**
  Stated directly: "It is a dream to do this... but the orchestrator
  isn't going to be something we just do every time... has to be tested
  over many projects." This gets built and trusted incrementally, not
  shipped and turned on. Graduation bar: 3 consecutive clean passes per
  stage (design doc's Graduation Numbers question, resolved).
- **Bias to stop, hard.** "You should never just plow ahead when we get
  to UAT and production loads... caution should be that you stop and ask
  if things are looking off and we don't have enough info." The stated
  cost asymmetry is explicit and drives every design choice here:
  **backing data out of a live org is worse than waiting for approval.**
  A false pause costs a little time; a false continue can cost a
  backout-and-redo cycle in production. When genuinely unsure which way
  to round, round toward stopping.
- **This still runs against Hard Rule 2** (the Live-Org Write
  Confirmation Rule — confirm before every `bulkops` call, enforced today
  as a per-invocation approval gate) — approving an entire UAT/PROD run
  up front, then proceeding through multiple objects/batches without
  re-confirming each one, is a genuine, deliberate loosening of that rule
  for this specific, narrow case, not a blanket change to how `bulkops`
  behaves everywhere.

**Phase 1 — built, tested, live-validated (2026-07-12).** The
deterministic tier-assessment logic (`orchestrator.py`'s `assess_tier()`
— Tier 1 Continue Silently, Tier 2 Continue with Warning, Tier 3 Pause
and Ask, Tier 4 Full Stop), `reference/orchestrator_thresholds.json`,
`bulk_op()`'s `failure_error_counts` addition, `cli.py orchestrator-assess`,
and opt-in `OrchestratorRunEvent` shadow-mode logging all exist and pass
24+ unit tests. Live-validated against this project's own real
`BulkOpsLog` history across all four tiers — including a deliberately
constructed test that produced real Tier 2 and Tier 3 outcomes, and
found (then fixed) a genuine gap in the elapsed-time trigger where Bulk
API 2.0's fixed per-job overhead made small clean batches look
"slower per row" than large ones. **Zero change to Hard Rule 2** — every
`bulkops` call is exactly as `ask`-gated as before; Phase 1 only observes
and reports after the fact.

**Phase 2 — not started, gated on a real UAT pass.** The actual
coarse-approval mechanism (`bulkops-under-plan`, a PreToolUse hook,
`orchestrator-approve`, `dbo.OrchestratorRunPlan`,
`reference/orchestrator_trust_ladder.json`, the new CLAUDE.md Hard Rule
for the narrow Hard-Rule-2 exception, and the `docs/SECURITY_OVERVIEW.md`
update for the hook as a new trust boundary) doesn't exist yet, and
shouldn't until Stage 1 shadow mode has actually run against a real
UAT-tier project — everything done so far has been Dev-tier dogfooding,
permanently out of this design's scope. See `docs/ORCHESTRATOR_DESIGN.md`
section 5 (deferred items) for the full list.

## 54. Chat-driven human-in-the-loop alerting/control — Slack/Teams (not built — roadmap idea per explicit request)

Two distinct capabilities worth keeping separate, raised directly
("I would love more than an email... that would be a cool feature to
turn Slack into an interface... Put that as a roadmap idea to
consider"):

1. **Outbound alerting** — push a notification to Slack/Teams instead of
   (or alongside) email when something needs the architect's attention
   (a batch failed, a run finished, a decision is needed). Low-risk, a
   webhook POST, no new trust boundary.
2. **Bidirectional chat-driven control** — the more ambitious version:
   the architect drives a production migration run *from* Slack instead
   of a terminal session. Real architecture question to flag up front,
   not gloss over: does this need a listening process (a bot subscribed
   to Slack events — an inbound network listener) or can it be done by
   polling (something periodically checks for new messages, no
   listener)? `docs/SECURITY_OVERVIEW.md` §7 states "no network
   listener" as a **current fact** about this framework's trust model,
   and §8 already says adding one requires a full fresh security review,
   not an incremental patch — if capability 2 is ever built via a
   listener, that document needs deliberate revisiting, not quiet
   staleness.

Capability 1 is a much smaller, safer first step and could ship well
before any version of capability 2 is even designed.

## 55. `REF_`-prefixed human-only audit columns, excluded from bulkops (built, hard rule 13)

Raised directly from real DBAmp-era experience: the user's own
established convention is adding `REF_`-prefixed columns to a Load table
for SQL-side human auditing during a build — tracking things that were
never meant to reach Salesforce. Under DBAmp, an unmatched column like
this got a warning but never failed the load. Confirmed this framework's
own pre-flight check (`bulkops.py`'s `_preflight_check`) would instead
treat any `REF_` column as `not_a_real_field` and **abort the whole
call** — the opposite of the desired behavior.

**What shipped**: `bulk_op()` gains `ref_prefix="REF_"` (overridable,
case-insensitive), excluded from the auto-derived `sent` column list in
both the insert and update/upsert branches — the exact same treatment
`id_column`/`error_column`/`key_column` already get. A `REF_` column
therefore never reaches `_preflight_check` (never a false
`not_a_real_field` abort) and never appears in the actual Bulk API
payload. Only applies to the auto-derived list — an explicit
`send_columns` naming a `REF_` column is a deliberate override, never
second-guessed. `cli.py bulkops` gains `--ref-prefix`.

## 56. Duplicate target-field detection — scripts and spreadsheets (built, hard rule 14)

Raised directly: a mapping doc or a transform script could end up
assigning the same target field twice. The exact line to draw, in the
user's own words: it's fine for *different* scripts/sheets to target the
same field (two source systems both feeding `Account.Name`, say) — the
problem is one **single** `CREATE TABLE`/`INSERT INTO` column list, or
one single mapping-doc sheet, naming the same target field twice.

**What shipped**: `check_mapping_balance()` (already parsing exactly the
two pieces needed) gained two new finding categories, captured before
the existing code collapsed either set of names to a `set()` and
discarded the duplicate information:
- `duplicate_target_fields`: `{target_field: [source_field, ...]}` for
  every Target Field API value chosen by more than one row **within one
  sheet**.
- `duplicate_implemented_columns`: column names appearing more than once
  in **one transform's own** `extract_insert_columns()` result.

`cli.py check-mapping-balance` reports both, the column-list one first
(it breaks the actual SQL outright, the softer spreadsheet-level one
doesn't). Also caught at the CSV-ingestion boundary: `source_ingestion.py`
gained `_check_no_duplicate_columns()`, called from
`generate_import_script()` right after reading a CSV's header — a
repeated CSV column name would otherwise fail with a confusing raw SQL
Server "column name … specified more than once" error partway through a
`CREATE TABLE`.

## 57. Data model ERD diagrams — source subject-area models + target model, SDMN-inspired (built)

Requested directly: generate Mermaid ERDs — one or more **source** models
grouped by subject area, plus a **target** model of core + custom
Salesforce objects — styled to approximate Salesforce's own official
**Salesforce Data Model Notation (SDMN)**, importable into Lucid.

**Verified against the real spec before promising anything**
(`developer.salesforce.com`'s SDMN guide — `architect.salesforce.com`'s
reference-diagrams intro 403'd; the Data Cloud data-model overview page
just points back to the same SDMN doc rather than adding its own
conventions): SDMN encodes real information in per-entity fill color and
border style (solid/dashed/dotted/none, indicating license/extension
status) and a **diamond symbol** specifically for master-detail vs a
plain line for lookup vs a curved line for recursive relationships.

**Design evolution — v1 (`erDiagram`) superseded by v2 (`classDiagram`),
same session**: v1 shipped with Mermaid's `erDiagram` and solid/dashed
relationship lines for master-detail/lookup, having concluded per-entity
color coding was unreachable in Mermaid at all. That conclusion was
**wrong for `erDiagram` specifically, not for Mermaid generally** —
discovered by finding `forcedotcom/sf-skills` (Salesforce's own official
Agent Skills library, `github.com/forcedotcom/sf-skills`), whose
`external-diagram-mermaid-generate` skill solves the identical problem
using `flowchart` + `style`/`classDef` to get real per-entity fill color
for Standard/Custom/External objects. Investigating further (their own
skill still uses `erDiagram` for field-level detail, `flowchart` only for
color, an explicit tradeoff in their design) found a genuinely better
single answer: Mermaid's **`classDiagram`** supports attribute lists
*and* `classDef`/`:::` per-class color styling *and* UML composition
(`*--`, filled diamond) vs aggregation (`o--`, hollow diamond) — all
three at once, confirmed directly against Mermaid's own current docs, not
assumed. Composition/aggregation is a closer match to SDMN's own
diamond-on-the-parent-side master-detail convention than either v1's
solid/dashed lines or sf-skills' own thin/thick flowchart arrows. **v2
rebuilt `data_model_diagram.py` around `classDiagram`** rather than
patching v1, and reused sf-skills' own validated Standard/Custom/External
hex palette rather than inventing a new one — no reason to pick different
colors for the same axis someone already tested.

**What shipped**, new module `data_model_diagram.py`:
- **Target model** (`generate_target_model_diagram`) — fully automatable,
  no reimplementation needed: `load_order.build_dependency_edges()`
  already returns real, `describe()`-driven relationships
  (`is_master_detail`/`is_nillable`), reused directly. Attributes default
  to Id/Name/required/reference fields; `--mapping-path` scopes them to
  whatever's actually flagged `Migrate Data = Yes` instead. Each object is
  colored Standard/Custom/External from `describe()`'s own `custom` flag
  and `__x` API-name suffix — also real, not guessed.
- **Source model(s)** (`generate_source_model_diagram`) — staging tables
  carry no FK constraints and no describe()-equivalent metadata, so
  relationships here are a **naming-convention heuristic only** (a
  column matching `<table>_?[Ii]d$` against another table in scope),
  always rendered as the weaker aggregation form and labeled
  `"(guessed)"`, and printed as an explicit review list by the CLI
  command — never presented with the same confidence as the target
  model's real relationships, and never color-coded (no Standard/Custom/
  External axis exists for a plain SQL table). Subject areas are an
  **explicit, human-provided grouping**
  (`--subject-area "Name:Table1,Table2"`, repeatable), never
  auto-clustered — there's no reliable signal to cluster source tables
  on automatically, and guessing domain boundaries on someone else's
  behalf is exactly what this framework avoids.
- **A real bug found and fixed during live testing**: the FK-naming
  heuristic initially labeled *any* column matching the `_id` pattern as
  `FK` in the entity's own attribute list — including a table's own
  primary key (e.g. `account_id` in `SourceAccounts` itself). Fixed by
  adding a genuine SQL Server primary-key lookup
  (`INFORMATION_SCHEMA.TABLE_CONSTRAINTS`/`KEY_COLUMN_USAGE` — real
  ground truth, not a guess) and only labeling `FK` a column that
  actually produced a guessed relationship, not merely one matching the
  naming pattern. Re-verified live after the v2 rewrite, same result.

Both commands write a plain `.md` file with a fenced ` ```mermaid ` block
— same "just emit Mermaid, GitHub/Lucid already handle the rest"
convention #52 sketched (not yet built) for Migration Run Book
flowcharts, no new file format invented. Read-only against
Salesforce/SQL Server either way.

**Relationship to `sf-skills`, not a replacement for it**: their skill is
a general-purpose Salesforce architecture diagrammer (OAuth flows,
sequence diagrams, system landscape, pre-built reference ERDs for
standard clouds) with no concept of a migration project's own source
staging tables, mapping doc, or load-order data — genuinely out of scope
for it, not a gap. This item stays narrow and project-specific on
purpose; no reason to rebuild their general diagramming capability here.

---

## 58. Bidirectional convert between a Data Transform's exported JSON and a Code Extension's Python (not built, depends on #45)

Raised directly, off the back of #45's own research this session:
`data360-code-extension-generate` confirmed Code Extensions are a real,
separate authoring surface for Data Cloud transforms — a Python project
(`payload/entrypoint.py`) against the `datacustomcode` SDK
(`client.read_dlo`/`read_dmo`/`write_to_dlo`/`write_to_dmo`), not the
same JSON format as the drag-and-drop Data Transform canvas wearing a
different name. The idea, extended from a first framing of "JSON →
Python only" to **both directions**: author in whichever surface is more
convenient for the task at hand, then convert to the other — canvas JSON
to a working `entrypoint.py`, or a Code Extension's Python back into a
canvas-importable JSON — instead of being locked into whichever surface
the transform happened to start in.

**The two directions have genuinely different risk profiles — this is
two features sharing one roadmap item, not one feature with a `--reverse`
flag.**

- **JSON → Python (the safer direction, unchanged from the original
  framing).** #45 is stuck generating *into* the canvas JSON format — 8
  of 11 node types still unconfirmed, no public schema reference, real
  risk of guessing wrong. Converting *out of* that JSON into Python
  doesn't carry the same risk for whatever node types *are* already
  confirmed: a `load` node maps mechanically to a
  `client.read_dlo()`/`read_dmo()` call with the same field list, a
  `formula` node's `expressionType: "SQL"` expression to a pandas column
  assignment, `outputD360` to `client.write_to_dlo()`/`write_to_dmo()`
  with the same field mapping. Translating known structure to known SDK
  calls is safer ground than inventing structure to match an undocumented
  format.

- **Python → JSON (the harder direction — inherits #45's original
  blocker, doesn't route around it).** This is generation *into* the
  same undocumented canvas format #45 already flagged as too risky to
  build against from one example — bidirectionality doesn't change that;
  it just means this direction stays gated on the same "more real DT
  exports first" condition #45 is already waiting on, for every node
  type beyond the 3 confirmed. It also adds a second constraint JSON→Python
  doesn't have: arbitrary Python has no canvas equivalent at all — a
  hand-written `entrypoint.py` using pandas/numpy freely can express
  things none of the 11 documented canvas node types can represent. This
  direction can only ever recognize a **constrained subset** of Code
  Extension Python that maps cleanly onto canvas node semantics (a
  `client.read_dlo()` call, a recognizable `.merge()`/`.groupby().agg()`/
  boolean-mask filter, a `client.write_to_dlo()` call at the end) — it
  should say so explicitly and refuse to convert whatever falls outside
  that subset, never silently drop or misrepresent logic the canvas can't
  express.

**Scope this the same way #45 already committed to**: build JSON→Python
for the 3 node types already confirmed from one real example (`load`,
`formula`, `outputD360`) first, ship that as genuinely useful today.
Python→JSON stays research, not implementation, until #45 itself has
enough real examples to trust generating the other 8 node types — the
same "more real examples before more generation code" discipline #45
already applies, not a reason to wait and build nothing on the JSON→Python
side. Either direction's output is a starting point for human review
(JSON→Python before `script scan`/`run`/`deploy`; Python→JSON before
import into a canvas DT), same spirit as `auto_mapper.py`'s mapping
suggestions or `snowfakery_data.py`'s recipe generation — never assumed
correct and deployed/imported unreviewed.

**Open design question, not yet resolved**: whether this ships as real
CLI commands in this repo (`cli.py convert-transform-to-code-extension
transform.json --output payload/` and the reverse, matching this
framework's own established "deterministic generation gets a real
command + slash-command wrapper" convention — #36, #57 both did this) or
as a Claude Skill of its own (a documented conversion workflow, closer to
how `sf-skills`' own `data360-*` family is shaped) — or both, a skill
that wraps the CLI commands the way this repo's existing
`.claude/commands/` already wrap every other verb. Decide when actually
building this, once enough real DT exports exist to know the converter
is worth shipping at all.

## 59. Migration brief intake / project bootstrap — BUILT (`migration_brief.py`)

Raised directly off a description of how this framework actually gets
used: an architect handles client discovery separately (with help from
another AI session — use cases, which objects need migrating, special
requirements), then hands that off to *this* framework to script,
validate, and run. Today that hand-off was a cold start — nothing here
read a discovery output; the architect re-typed the object list into the
first `describe`/`analyze-load-order` call by hand.

`parse_migration_brief()` reads a minimal, deliberately simple YAML file
(not a rigid schema — start empty, grow from real usage, same discipline
as `reference/field_synonyms.json`) a discovery-AI session could produce
directly: objects in scope, a short note per object, the target org
alias, and a ticket/project reference. `bootstrap_project()`
(`cli.py bootstrap-project brief.yaml run_book.xlsx --tab Dev1`) does the
boring, mechanical first pass and nothing more: confirms every named
object is real via live `describe()` (a typo or a renamed object
surfaces immediately as a reported problem, not three commands later —
never silently skipped), runs `analyze-load-order` (#2) across the
objects that ARE real, and scaffolds a Migration Run Book (#16) via
`generate_migration_run_book()` with that object list already wired in.
Deliberately does **not** try to guess mapping, field lists, or
transform logic from the brief's own notes — that's still
`generate-mapping-doc`/`auto-map`'s job, on the real source tables, once
they exist (Hard Rule 11's same first-pass-only scope discipline).

Two things worth calling out beyond the original idea sketch above:

- **Org-alias cross-check.** The brief's `target_org_alias`, when given,
  is compared against this session's *actual* configured org alias
  (`Settings.sf_org_alias`) — a warning, not a hard block, since a brief
  written before the exact alias was finalized is a normal, non-error
  state (Hard Rule 2's spirit: confirm the target org, without
  over-blocking a legitimate early-draft brief).
- **The ticket field doesn't force-fit into the Run Book.**
  `generate_migration_run_book()`'s own `ticket_url`/`ticket_label`
  header fields describe a whole ticket **system** link (e.g. a Jira
  project URL), not one specific ticket number — there's no natural home
  for "this project's ticket is PROJ-123" at that level. Rather than
  misuse those fields, the brief's `ticket` is simply reported back as a
  reminder for the Script Ticket Traceability Rule (#10) once real
  transform scripts get built.

Building this needed `load_order.py`'s own `write_to_sql()` ported off
raw SQL-Server-only T-SQL onto `sql_dialect.py` (same pattern as
`risk_analyzer.py`/`migration_run_book.py`/`mapping_doc.py`/
`mock_data.py`'s own ports) — `analyze_load_order()` needed to be
real-SQLite-testable, and `load_order.py` had zero test coverage for its
database-writing half before this (only the pure `compute_load_order()`/
`_group_cycle_members()` functions had tests). Both are now covered
against a real SQLite engine. Dogfooded live against this project's own
org: confirmed a real object, caught a deliberately-typo'd one, and
scaffolded a real Run Book tab with the correct script filename linked.

## 60. Discovery question checklist generator — BUILT (`discovery_checklist.py`)

The companion to #59, running the other direction: instead of *starting*
from a discovery output, `generate_discovery_checklist()` (`cli.py
generate-discovery-checklist <Objects> [--output path.md]`) generates
the questions an architect should be *asking* during discovery, derived
from what this framework already knows how to check rather than a
generic template a human has to remember:

- `analyze_object_risk()` (`risk_analyzer.py`, #5) already finds active
  validation rules per object — each one becomes a real question naming
  its actual `ErrorDisplayField` and `ErrorMessage` ("confirm source data
  will satisfy 'BillingCity' -- City is required" rather than a generic
  "any validation rules?"). Apex triggers/workflow rules/flows are still
  surfaced as summary counts for context, but don't generate individual
  questions of their own — there's no natural client-facing question a
  count alone implies the way a validation rule's own error message does.
- An object carrying `RecordTypeId` (the RecordType Resolution Rule,
  #15/#36) becomes "Does the client use Record Types on this object? Get
  the exact DeveloperName for each one in scope."
- A reference field pointing at an object **not yet** in the candidate
  list becomes "This object depends on `<Parent>`; confirm it's in scope
  too, or that target records already exist for it" — deliberately the
  *inverse* of what `load_order.py`'s own `build_dependency_edges()`
  tracks (that function only records edges *within* scope, by design),
  so this reads `describe()` directly rather than repurposing that
  function against its own grain. A **polymorphic** field (more than one
  `referenceTo` target — e.g. `Task.WhatId`'s ~90 possible types, see
  `validators/Task.md`) collapses into a single question naming the
  field and a truncated target list, rather than one question per
  target — found via a real full-pipeline dogfood run, not a synthetic
  test: the original flat-target design produced ~90 near-identical
  lines for `WhatId` alone, drowning out every other, genuinely
  actionable question for that object.

Mostly a new presentation layer over data `risk_analyzer.py`/`describe()`
already fetch, not a new integration — the value is turning "what should
I ask" into something derived from the org's actual complexity signals,
not memory or a generic checklist template. Purely read-only against
Salesforce, with **no engine/mirror-DB dependency at all** — a
deliberate design choice, not an oversight: this needs to run during
discovery itself, potentially before the SQL Server side of a project
exists yet, so it can't depend on `dbo.ObjectAutomationRisk` already
being populated by a prior `analyze-org-risk` run — it calls the same
live Tooling API scan directly instead. Plain Markdown output for v1,
same "ship the simple version, decide on polish later" discipline as
#52/#66's own v1 framing — landing questions as starter rows in a
Migration Run Book's Pre-Migration phase instead (or in addition) remains
a future enhancement, not built here. Dogfooded live against this
project's own org: correctly flagged Account's real out-of-scope lookup
dependencies (`DandBCompany`/`OperatingHours`/`User`) when run alone, and
correctly suppressed the `Account` dependency once `Contact` was checked
together with it.

## 61. Bulk-load failure triage assistant — BUILT (`failure_triage.py`)

Builds directly on this session's ruthless-review fix to `bulkops.py`'s
`failure_error_counts` (record-Id tokens normalized to `<ID>` so a
recurring error reads as "known," not "novel," across runs, via
`_normalize_error_signature()`). `triage_failures(engine, table, schema=
"dbo", error_column="Error", object_name=None, mapping_path=None)`
(`cli.py triage-failures <table>`) groups a load's failures by that same
normalized signature and maps well-known Salesforce Bulk API error codes
to a likely root cause and which existing command to run next, instead
of leaving the architect to manually parse raw error strings row by row.
`table` is the same load table (written back in place) or
`<table>_Result` table `bulkops-retry`/`build_retry_table()` already
reads — same calling convention, deliberately, so the two commands slot
into the same post-load workflow.

Guidance is registered per error CODE (`_ERROR_CODE_GUIDANCE`) for
`DUPLICATE_VALUE`, `REQUIRED_FIELD_MISSING`, `STRING_TOO_LONG`,
`INVALID_CROSS_REFERENCE_KEY`, `FIELD_CUSTOM_VALIDATION_EXCEPTION`,
`INVALID_FIELD_FOR_INSERT_UPDATE`, `MALFORMED_ID`, and
`UNABLE_TO_LOCK_ROW` — an unrecognized code still gets a clear "no known
guidance yet" fallback rather than erroring. Two deliberate, disclosed
scope limits versus the original idea sketch above, both explained in
`failure_triage.py`'s own module docstring:

- Field-name extraction is only attempted for `REQUIRED_FIELD_MISSING`'s
  stable "Required fields are missing: `[Field1, Field2]`" bracketed-list
  shape (`_extract_required_fields()`) — every other code gets guidance
  text only, since inventing a field-position regex for a message shape
  not directly confirmed against this project's own live data would be
  exactly the kind of stale-training-data guess `CLAUDE.md` warns against
  for anything Salesforce-API-version-specific.
- `DUPLICATE_VALUE` gets no live cross-reference against
  `dbo.ObjectAutomationRisk` — `analyze-org-risk`/`risk_analyzer.py` only
  ever scans ValidationRule/ApexTrigger/WorkflowRule/ApprovalProcess/
  FlowDefinitionView, never Salesforce's separate DuplicateRule metadata
  type, so there's genuinely nothing on file to check yet (a real,
  disclosed gap, not an oversight — a future item in its own right if
  DuplicateRule scanning ever gets added to `risk_analyzer.py`).

Two real, live cross-references ARE built, both opt-in via optional
arguments (works fine without them, richer with them — same pattern as
`analyze_object_risk()`'s own `fields_in_scope`): `--object` +
`--mapping-path` checks whether a `REQUIRED_FIELD_MISSING` field was
ever chosen as a Target Field in the mapping doc at all
(`_is_field_ever_mapped()` — the reverse question from
`find_unmapped_required_fields()`/#49, which only surfaces source rows,
not "was this target field mapped by anyone"); `--object` alone pulls
`FIELD_CUSTOM_VALIDATION_EXCEPTION` candidates from whichever active
`ValidationRule` rows a prior `analyze-org-risk` run already cached for
that object. Read-only, advisory only — never changes data, never
re-runs `bulkops` — same "suggests, never auto-fixes" posture as
`auto_mapper.py`. Verified via real `bulk_op()` runs against a SQLite
engine (`tests/test_failure_triage.py`), not yet dogfooded against a
live Salesforce failure — there was no real failure sitting in the
mirror DB to point it at when this was built, and manufacturing one
against the live org wasn't judged worth a real write just for a demo.

## 62. Adversarial mock data generation — BUILT (`adversarial_mock_data.py`)

`generate-mock-data`/`generate-related-mock-data` (#6) generate
happy-path data only — every row is well-formed by construction.
`generate_adversarial_mock_data()` (`cli.py generate-adversarial-mock-data
<Object> --count N --scenario scenario:field:rows`, repeatable) is the
deliberate opposite: reuses `mock_data.py`'s own describe()-derived
Mockaroo schema directly, then corrupts a chosen, disjoint slice of rows
per scenario, so a validation-rule collision or pre-flight-check gap
surfaces during Dev testing, not for the first time against real client
data or, worse, during a UAT pass. Five scenarios shipped, each mapped to
one of `triage-failures`' (#61) own known error codes:

- `duplicate_key` — two or more rows share one migration-key value
  (`DUPLICATE_VALUE`).
- `oversized_string` — a value deliberately exceeds the target field's
  real `describe()` length (`STRING_TOO_LONG`).
- `missing_required` — a genuinely required field is left blank
  (`REQUIRED_FIELD_MISSING`) — raises if the named field isn't actually
  required (nillable or defaulted), so a miswired scenario can't silently
  test nothing.
- `invalid_picklist` — a picklist/combobox field gets a value that isn't
  one of its real `picklistValues`.
- `bad_reference` — a reference field (never part of a normal happy-path
  mock run — `mock_data.py` skips references entirely, since there's no
  target Id to point at yet) gets a well-formed-looking, 18-char,
  real-org-guaranteed-nonexistent Id (`INVALID_CROSS_REFERENCE_KEY`).

Writes to `<Object>_Mock_Adversarial` — never `<Object>_Mock`, so this
never mixes into or overwrites the normal happy-path mock table — tagging
every corrupted row's scenario in a `REF_AdversarialScenario` column
(`REF_`-prefixed, hard rule 13, so `bulkops` never sends it to
Salesforce). The same table can go straight into a real, separately-
confirmed `bulkops` call to watch the pipeline handle each provoked
failure for real. Every field/scenario pairing is validated against live
`describe()` before anything is corrupted (wrong field type for the
scenario raises immediately, rather than silently corrupting something
that doesn't test what was asked for).

Building this required porting `mock_data.py`'s own `create_mock_table()`
off raw SQL-Server-only T-SQL onto `sql_dialect.py` (same pattern as
`risk_analyzer.py`/`migration_run_book.py`/`mapping_doc.py`'s own ports)
— `adversarial_mock_data.py` needed it to be real-SQLite-testable, and
this project's own testing convention is a real engine, not a mock. Zero
behavior change against SQL Server: `MssqlDialect.sf_type_to_sql()` calls
the exact same `type_map` function `create_mock_table()` used directly
before. `mock_data.py` had no test coverage at all before this — both it
and the new module are now covered against a real SQLite engine.

Deliberately NOT attempted here, same disclosed gap as `triage-failures`'
own `DUPLICATE_VALUE` limit: deriving a scenario automatically from an
active validation rule's `ErrorDisplayField`. `risk_analyzer.py`'s
`dbo.ObjectAutomationRisk` only persists a `ValidationRule`'s ItemName/
IsActive/Detail (ErrorMessage) today, not `ErrorDisplayField` — nothing
on file yet to build that suggestion from without a second live Tooling
API call or a schema change to that table. A natural follow-up once
`ErrorDisplayField` is persisted there too.

## 63. Reset-dev-cycle command — BUILT (`dev_cycle.py`)

Codifies a ritual this project's own dogfooding did by hand, repeatedly,
across earlier sessions (see `docs/ORCHESTRATOR_DESIGN.md`'s field notes:
"a full reset — org records deleted, scripts/docs/SQLite wiped — before
each of three consecutive full Dev-tier cycles"). `reset_dev_cycle_tables()`
(`cli.py reset-dev-cycle --objects Account Contact ...`) drops every
`_Mock`/`_Mock_Adversarial`/`_Load`/`_Load_Result`/`_Load_Retry`/`_Purge`/
`_Purge_Result` table for the given objects — idempotent, a table that's
already gone is silently skipped — and clears their `dbo.FieldProfile`/
`FieldProfileValues` rows too, a real addition beyond the original idea
sketch above: without it, roadmap #47's own "skip re-profiling an
already-profiled object" behavior would silently treat a dropped-and-
rebuilt table as still current on the next Dev cycle, since the
profiling row itself would still be sitting there claiming otherwise.

`purge_org_test_data()` is a thin, undisguised pass-through to
`bulkops.py`'s own `purge_by_filter()` (#32) — not a separate delete
mechanism, exactly the same one, wired up via `--purge-org-where
Object:WHERE_CLAUSE` (repeatable). A real Salesforce delete, so the
Live-Org Write Confirmation Rule (#2) applies in full; `--dry-run`
reports the matched count without deleting anything, same as
`purge_by_filter()` always has. Deliberately no skill wrapper in
`.claude/commands/` — same reasoning as the main `bulkops` command
itself never getting one, since this command can trigger a real delete
depending on which flags are passed.

Deliberately leaves `sql/transformations/*.sql`, mapping docs, and every
org-metadata-derived cache (`dbo.ObjectAutomationRisk`, `dbo.RecordTypeMap`,
`dbo.SourceRegistry`/`AutoMapSuggestions`) untouched — those are either
real, committed artifacts a reset must never silently erase, or reflect
the target org's own state (which a Dev-cycle reset doesn't change), not
this project's own iteration-specific mock/test data. "Any staging
tables" from the original idea sketch above was dropped from scope:
`source_ingestion.py`'s staging tables are named after the source CSV
file, not the Salesforce object, so there's no reliable naming
convention to derive them from an object list without guessing.

Purely a convenience wrapper around existing primitives (`DROP TABLE`,
`bulkops delete`) — no new logic, just removing the "did I remember every
step" risk of doing this by hand before every fresh iteration.

## 64. Row-count reconciliation report — BUILT (`reconciliation.py`)

A data-completeness auditor spanning the whole load order, not a
per-tool spot check. `reconcile_load_counts()` (`cli.py
reconcile-load-counts <Objects> [--mapping-path] [--load-table
Object=Table]`) cross-checks three numbers per object: the source
table's row count, the Load table's row count (did the transform's
`JOIN`s/`WHERE` clauses silently drop rows it shouldn't have?), and
`bulkops`' most recent submitted/succeeded/failed counts from
`BulkOpsLog` (#14). Four flags, not just one: the Load table doesn't
exist yet; it has fewer rows than the source; it's never been loaded via
`bulkops` at all; or its current row count no longer matches what the
most recent `bulkops` run actually submitted — a real addition beyond
the original idea sketch above, catching a *stale* reconciliation (the
Load table was rebuilt/changed after the last `bulkops` run) rather than
just a row-count shortfall.

Source-table discovery reads a mapping doc's own "Source Object:" header
cell for that object's sheet — the exact cell `generate-mapping-doc`
(`generate_mapping_workbook()`) already writes — real, not guessed;
`--mapping-path` is optional, and omitting it just skips the
source-count half (Load/`bulkops` cross-checking still runs). Load table
naming defaults to `<Object>_Load`, matching this project's own
overwhelming convention (the same default `reset-dev-cycle`/
`pass_summary.py` already use); `--load-table Object=TableName`
overrides it per object, never guessed. Entirely read-only, aggregating
data every one of these tools already produces — the value is in
cross-checking all three together in one pass, not new data collection.

## 65. Migration readiness score — BUILT (`readiness.py`)

One aggregate go/no-go view instead of manually checking five different
tables/commands to answer "are we actually ready for this pass."
`assess_migration_readiness()` (`cli.py assess-migration-readiness
<Objects> [--migration-key Object=Field] [--mapping-path]
[--load-table Object=Table]`) checks, per object: has the Parent-Batch
Sort Rule (#6) been applied — only when the object actually has an
in-scope parent on file in `dbo.ObjectDependency` (from
`analyze-load-order`), so a parent-less object is never falsely flagged
for a missing `Sort` column? Has the Migration Key Integrity Rule (#7)
check passed clean — re-run live via `load_table_prep.py`, not recalled
from memory? Has the Live Migration Key Validation Rule (#12) passed
against the live org — re-run live via `metadata.validate_external_id_field()`?
Has `analyze-org-risk` (#5) actually been run for this object (the same
"scanned vs. never scanned" signal `orchestrator.py` already needs and
`risk_analyzer.py`'s `ScanCompleted` marker already makes checkable)? Has
`check-mapping-balance` (#3) come back clean — re-run live against the
mapping doc and the object's real transform script, auto-resolved via
`script_numbering.script_filename_for()`? Has Email Deliverability been
attested for this pass (hard rule 9 — still a human attestation, never
auto-checked, so this can only confirm the flag was recorded on the most
recent `BulkOpsLog` insert/update/upsert row, not verify the Setup value
itself — skipped, not failed, when the most recent run was a delete,
since deletes never need it)? Row-count reconciliation (#64) is folded
in directly, reusing `reconciliation.py` rather than reimplementing it.

Two gates need a per-object parameter this module can never safely guess
— the migration-key field name and the mapping doc path — both optional;
an object left out of `--migration-key` just reports those two gates as
"not checked," never assumed clean. Every gate's result is `True`/
`False`/`None` (not applicable or not checked) — **only an explicit
`False` blocks the overall READY/NOT READY verdict**; a `None` gate is
still fully reported (so a human can judge whether that gap matters for
this particular pass) but doesn't itself sink readiness. This distinction
mattered in practice: the row-count-reconciliation gate originally
treated `reconciliation.py`'s own "Load table doesn't exist yet" flag as
an explicit failure, inconsistent with every other gate's `None`
treatment of that exact state (a load that simply hasn't happened yet
isn't a readiness *failure*) — found and fixed via this module's own
test suite before it shipped. Aggregate into a per-object checklist plus
one overall verdict — read-only, no new checks invented, purely a
re-presentation of gates this framework already enforces individually.
Dogfooded live against this project's own org and mirror DB, including
watching the verdict flip from NOT READY to READY after a real
`analyze-org-risk` run.

**Two more real bugs found via the full pipeline dogfood run** (bootstrap
through a live 4-object `bulkops` load, `analyze-org-risk`,
`reconcile-load-counts`, and `generate-pass-summary`):

- The Parent-Batch Sort gate's "does this object have an in-scope parent"
  check counted a **self-reference** edge (`ChildObject == ParentObject`
  in `dbo.ObjectDependency` — e.g. `Account.ParentId`/`MasterRecordId`,
  both pointing `Account -> Account`) as a real parent, wrongly demanding
  a `Sort` column on `Account_Load` even though `Account` has no actual
  cross-object parent to batch against at all (a self-reference is a
  two-pass-load field, per `load_order.py`'s own `self_references`
  tracking — never mocked, never something `add-bulk-load-sort-column`
  needs). Fixed by excluding `ParentObject != ChildObject` from the has-a-
  parent query.
- `check-mapping-balance`'s column-list parser (`mapping_doc.py`) had
  **never actually recognized either of this project's own two real
  *_Load-building patterns** — `SELECT ... INTO` (mssql,
  `sql_dialect.py`'s own `MssqlDialect.create_table_as_select_sql()`) and
  `CREATE TABLE ... AS SELECT` (sqlite) — only a literal
  `INSERT INTO table (col1, col2, ...)` DML statement, which no real
  transform script in this project uses at all. `assess-migration-
  readiness`'s `mapping_balance` gate raised "No INSERT INTO statement
  found" against every one of this project's own working scripts, mssql
  or sqlite. Fixed by adding real SELECT-list parsing for both forms
  (splitting on top-level commas so a `CAST(x AS y)`'s own internal
  syntax isn't mistaken for a second column; taking the `AS alias` if
  present, else the bare/qualified column name). That fix then exposed a
  second, genuinely funny bug the same regex-only approach was hiding:
  the parser had no SQL-comment awareness at all, so `010_account_load.sql`'s
  own header comment — which happens to describe the port in English
  prose, literally *"SELECT ... INTO is the equivalent"* — matched as if
  it were real SQL, extracting `is` as the table name and comment text as
  the column list. Fixed by stripping `/* */` and `--` comments before
  any pattern match, for all three recognized forms.

**One real, structural gap found but deliberately left open, not fixed
this session**: a load table's own bookkeeping key column (this
framework's own `LoadId` convention — the Snowfakery-era join key every
generated `*_Load` table carries, distinct from a `REF_`-prefixed audit
column, hard rule 13) is not a real Salesforce field and will **always**
show up in `mapping_balance`'s `not_a_real_field` list for every object,
in every project using this convention — there's currently no equivalent
of `bulk_op()`'s own `key_column`/`id_column`/`error_column`/`ref_prefix`
exclusion list for `check_mapping_balance()`. Confirmed live: every one of
this dogfood run's 4 objects reported `NOT READY` on this gate alone, a
false alarm each time (`LoadId` is expected and correct, not a mapping
mistake) — a real usability problem for `assess-migration-readiness`'s
whole "one aggregate go/no-go view" premise if every real project
permanently shows `NOT READY` on a benign, unavoidable finding. Worth
fixing before this command is relied on for a real (non-dogfood) project:
thread the load table's own bookkeeping column names (and/or the `REF_`
prefix) through to `check_mapping_balance()` the same way `bulk_op()`
already excludes them, rather than reporting them as an ordinary
not-a-real-field imbalance.

## 66. Auto-drafted client-facing pass summary — BUILT (`pass_summary.py`)

A plain-English "here's what happened this pass" draft, pulled from the
Migration Run Book's (#16) own Load-phase rows for a given tab — ready to
send a client stakeholder instead of a raw spreadsheet dump or a
manually-written status email. `generate_pass_summary()` (`cli.py
generate-pass-summary <path> --tab <name> --output <path.md>`) reads
`migration_run_book.py`'s own `_iter_load_phase_rows()` (no changes
needed to that module) for object count and total/succeeded/failed
records per object, then composes a Markdown narrative: an overview line,
a per-object results table, and a "Known issues" section for anything
that didn't come back 100% clean.

`--load-table Object=TableName` (repeatable) optionally enriches that
section with a real, plain-language root cause per failure signature via
`triage-failures` (#61) instead of just a raw failed count — deliberately
never auto-derived from the Run Book's own Object cell, which may hold a
bare object name or a real script filename (`020_contact_load.sql`, once
`set-mapping-script`/the Load-phase sync has run) — neither reliably
gives the actual SQL Load table name (`Contact_Load`) on its own, so
guessing it would risk quietly triaging the wrong table, or none at all.
An object left out of `--load-table` just gets a pointer at the Run
Book's own Notes/Error Details columns instead — always correct, if less
specific.

Plain Markdown for v1, not `solution_doc.py`'s `docxtpl`-based Word
generation — same "ship the simple version, decide on polish later"
discipline as #52's own v1 framing; that machinery is there to reuse
later if a client-ready Word format is ever wanted instead.

---

## End-to-end project workflow (vision, not built)

The long-term shape this framework is heading toward — a full project
lifecycle, not just a set of standalone tools. Laid out end to end
directly in one conversation, phase by phase, referencing what already
exists and what's newly captured above rather than restating either:

0. **Discovery** (new, upstream of this framework's own tools): the
   architect handles client discovery separately — often with another AI
   session's help — landing on which objects need migrating, the use
   cases behind each one, and any special requirements. Two new ideas
   bridge that into this framework instead of leaving it a cold start: a
   discovery question checklist generator (#60), driven by real
   complexity signals (`analyze-org-risk`, RecordTypes, load-order
   dependencies) rather than a generic template, informs what to ask; a
   migration brief intake (#59) then turns the discovery output into the
   first real command sequence (`describe` validation, `analyze-load-order`,
   a scaffolded Migration Run Book) instead of re-typing an object list by
   hand.
1. **Source ingestion**: read a client-provided directory of CSVs (or
   validate a later pass's files against what's already loaded) and
   build the Source SQL Server database from it — #46, the current gap.
2. **Mapping**: generate the mapping document (#3) with one tab per
   source table just loaded, then decide by pass — first pass gets a
   full profile (#7) and auto-map (#10) first draft for a human to
   finish; a later pass reviews and polishes the *existing* doc instead
   (#47's pass-awareness gap). A finished first-pass mapping is also,
   with explicit per-project consent, a candidate to teach the shared
   synonym thesaurus something new (#48) — and a chance to catch a
   migrate-flagged field with no target chosen yet (#49).
3. **Build**: generate the T-SQL transform for each source → target
   pairing, in load order (#2), using this project's established
   numbering convention (`CLAUDE.md`'s standard workflow: mapping →
   confirm field names via `describe`/`dump-describe` (rule 5) → build →
   sort (rule 6) → dupe-check (rule 7)). Before any of it can load,
   confirm the migration key's target field is genuinely
   external+unique in the live org (#50, hardening rules 4/7) — this
   framework's job is to verify that gate, not to build the field itself.
4. **Test each script individually, not end to end yet**: drive toward
   100% of rows loading per object, fixing the SQL when it doesn't
   rather than accepting errors as normal at this stage. Established
   tools do double duty here: `bulkops delete --where`/`--dry-run` (#32)
   for the load → find a problem → back out → fix → reload cycle during
   iteration, and `analyze-org-risk` (#5) plus a reference-record pull
   (#51, new) when an architect hand-creates a record in the UI to show
   what "correct" actually looks like against the org's real automation.
   Two new ideas speed this cycle up directly: adversarial mock data
   (#62) provokes known failure classes on purpose so a validation-rule
   collision surfaces here, not during a real client load; a failure
   triage assistant (#61) groups whatever does fail by normalized
   signature and maps it to a likely root cause instead of leaving that
   to manual error-string reading. A reset-dev-cycle command (#63)
   codifies the "wipe and try again" ritual this project's own
   dogfooding has done by hand every iteration. The standing goal stated
   directly: our data should land looking indistinguishable from a
   record created natively in the org — the migration key is the *only*
   thing that should ever tell the two apart.
5. **Document and diagram**: code review and documentation of the
   scripts as they stabilize, plus Mermaid process-flow diagrams
   generated from the Migration Run Book (#52, built) for a visual
   instead of a spreadsheet-only view.
6. **Verify completeness before a full run** (new): a row-count
   reconciliation report (#64) cross-checks source count → Load table
   count → `bulkops` succeeded count per object, catching a silently
   dropped row before it reaches a human's attention on its own; a
   migration readiness score (#65) aggregates every gate this framework
   already enforces individually (hard rules 6/7/12/15, `analyze-org-risk`
   coverage, mapping balance, Email Deliverability attestation) into one
   go/no-go view instead of five separate checks.
7. **Full end-to-end runs**: once individual scripts are solid, run the
   real sequence — object by object, adapting batch size (#15) and
   retrying (#11) automatically, logging everything (#14/#16). Perfect
   completion isn't the bar; a UAT pass with a handful of genuinely
   unfixable source-data rows is a normal, reportable outcome, not a
   failure — call it out in the run book, report it to the client, and
   revisit with a subset reload later if needed. This is #53's
   orchestrator, still waiting on a real UAT pass before Phase 2 gets
   built.
8. **Keep the human in the loop, better than email**: #54's Slack/Teams
   idea — starting with outbound alerts, with bidirectional chat-driven
   control as the further-out, architecture-changing version — alongside
   an auto-drafted client-facing pass summary (#66) pulled straight from
   `BulkOpsLog`/the Migration Run Book, so reporting a pass's outcome
   isn't a separately hand-written status email.

This ties together #2 (load order), #3 (mapping doc), #4 (solution doc),
#5 (org metadata risk), #6 (mock data), #7 (profiling), #10
(auto-mapping), #11 (bulkops + retry), #14/#16 (logging + run book), #15
(batch sizing), and #32 (purge-by-filter) into one pipeline, plus the
gaps captured above (#46–#66) as the concrete next pieces. Scoping any
one of them into a real build is the next step — this section is the
shape of where it's all going, not a spec for any single piece of it.

## 67. Methodology PowerPoint deck + deep-dive PDF manual (not built — roadmap idea per explicit request)

Raised directly: a PowerPoint presentation explaining the whole
methodology — what this framework can do, the order of things, diagrams
showing the flow of steps — aimed at a **technical audience** for now,
with appendix slides specifically covering security. No feature should be
skipped, however small. Alongside it, a **PDF document** that goes deeper
than the deck, pulling the same information into manual-length detail.

Two separate deliverables, not one document at two zoom levels:

1. **PowerPoint deck** — the methodology story: what the framework is
   (SQL-centric, SQL Server as the integration hub, git-versioned
   transforms), the end-to-end flow (bootstrap → discovery → profiling →
   mapping → transform build → hard-rule gates 6/7/12/15 → load →
   readiness/reconciliation → pass summary — the same sequence #53's
   orchestrator and this session's full dogfood run both exercise),
   and a walk through every command surface (`cli.py` verb, matching
   `.claude/commands/*.md` skill) grouped by phase rather than
   alphabetically. Diagrams should reuse this framework's own generation
   tooling rather than being hand-drawn twice: `generate-target-data-model`/
   `generate-source-data-model` (#57, Mermaid SDMN-style ERDs) and the
   Migration Run Book's own Mermaid process-flow diagrams (#52) are
   already real, checked-in artifacts a deck could screenshot or embed
   rather than redraw. **Appendix**: security — the credential inventory,
   trust boundaries, and code-enforced vs. convention-enforced controls
   `docs/SECURITY_OVERVIEW.md` already documents, restructured for a
   slide format rather than duplicated by hand (so the deck can't drift
   from that document without both being touched).
2. **PDF manual** — the same material at real depth: every hard rule
   (1–15) with its rationale, every System Validator, every CLI command's
   full option surface, the opt-in logging tables and what each column
   means, the batch-size/orchestrator threshold files and how they're
   tuned, source ingestion drift detection, the Migration Run Book's full
   phase structure — effectively a bound version of `CLAUDE.md` + `README.md`
   + `docs/*` + `ROADMAP.md`'s "BUILT" sections, organized for a reader
   working through it linearly rather than jumping between files.

Neither exists yet. Open build questions once this is scoped for real:
whether the deck is generated (a Python-built `.pptx` via `python-pptx`,
kept in sync with the codebase like every other generated artifact this
framework produces — mapping docs, solution docs, run books) or hand-
authored once and maintained manually; same question for the PDF (rendered
from Markdown via a toolchain, vs. hand-assembled in a word processor).
Given this framework's own consistent pattern — generated artifacts that
can't silently drift from the code that produced them (`solution_doc.py`,
`migration_run_book.py`, the data model diagram generators) — a generated
deck/PDF pulling from the same source-of-truth files (`CLAUDE.md`,
`ROADMAP.md`, `docs/SECURITY_OVERVIEW.md`) is the more consistent direction,
but that's a real design decision for whoever scopes the actual build, not
decided here.

## 68. Docker-based local dev environment — BUILT (`Dockerfile`, `docker-compose.yml`, `docker/init-db.sh`, `docs/DOCKER.md`)

Raised directly, alongside PostgreSQL/Fivetran/Apache Hop, as a
technology worth an opinion on. Verdict here is the opposite of the two
FAQ entries below (#70) — this one was a genuine fit, not a "why not," so
it was built out for real rather than just scoped.

**The friction this solves**: every setup instruction in this repo
(`CLAUDE.md`'s own canonical commands, `sqlcmd -S localhost -E`) assumed a
Windows box with a local SQL Server instance and the ODBC driver already
installed — real friction for a new contributor or a fresh project
machine, and a genuine barrier on non-Windows hardware. The test suite
already sidestepped this for CI (`SQL_BACKEND=sqlite`, no server needed
at all), but that was a CI-only escape hatch, not a real local dev story
for anyone who actually needs to run against `mssql` (most of the
SQL-Server-only tooling listed in CLAUDE.md's "SQL backend" section —
`sql/functions/`, `profiling.py`, `auto_mapper.py`, etc. — only exercises
for real against `mssql`).

**What shipped**: `docker-compose.yml` defines two services — `sqlserver`
(SQL Server 2022 Developer Edition, free/non-production, a named volume
for persistence) and `app` (this repo's Python environment — `Dockerfile`
installs the Microsoft ODBC Driver 18, `mssql-tools18`/`sqlcmd`, and the
Salesforce CLI on top of `python:3.12-slim-bookworm`, then `pip install -r
requirements.txt`; the repo itself is bind-mounted rather than copied in,
so host edits are live with no rebuild needed). `docker compose up -d`
then `docker compose exec app python cli.py <verb>` replaces README.md's
steps 3–7 (Python venv, SQL Server engine, SSMS, the ODBC driver, creating
the database) entirely. Doesn't change anything about Hard Rule 1
(mirror-DB-only writes) or any other Hard Rule — purely a packaging
change for the exact same architecture, not a design change.

**A brutal post-build review caught real problems in the first pass,
fixed before this was considered done — worth recording, not just
quietly patched**:
- The original design had a *separate* one-shot `sqlserver-init` service
  and `sqlserver`'s own healthcheck both calling `sqlcmd` from *inside
  the `mcr.microsoft.com/mssql/server` image itself* — an unverified
  assumption (that image is the SQL Server engine, not a tools image; its
  bundling `sqlcmd` was never actually confirmed) that could have quietly
  blocked the entire stack from ever starting if wrong, since `app`
  depended on that init step completing successfully. Fixed by removing
  `sqlserver-init` entirely: `sqlserver`'s healthcheck now does a
  dependency-free bash TCP check instead, and the mirror-database
  creation step (`docker/init-db.sh`) runs at `app`'s own startup, using
  that container's own **verified** `mssql-tools18` install (the
  Dockerfile everyone can read installs it directly) — with a real retry
  loop (up to 120s), since a TCP-up healthcheck doesn't guarantee SQL
  Server can authenticate a login yet.
- The Dockerfile's `gnupg2` package name is a real risk on Debian
  12/bookworm (Debian merged `gnupg`/`gnupg2` long ago; the transitional
  package isn't reliably present) — changed to the canonical `gnupg`.
- Installing the Salesforce CLI via Debian's own default `nodejs`/`npm`
  apt packages was fragile — distro-packaged Node lags behind current
  LTS, and Salesforce's own install docs specifically warn against this
  for exactly that reason. Changed to NodeSource's own setup script,
  pinned to a specific Node major version deliberately (same "pin it,
  bump it on purpose" discipline as any other dependency here), not
  "whatever the distro happens to ship."
- `docs/DOCKER.md`'s own "inspecting the mirror DB from inside the
  container" example referenced `$MSSQL_SA_PASSWORD` — a variable never
  actually set inside the `app` container (only `sqlserver` gets it
  directly; `app` only gets the derived `SQL_PWD`) — fixed to reference
  the variable that's actually there. Also added `DEBIAN_FRONTEND=
  noninteractive` (a latent risk of an unexpected interactive apt prompt
  hanging an automated build) and fixed a markdown heading that was
  accidentally split across two lines in the original doc, silently
  breaking how that section rendered.

**The three real open questions from the original idea, resolved**:
- *SQL Server licensing*: `MSSQL_PID: Developer` — free, full-featured,
  non-production use, same edition README.md's own setup already
  recommends; nothing new to clear here.
- *`sf` CLI auth from inside a container*: genuinely mode-dependent, not
  a single answer — `jwt`/`password` mode (`sf_client.py`'s
  `connect_salesforce()`) are pure Python and need the `sf` binary not at
  all, so they work with zero extra container config. `cli` mode needs a
  real browser for `sf org login web`, which doesn't work headlessly
  inside a container — the original idea here was a `~/.sf` bind mount to
  reuse an already-authenticated host session, but **that turned out not
  to work at all**: confirmed live (2026-07-13), current `sf` CLI
  versions store org authorization in the host OS's own keychain
  (Windows Credential Manager / macOS Keychain / `libsecret`), not a
  plaintext file under `~/.sf` — nothing a Linux container can reach
  through any bind mount, regardless of the exact host path. The
  `docker-compose.yml` mount line was reverted to commented-out-for-
  reference-only; use `jwt`/`password` for anything running in the
  container. See `docs/DOCKER.md`'s auth-mode section for the full
  finding.
- *Whether to bundle `sqlcmd`*: yes — installed in the `app` image
  alongside the ODBC driver (both come from the same Microsoft
  `mssql-tools18` package), so the "look at SQL Server directly"
  read-only workflow works the same way inside the container
  (`docker compose exec app sqlcmd ...`) as it does today on a host with
  SSMS/`sqlcmd` installed directly; port 1433 is also published so a
  host-installed tool (SSMS, Azure Data Studio, DBeaver) can connect
  directly too, whichever a given developer prefers.

**One thing worth knowing that isn't obvious from the compose file
alone**: the `app` service's own `environment:` block deliberately
overrides `SQL_SERVER`/`SQL_DATABASE`/`SQL_TRUSTED_CONNECTION`/`SQL_UID`/
`SQL_PWD` even though `.env` is also mounted in via `env_file` — inside
the compose network, "localhost" means the app container itself, not a
SQL Server the developer may separately have installed on their host.
This works cleanly (not a footgun) because `config.py`'s
`load_dotenv()` call never overrides an already-set OS environment
variable (python-dotenv's own documented default), and Compose's
`environment:` block sets real process env vars before the container's
Python process ever starts — so the override always wins, and every
non-SQL setting (`SF_*`, `MOCKAROO_API_KEY`, `TICKET_SYSTEM_*`) still
loads normally from the developer's own mounted `.env`, unchanged.

Not yet extended to PostgreSQL (#69, not built) or a SQLite container
variant (SQLite needs no server at all, so there's nothing to
containerize there) — `docs/DOCKER.md` notes both explicitly as
deliberately out of scope for this pass.

## 69. PostgreSQL as a third `sql_dialect.py` backend (core dialect + Docker service both built and live-verified 2026-07-13)

The other technology worth a genuine "yes, eventually" out of the four
raised. `sql_dialect.py` already proves the seam works — one `SqlDialect`
ABC, `MssqlDialect`/`SqliteDialect` as the two real implementations. A
third, `PostgresDialect`, is now built too, implementing the same
abstract methods (`qualify`/`quote_ident`/`table_exists`/`column_exists`/
`list_columns`/`create_table_as_select_sql`/`select_top_n_sql`/
`autoincrement_pk_column_ddl`/`sf_type_to_sql`/`normalize_datetime_columns`),
registered under `_DIALECTS["postgresql"]` to match `engine.dialect.name`
for a `postgresql+psycopg2://` engine (`sql_client.py`'s
`_make_postgres_engine()`, using `sqlalchemy.engine.URL.create()` rather
than a hand-rolled connection string — its password field is redacted
by SQLAlchemy's own `repr()`/`str()` by default, confirmed live, unlike
`_make_mssql_engine()`'s `odbc_connect` blob which that function's own
comment already flags as unmaskable). `SQL_BACKEND=postgresql` plus
`SQL_PORT`/`SQL_POSTGRES_SSLMODE` (reusing `SQL_SERVER`/`SQL_DATABASE`/
`SQL_UID`/`SQL_PWD` for the rest) is wired through `config.py`, with
`psycopg2-binary` added to `requirements.txt`. 10 new/updated unit tests
in `tests/test_sql_dialect.py` cover identifier quoting, CTAS/`LIMIT`
SQL, the identity-column DDL, `sf_type_to_sql`'s full type mapping, and
`for_engine()` resolution — confirmed passing, plus a live (no server
needed) end-to-end check that `config.py` → `sql_client.make_engine()`
→ `sql_dialect.for_engine()` resolves to a real `PostgresDialect`
instance with a correctly-redacted engine URL.

**Follow-up pass (2026-07-13, same day): the column-type gap above is
now actually fixed, plus two deeper gaps found and fixed along the
way — verified against a real, throwaway Postgres 16 container
(`docker run postgres:16`), not just reasoned from docs:**

- **The type-mapping gap itself**: `sql_dialect.py` gained a shared
  `SqlDialect.pick_type(mssql_type, sqlite_type, postgres_type)` method
  (plus a `backend_key` class attribute per concrete dialect) replacing
  the private, mssql-or-sqlite-only `_col_type()`/inline
  `isinstance(d, MssqlDialect)` ternaries that used to be duplicated
  independently in **five** places, not the three originally found:
  `bulkops.py`, `orchestrator.py`, `source_ingestion.py`, **and
  `load_order.py`/`risk_analyzer.py`** (the last two build
  `ObjectDependency`/`ObjectLoadOrder`/`ObjectAutomationRisk` — core
  `analyze-load-order`/`analyze-org-risk` output, not opt-in logging at
  all, so this was a bigger miss than first documented). A future backend
  now needs updating in one place, not five.
- **Hard Rule 6 needed genuinely new code, not just a type swap**:
  `load_table_prep.add_bulk_load_sort_column()`'s SQLite branch
  correlates via SQLite's own implicit `rowid`, which doesn't exist in
  Postgres. Added a real third branch using Postgres's `ctid` (its own
  physical-row-identifier analogue) via `UPDATE ... FROM` — Postgres has
  no updatable-CTE syntax either, so this isn't just find-and-replace.
  Verified live against a real multi-child-per-parent case (the exact
  scenario this rule exists for): every parent's rows land in a
  contiguous `Sort` range, matching the mssql/sqlite behavior exactly.
- **A second, unrelated bug surfaced only by live testing**: `CREATE
  TABLE` in these five files quoted column names (`d.quote_ident(name)`,
  preserving exact case in Postgres's catalog), while every `INSERT`/
  `SELECT`/`WHERE`/`DELETE` elsewhere in the codebase that touches these
  same tables (`batch_advisor.py`, `failure_triage.py`,
  `migration_run_book.py`, `readiness.py`, `reconciliation.py`, plus
  these five files' own INSERTs) already references columns **bare**
  (unquoted). SQL Server/SQLite tolerate that mismatch (both match
  unquoted references case-insensitively regardless); Postgres does not
  — it folds an unquoted reference to lowercase, which doesn't match a
  quoted, case-preserved catalog name, raising
  `psycopg2.errors.UndefinedColumn`. Fixed by making `CREATE TABLE`
  bare too (matching the codebase's own dominant convention) rather than
  quoting every scattered reference across ten-plus files — the one
  genuine exception, `SourceIngestionLog.RowCount` (a real T-SQL
  reserved-word collision), stays quoted on both the creation and
  reference side, exactly as it already was.
- **A third bug, one layer deeper still**: Postgres also returns
  **lowercased** column names in a query's own result set for any
  unquoted column (not just at creation) — unlike SQL Server/SQLite,
  which return whatever case was originally declared. `orchestrator.py`'s
  `row["LogId"]` and `_row_to_current()`'s `row.get("RecordsSubmitted")`-
  style exact-case access both silently broke (the `.get()` case is
  worse: no crash, just silent `None`/zero defaults). Added
  `sql_dialect.row_get(row, key)` (exact-case fast path, case-insensitive
  fallback) and fixed both spots in `orchestrator.py` specifically, since
  that's what this pass was scoped to.

**Follow-up pass, same day: `migration_run_book.py` fixed too, plus a
structural bug found while starting this pass.** Before touching
`migration_run_book.py`, re-verifying `sql_dialect.py` turned up a real
defect from the *first* follow-up pass above: the edit that added
`row_get()` had accidentally landed its whole body, unindented, between
`SqlDialect.pick_type()` and the ABC's own `@abstractmethod`
declarations — which silently re-nested every one of `qualify`/
`quote_ident`/`table_exists`/etc. as dead, unreachable functions *inside*
`row_get()`'s own body instead of leaving them as `SqlDialect`'s abstract
methods. No test caught it and nothing broke at runtime (every concrete
dialect still fully implements its own `qualify`/etc. independently, so
losing the ABC's enforcement was invisible in practice) — but
`SqlDialect.__abstractmethods__` was silently empty, meaning a future
fourth dialect that forgot to implement a method would no longer be
caught at instantiation time. Fixed by moving `row_get()` (and a new
`lower_keys()` helper, below) to their correct place *after* the full
`SqlDialect` class body; confirmed via `ast.parse()` and
`SqlDialect.__abstractmethods__` that all eleven abstract methods are
back where they belong.

With that fixed, `migration_run_book.py`'s three affected functions
(`_load_order_rows()` — `ObjectLoadOrder`/`ObjectDependency` reads;
`sync_run_book_from_log()`/`_apply_log_result()` — `BulkOpsLog` reads;
`sync_source_ingestion_to_run_book()`/`_apply_source_ingestion_result()`
— `SourceIngestionLog` reads) all had the identical bare-vs-exact-case
read pattern `orchestrator.py` had. Rather than routing each of the ~15
individual field accesses through `sql_dialect.row_get()` one at a time,
added a second shared helper, `sql_dialect.lower_keys(row)` (lowercase
every key once, then reference lowercase consistently) — `orchestrator.py`'s
own `_row_to_current()` was refactored to call this too instead of its
own inline version. Verified live against a real Postgres 16 container:
`generate-migration-run-book` (exercising `_load_order_rows()`),
`update-migration-run-book`'s `BulkOpsLog` sync, and its
`SourceIngestionLog` sync all produced correct results end-to-end.

**Follow-up pass, same day: `readiness.py` fixed too.**
`assess_migration_readiness()`'s `_email_deliverability_gate()` had the
identical bare-vs-exact-case read (`row["Operation"]`/
`row["EmailDeliverability"]` from its own `BulkOpsLog` query) — fixed via
the same `sql_dialect.lower_keys()` helper. Verified live against a real
Postgres 16 container by calling the gate function directly (a full
`assess_migration_readiness()` run also needs a live Salesforce
connection for two of its other gates, out of scope for this
Postgres-specific check): correctly resolved `ok: True` with the
attested `'system-email-only'` value from a real logged row.
`readiness.py`'s other gates (`_sort_column_gate`/`_org_risk_gate`) only
ever use `.scalar()`, never row-mapping key access, so they had no
version of this bug to begin with.

**Follow-up pass, same day: `reconciliation.py` fixed too.**
`_latest_bulkops_row()` returned `dict(row)` with whatever case the
driver gave back (exact case on mssql/sqlite, lowercase on Postgres),
and `reconcile_load_counts()` then read `bulkops_row["RecordsSubmitted"]`/
`["RecordsSucceeded"]`/`["RecordsFailed"]` by exact case in three places
— including the actual stale-prior-run comparison
(`bulkops_row["RecordsSubmitted"] != load_count`), not just a display
value. Fixed by returning `sql_dialect.lower_keys(row)` instead of a
plain `dict(row)`. Verified live against a real Postgres 16 container
with two cases, not just the happy path: a clean reconciliation (Load
table row count matches the most recent `BulkOpsLog` submission, zero
flags) and a genuinely mismatched one (Load table grew after the last
bulkops run — correctly raised the "may reflect a stale prior run" flag,
proving the comparison itself works on Postgres, not just that reading
the row doesn't crash). This also means `assess-migration-readiness`'s
own `row_count_reconciliation` gate (which calls
`reconcile_load_counts()` directly) is now fully covered too.

**Follow-up pass, same day: `batch_advisor.py` and `failure_triage.py`
fixed too — plus two more genuinely new bug classes found, not just the
read-side pattern.** `batch_advisor.py` turned out NOT to have the
case-folding read bug at all: its history/heuristic queries use plain
`.fetchall()` with positional tuple unpacking
(`last_batch_size, last_lock_errors = rows[0]`) and a `dict()` keyed by
**data values** (`CheckType` strings like `"ApexTrigger"`, never column
names) — both immune to case-folding by construction, confirmed by
reading the code before assuming it needed the same fix as everywhere
else. What live testing found instead, in both files:

- **A genuinely new bug class**: `_automation_adjustment()`
  (`batch_advisor.py`) and `_validation_rule_candidates()`
  (`failure_triage.py`) both hardcode `IsActive = 1` as a literal in the
  SQL text. `IsActive` is a real `BOOLEAN` column on Postgres
  (`risk_analyzer.py`'s own DDL, from the very first follow-up pass
  above) — Postgres raises `operator does not exist: boolean = integer`
  outright, where SQL Server's `BIT`/SQLite's `INTEGER` both tolerate the
  literal fine. Fixed by binding `True` as a real query parameter
  (`:is_active`) instead of a literal in the SQL text, letting each
  backend's own driver coerce it correctly for its actual column type.
- **A bug in `PostgresDialect.column_exists()` itself, not a caller**:
  found while re-testing `batch_advisor.py`'s history adjustment, which
  reported "`BulkOpsLog` exists but predates batch-size tracking" on a
  table that had just been created *with* that column. `column_exists()`
  compared `column_name = :column` (exact case) against
  `information_schema.columns` — correct for `table_exists()` (table
  names are always created via `self.qualify()`, therefore quoted and
  case-preserved) but wrong for columns, which this codebase creates
  bare/lowercase-folded almost everywhere (per the second follow-up pass
  above). Fixed with `LOWER(column_name) = LOWER(:column)`; verified live
  that this still correctly resolves `SourceIngestionLog.RowCount` (the
  one genuinely case-preserved, quoted column) in both its original case
  and lowercase, not just the newly-fixed bare columns.

`failure_triage.py` also had the ordinary read-side pattern
(`r["ItemName"]`/`r["Detail"]`) on top of its own `IsActive = 1` —
fixed via `sql_dialect.lower_keys()`, same as everywhere else.

**`auto_mapper.py`/`profiling.py`/`data_model_diagram.py`/
`record_types.py`/`reference_record.py` weren't touched** — they're
SQL-Server-only tables, out of scope for `SQL_BACKEND=postgresql`
regardless.

**The "fully closed" claim above was wrong — a ruthless code-review pass
found it wasn't.** A full multi-angle review (8 finder agents + a
mandatory security pass) of everything in this and the three prior
follow-up passes found the audit above had missed `load_table_prep.py`
itself — Hard Rules 6/7's own implementation, the one this whole chain
of fixes exists to protect:

- **`add_bulk_load_sort_column()`** and **`check_load_table_duplicate_keys()`**
  both used bare SQL aliases (`ParentKey`/`MinSort`/`MaxSort`/`SortSpan`/
  `DuplicateKey`/`Occurrences`) and returned `dict(r)` unlowered — but
  their return values are a **public, documented Pascal-case contract**
  `cli.py` reads by exact key. On Postgres this raised `KeyError`
  precisely when either check found something real to report (a
  non-contiguous Sort range, a genuine duplicate migration key) — the
  exact opposite of every other fix in this chain, which normalizes the
  *reader* to lowercase. Here the *aliases themselves* are wrapped in
  `d.quote_ident()` instead (same mechanism `RowCount`/`Sort` already
  used in this file), guaranteeing the exact declared case on all three
  backends with zero changes needed to `cli.py`/`readiness.py`. Verified
  live with a genuinely non-contiguous range and a genuine duplicate key
  (not just the clean path) — both now report correctly instead of
  crashing.
- **`source_ingestion.py`'s generated `.sql` script** (and its module/
  function docstrings) hardcoded "SQLite has no BULK INSERT equivalent"
  regardless of the actual backend — false, and a real, permanent
  inaccuracy in a Hard-Rule-10-traceable, git-committed artifact once
  `SQL_BACKEND=postgresql` existed. Fixed to name the real backend
  (`Backend: PostgreSQL` in the generated header) and describe both
  non-mssql backends accurately (SQLite has no bulk-load mechanism at
  all; Postgres has `COPY`, genuinely not used here). `import-directory`
  itself (both the "new file" and "existing file, later pass" cases) is
  now live-verified against Postgres too — CLAUDE.md's claim that it
  "works on all three backends" was true in practice (the generic pandas
  path) but had never actually been exercised against Postgres before
  this pass.
- **Doc drift**: `docs/SECURITY_OVERVIEW.md` (never updated for the
  Postgres backend — added its credential row to §3, `psycopg2-binary`
  to §9), `docs/DOCKER.md` (still said Postgres "isn't built yet" — now
  distinguishes "the Python-level backend is built and live-verified" from
  "no `docker-compose.yml` service exists yet"), and `README.md`'s own
  "SQL backend" section (still only described `mssql`/`sqlite` — now has
  a full PostgreSQL config example, mirroring `CLAUDE.md`'s).
- **Cleanup**: the review found `row_get()` had exactly one production
  call site, which itself did two redundant passes over the same row
  (`row_get()` then a separate `lower_keys()` inside `_row_to_current()`)
  — collapsed to a single `lower_keys()` call, and `row_get()` removed
  entirely (no remaining callers). `migration_run_book.py`'s
  `_apply_log_result()`/`_apply_source_ingestion_result()` each
  re-lowered a row their one caller had already lowered for the whole
  batch — removed the redundant second pass in both.
- **The actual testing-strategy gap the review flagged is now closed
  too**: added `tests/conftest.py`'s `postgres_engine` fixture (skips
  gracefully with no Postgres reachable, matching every contributor's
  machine without one) and `tests/test_load_table_prep_postgres_integration.py`
  (6 tests, including the one case neither backend's suite covered
  before at all — a genuinely non-contiguous Sort range actually being
  reported, not just the clean path), plus a real `postgres:16` service
  in `.github/workflows/tests.yml` so these run automatically in CI, the
  same way the 6 existing `test_*_sqlite_integration.py` files already
  do for SQLite. Every one of this pass's bug classes was found by a
  human manually running `docker run postgres:16` — this is the first
  of that manual verification to become a permanent, automated
  regression guard instead of a one-time check.

Everything genuinely verified live across all four follow-up passes:
`PostgresDialect` itself (including the `column_exists()` fix),
`replicate`/`bulkops`'s own writeback path, hard rules 6/7's
`load_table_prep.py` (now with real reporting-path test coverage, not
just the clean path), `BulkOpsLog`/`OrchestratorRunEvent`/
`SourceIngestionLog`/`ObjectDependency`/`ObjectLoadOrder`/
`ObjectAutomationRisk` DDL + writes + reads, `orchestrator-assess`,
`generate-migration-run-book`, `update-migration-run-book` (both its
`BulkOpsLog` and `SourceIngestionLog` syncs), `reconcile-load-counts`,
`recommend-batch-size` (all three of its seed/automation/history
layers), `suggest-batch-heuristics`, `triage-failures`'s
`ObjectAutomationRisk` cross-reference, `assess-migration-readiness`'s
own `email_deliverability_attested` and `row_count_reconciliation`
gates, and `import-csv-directory` end to end (both new-file and
reused-on-a-later-pass cases).

**What's genuinely still not built**: the actual `docker-compose.yml`
`postgres` service (only CI has a live Postgres wired up so far, via
GitHub Actions' own `services:` block — a local `docker compose up`
still only gets SQL Server). A true end-to-end pass — Docker Compose +
Postgres + Snowfakery mock data + the full replicate/transform/bulkops
methodology together, not individual functions probed by hand — hasn't
been attempted yet.

**Why this, specifically, over other possible third backends**: Postgres
is free, genuinely production-grade (unlike SQLite, which this project
already treats as CI/dev-only, never a real migration project's actual
mirror DB), and the obvious choice for a client environment that doesn't
already run SQL Server — a self-hosted Postgres instance or a managed
one (RDS, Supabase, Cloud SQL) removes the SQL Server licensing question
entirely for a project that has no other reason to run Windows/SQL
Server infrastructure.

**The real scope, stated plainly rather than undersold**: CLAUDE.md's own
"SQL backend" section already lists what's SQL-Server-only *today* as a
"deliberate scope boundary, not an oversight" — `sql/functions/`
(cleansing/matching/lookups, real T-SQL function bodies), plus
`profiling.py`, `auto_mapper.py`, `solution_doc.py`, `parquet_import.py`,
`record_types.py`, `reference_record.py`. Postgres becoming a genuinely
first-class backend (not just "table DDL and basic reads/writes work,"
which is roughly where SQLite already sits) means porting all of those
too, the same one-at-a-time, "port it when a real project needs it"
discipline CLAUDE.md already states for SQLite. Not a reason to avoid
this — just a reason not to promise more than `sql_dialect.py`'s own
seam actually delivers on day one.

**Follow-up pass, same day: the Docker placeholder above is now actually
built, planned via `EnterPlanMode` and verified against a real
container, not an ad hoc one.** `docker-compose.yml` gained a `postgres`
service + its own `app-postgres` variant, structured as Compose
**profiles** (`mssql` default, `postgres` new) rather than a second
override file — Compose merges `depends_on` additively across `-f base
-f override`, so an override adding `postgres` to `app`'s `depends_on`
would NOT have removed the base file's `sqlserver` dependency, forcing
both databases to start on every run; profiles avoid that structurally
by keeping each backend's services (and its own `app-*` variant)
mutually exclusive in one file. `POSTGRES_PASSWORD` mirrors
`MSSQL_SA_PASSWORD`'s existing pattern exactly (a docker-only var,
separate from `.env`'s own `SQL_PWD` a host venv might use for a
different real Postgres server); `COMPOSE_PROFILES=mssql` is set as the
`.env.example` default so a plain `docker compose up -d` with no
`--profile` flag still behaves exactly like before profiles existed.

Two real risks found during planning, not just copy-pasting the
`sqlserver` service:
- **Postgres has no built-in `dbo` schema** the way SQL Server does (its
  own default is `public`), and every `cli.py` command defaults
  `--schema` to `"dbo"` regardless of backend — without an explicit step,
  the first real `replicate`/`bulkops` call against a fresh Postgres
  container would have failed outright with "schema dbo does not
  exist." `docker/init-db.sh` gained a `case "$SQL_BACKEND"` dispatch (the
  mssql branch unchanged) with a new `postgresql` branch: retry
  `psql`-based login (same 120s retry shape as the mssql branch), `CREATE
  DATABASE` only if `pg_database` doesn't already list it (Postgres has
  no `CREATE DATABASE IF NOT EXISTS`), then `CREATE SCHEMA IF NOT EXISTS
  "dbo"` (Postgres does support this one natively).
- **No `psql`/`pg_isready` in the `app` image** — `requirements.txt`'s
  `psycopg2-binary` is Python-only. Added `postgresql-client` to the
  existing apt-get layer that already installs `msodbcsql18`/
  `mssql-tools18`.

`postgres:16` was pinned to match `.github/workflows/tests.yml`'s own CI
service exactly. Its healthcheck uses `pg_isready` — not a repeat of the
`sqlserver` healthcheck's own "is this binary even bundled" uncertainty,
since this repo's own CI already runs `--health-cmd pg_isready` against
this exact image today, a real, already-observed precedent rather than a
new guess.

**Verified live, an 8-step check before spending any further time**: (1)
`pg_isready --version`/`psql --version` confirmed present in the pinned
image directly, not just trusted from the CI precedent; (2) clean-state
`docker compose --profile postgres up -d --build` — `postgres` reached
healthy, `app-postgres` started; (3) `docker compose logs app-postgres`
confirmed `init-db.sh`'s postgres branch actually ran (`CREATE SCHEMA`
in the log); (4) `psql ... -c '\dn'` confirmed the `dbo` schema
genuinely exists — the concrete regression this pass existed to
prevent; (5) `cli.py list-objects` confirmed `jwt`-mode Salesforce auth
works identically to the mssql variant; (6) `cli.py replicate Account`
— see the real bug this one caught, below; (7) `docker compose down`
(no `-v`) then `up` again confirmed idempotent re-run (`"schema dbo
already exists, skipping"`) with data intact; (8) `docker compose
--profile mssql up -d` plus a real `list-objects`/`replicate Account`
confirmed zero regression to the existing SQL Server path after the
profiles refactor.

**A real, previously-undiscovered bug, caught only by step 6 — running
`replicate` through the actual compose network, not a throwaway
container**: `replicate.py`'s boolean-field coercion mapped Salesforce's
CSV `"true"`/`"false"` text to Python integers `1`/`0`
(`chunk[c].map({"true": 1, "false": 0})`). SQL Server's `BIT` and
SQLite's `INTEGER` both silently accept an integer for a boolean-ish
column; Postgres's native `BOOLEAN` column does not — the very first
`replicate Account` against the new container failed outright
(`psycopg2.errors.DatatypeMismatch: column "IsDeleted" is of type
boolean but expression is of type integer`). Fixed by mapping to real
Python `True`/`False` instead — every backend's own driver (pyodbc/
sqlite3/psycopg2) adapts a genuine Python bool to its own column type
correctly, the same way `risk_analyzer.py`'s own `IsActive`/`DirectHit`
`BIT` columns already do. Re-verified: `replicate Account` now writes 5
rows correctly, `IsDeleted` stored as a real Postgres `f`/`t`, and the
data survives the idempotent-restart check (step 7) unchanged.

**What's genuinely still not built, stated plainly**: the actual
migration *methodology* — Snowfakery mock data, a real Postgres-flavored
transform, `bulkops` against a live org — hasn't been run through this
new container yet. This is deliberately a separate, later piece of work,
not scriptable straight through: Hard Rule 2 (Live-Org Write
Confirmation) and Hard Rule 9 (Email Deliverability Attestation) both
require a human, in that live session, to state the org/mode and what
Setup's Deliverability page actually shows — neither has any code
representation to pre-script past, and pre-filling either to make a
pass "fully automated" would defeat the rule's actual purpose even
though nothing in the code would catch it. The prior real dogfood pass
(`_dogfood/brief.yaml` → discovery checklist → mapping → transforms →
live `bulkops` insert against `D360_PLAYGROUND` → pass summary, commit
`3314caf`) is this project's own working definition of "end to end," and
its four existing transform scripts are hand-written T-SQL — not valid
Postgres syntax, so a Postgres pass needs new transform scripts, not a
rerun of the same artifacts.

## 70. FAQ: Fivetran / Apache Hop — why they're not part of this framework (researched — not pursued, out of scope)

Two more technologies raised directly, alongside Docker/PostgreSQL above
— but these two are a genuine "no," not a future roadmap item, so this
entry is written as an FAQ rather than a build plan: the recurring
question ("why doesn't this framework just use X") answered once, in
enough technical depth that it doesn't need re-litigating next time
someone (human or AI session) proposes the same substitution. Same
"Researched — not pursued" convention as #43 (Salesforce GraphQL API) —
measured against the "Scope" section at the top of this file, not
against "is the tool good" in the abstract. Both tools are genuinely
good at what they're built for; neither is built for what this framework
actually does.

**Q: Why not replace `replicate.py`/`bulkops.py` with Fivetran?**

Fivetran is a managed ELT platform: continuous, incremental sync from a
Salesforce connector into a warehouse, with schema-drift handling and
near-real-time refresh. That's a fundamentally different job from what
`replicate.py`/`bulkops.py` do here — a bounded, human-confirmed,
one-time-per-environment migration cutover (Dev → UAT → PROD, per this
framework's own pass model), not an ongoing pipeline that runs forever.
Three concrete mismatches, not just a vibe:

- **Auditability collides with Hard Rule 1 and Hard Rule 10.** Every
  write this framework makes is either a plain Python CLI verb or a
  git-versioned `.sql` file under `sql/transformations/`, with a ticket
  reference required on the file itself — anyone can `git diff`/PR-review
  exactly what a load did and why. Fivetran's own sync/transform logic
  lives inside its managed service, not as exportable, reviewable code —
  adopting it for the *replicate* step would mean the single most
  safety-critical operation (getting live org data into the mirror DB)
  happens inside a black box this repo can't version, diff, or code-review
  at all.
- **The pricing model is built for the wrong shape of workload.**
  Fivetran bills by monthly active rows — steady-state, ongoing
  ingestion. A migration project's actual load pattern is bursty (a
  handful of full-object extracts across Dev/UAT/PROD passes, not a
  continuously-running sync) — paying for a continuous-sync pricing model
  to do a few one-time extracts is the wrong tool's cost curve, not
  just a preference.
- **Where it genuinely *would* make sense**: a client's own separate,
  ongoing BI/analytics warehouse sync is a real and legitimate use of
  Fivetran — just not this framework's job. `replicate.py` and a client's
  existing Fivetran pipeline can coexist without conflict; there's no
  reason to route migration-specific extraction through it instead of the
  direct Salesforce API calls this framework already makes.

**Q: Why not replace hand-written `sql/transformations/*.sql` scripts
with Apache Hop (or Pentaho/Talend-style visual ETL)?**

Apache Hop's core value proposition is a visual pipeline/workflow
designer — pipelines are saved as `.hpl`/`.hwf` XML files carrying
canvas-position metadata, authored and edited through its own Java
desktop app. That's the direct opposite of this framework's foundational
design choice: every transform is a plain, numbered `.sql` file, ticketed
(Hard Rule 10) and reviewed like any other code change, not a GUI
designer's saved canvas state. Concretely:

- **Not meaningfully code-reviewable.** A data architect reviewing a Hop
  pipeline file in a PR is reviewing XML positional/canvas metadata, not
  the actual transformation logic in a form a human reads the way they'd
  read T-SQL — this framework's whole audit trail (Hard Rule 10's ticket
  traceability, `check-mapping-balance`'s diff between a mapping doc and
  the real implemented columns) depends on the transform itself being
  plain, parseable text, which a visual designer's save format isn't.
- **A second runtime and trust boundary for no capability gap.** Hop
  needs its own JVM runtime and project/metadata config alongside the
  Python + SQL Server (or SQLite) this framework already needs — widening
  `docs/SECURITY_OVERVIEW.md`'s trust boundary and adding a whole second
  stack to secure and maintain, without closing any gap in what this
  framework's actual job (SQL Server as the single integration hub, one
  direction in via `replicate`, one direction out via `bulkops`) doesn't
  already do.
- **Where it genuinely *would* make sense**: a client's own pre-existing,
  heterogeneous, multi-source warehouse ETL (flat files, several
  different databases, multiple SaaS APIs chained together) is a real
  problem Hop is built to solve — but that's a different, ongoing
  warehouse-ETL problem than migration cutover remediation, and nothing
  here argues against a client using Hop for that separately, upstream of
  anything this framework touches.

**Conclusion, for both**: neither tool closes a gap in what this
framework's actual scope requires — an audited, git-versioned, one-time-
per-environment Salesforce migration cutover (see "Scope" at the top of
this file) — and adopting either would trade away the core trust model
(everything reviewable in plain git-tracked code) for capabilities aimed
at a genuinely different job (ongoing SaaS sync, general-purpose
heterogeneous visual ETL). Recorded here so this substitution doesn't get
re-proposed without this reasoning being visible first, same as #43.
