# SQL-centric Salesforce migration framework

*AI Assisted Data Migration*

Copyright (c) 2026 JP Ziller LLC. Released under the [MIT License](LICENSE) —
free to use, modify, and redistribute (including commercially), provided the
copyright notice is retained.

A SQL database is the integration hub — SQL Server (the default), SQLite
(`SQL_BACKEND=sqlite`, no server/install required), or PostgreSQL
(`SQL_BACKEND=postgresql`), per project (see "SQL backend: SQL Server,
SQLite, or PostgreSQL" below). Python handles the two directions of
movement: `replicate` (org → SQL) and `bulkops` (SQL → org, with Id/Error
written back). All transformation logic stays in versioned SQL under
`sql/` — T-SQL by convention on the default SQL Server backend, ANSI SQL or
SQLite's own dialect on the other two (a project's own scripts are written
once, in whichever dialect that project's `SQL_BACKEND` actually uses).

See [`docs/MIGRATION_PLAYBOOK.md`](docs/MIGRATION_PLAYBOOK.md) for the
methodology behind this framework — script pattern, row-lock/batching
considerations, object-by-object migration notes, and more. See
[`docs/SECURITY_OVERVIEW.md`](docs/SECURITY_OVERVIEW.md) before a security
review — credential inventory, trust boundaries, and what's actually
code-enforced versus convention-enforced today.

```
org  --replicate-->  SQL Server, SQLite, or PostgreSQL (typed mirror tables)
                         |
                         |  SQL transforms (sql/transformations/*.sql, in git)
                         v
                     *_Load tables  --bulkops-->  org
                         ^                              |
                         |______ Id / Error written back
```

---

## One-time environment setup

Windows host assumed for the steps below (SQL Server's natural home, and
still the default backend); notes for Mac/Linux where they differ, and the
SQLite/PostgreSQL paths below need none of the Windows-specific pieces.
**Follow this order** — later steps depend on earlier ones (noted inline),
so installing out of order means backtracking.

**Using Docker instead?** `docker compose up -d` replaces steps 3–7 below
(Python venv, SQL Server/PostgreSQL engine, SSMS/psql, the driver,
creating the database) with one command — same architecture, just
containerized, with a `postgres` profile alongside the default `mssql`
one (roadmap #69). See [`docs/DOCKER.md`](docs/DOCKER.md) — including a
container-specific auth-mode caveat (`cli` mode doesn't work there; see
"Auth modes" below and `docs/DOCKER.md`'s own auth-mode section for the
full finding).

**Using SQLite instead (`SQL_BACKEND=sqlite`)?** Skip steps 4–7 entirely
(SQL Server, SSMS, the ODBC driver, and creating a database) — SQLite needs
no server, no separate driver install, and no credentials at all. Jump to
"SQL backend: SQL Server, SQLite, or PostgreSQL" below for the config and what's in/out
of scope on that path.

```
Git for Windows ──> clone this repo ──┬─> Python venv + pip install -r requirements.txt
                                       └─> SQL Server Developer Edition ──┬─> SSMS
                                                                          └─> ODBC Driver 18 ──> create SF_Migration DB
Salesforce CLI (sf) ──> auth target org ──> VS Code + Salesforce Extension Pack (auto-detects the auth)
Mockaroo account (optional — only for mock-data generation) ──> API key
GitHub CLI (gh, optional — only for PR/issue workflows) ──> gh auth login
Claude Code (optional, needs Git for Windows) ──> authenticate
                                       all of the above ──> configure .env
```

**1. Git for Windows**
Needed to clone this repo and — separately — to give Claude Code a Bash
shell later. Install from git-scm.com (default options are fine).

**2. Clone this repo**
```bash
git clone https://github.com/jpziller/DataMigration.git
cd DataMigration
```
(If you're starting a brand-new project from this framework as a template
rather than joining this one, `git init` + `git remote add origin <url>` +
push instead — but joining an existing project means cloning, not
re-initializing.)

**3. Python 3.11+**
Install from python.org (check "Add to PATH"). Requires the repo already
cloned (step 2), since `requirements.txt` lives in it:
```bash
py -m venv .venv && .venv\Scripts\activate      # Windows
# python3 -m venv .venv && source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

**4. SQL Server 2022 Developer Edition**
Free, full-featured, from Microsoft's SQL Server downloads page. A "Basic"
installation is enough to start.

**5. SQL Server Management Studio (SSMS)**
**A separate download from the SQL Server engine itself** — the Developer
Edition installer doesn't bundle it. Its own installer offers an
"Install SSMS" shortcut, or get it standalone from Microsoft's SSMS download
page. This is how you'll browse the mirror DB visually, run ad hoc T-SQL, and
review `*_Load` tables by eye. (Mac/Linux: SSMS is Windows-only — Azure Data
Studio or DBeaver are the cross-platform equivalents; `sqlcmd` works
everywhere.)

**6. ODBC Driver 18 for SQL Server**
Install separately from Microsoft — `pyodbc` (step 3) needs this at runtime;
it doesn't ship with the SQL Server engine or with the Python package itself.
Driver 18 encrypts by default, so for a local instance with a self-signed
cert keep `SQL_TRUST_SERVER_CERT=yes` in `.env` (step 14) or connections fail.

**7. Create the mirror database**
In SSMS (step 5) or via `sqlcmd`:
```sql
CREATE DATABASE SF_Migration;
```

**8. Salesforce CLI (`sf`, v2)**
```bash
npm install --global @salesforce/cli
sf --version          # expect 2.x, API 67.0 (Summer '26) or later
```
`sfdx` is deprecated — use `sf`. Auth the target org once:
```bash
sf org login web --alias MIGRATION_TARGET
# sandbox: sf org login web --alias MIGRATION_TARGET --instance-url https://test.salesforce.com
```

**9. VS Code**
Install VS Code, then the **Salesforce Extension Pack** and the **Python**
extension from the marketplace. Open this folder as the workspace. The SF
extensions pick up the `sf`-authed orgs from step 8 automatically — auth
first, or they'll have nothing to detect.

**10. Mockaroo (optional — only needed for `generate-mock-data`)**
Sign up free at mockaroo.com, then get an API key from mockaroo.com/account.
Free tier: 200 requests/day, up to 5,000 records/request. Add it to `.env` in
step 14 — never commit it or paste it into a chat/AI session (see step 14).

**11. GitHub CLI (`gh`, optional — only needed for PR/issue workflows)**
Install from cli.github.com (or `winget install --id GitHub.cli`), then
authenticate once:
```bash
gh auth login
```
Interactive — run it directly in your own terminal (not piped through an
AI assistant) so you can see and respond to the prompts, including the
one-time device code. Choose GitHub.com → HTTPS → login with a web browser.

**12. SFDMU (optional — only needed for `bulkops --engine sfdmu`)**
```bash
sf plugins install sfdmu
```
Needs the `sf` CLI (step 8) already installed — Node.js itself doesn't need
a separate install, it's bundled with the CLI. This is a second, optional
load engine for `bulkops` (`forcedotcom/SFDX-Data-Move-Utility`, Salesforce's
own Apache-2.0-licensed data migration plugin) — the default `python` engine
needs nothing here and is unaffected either way. See "Two `bulkops` load
engines" below for what it's for and its current scope.

**13. Claude Code (optional, but this repo's operating model assumes it)**
Needs Git for Windows (step 1) for its Bash shell. See "Claude Code operating
layer" below for install + setup details.

**14. Configure**
```bash
copy .env.example .env       # cp on Mac/Linux
```
Set `SF_ORG_ALIAS=MIGRATION_TARGET`, your SQL database values for whichever
backend you're using (or, on SQLite, `SQL_BACKEND=sqlite` +
`SQL_SQLITE_DIR`/`SQL_SQLITE_SCHEMAS` — see
"SQL backend: SQL Server, SQLite, or PostgreSQL" below), and (if using mock data)
`MOCKAROO_API_KEY`. `.gitignore` already excludes `.env`, `_stage/`,
`_sqlite/`, and `server.key` — never commit real credentials, and never
paste `.env` contents into a chat session (including with an AI assistant).

---

## Repository structure: template vs. generated

Two categories, and the distinction matters for what gets committed:

**Template content** — the framework itself, always committed, identical
whoever clones this repo:
```
cli.py, config.py, sf_client.py, sql_client.py,        framework code
sql_dialect.py, load_table_prep.py,                    (backend-aware SQL seam;
replicate.py, bulkops.py, type_map.py, metadata.py,      hard rules 6/7 -- see "SQL
parquet_import.py, load_order.py, profiling.py, query_tool.py,  backend" above)
mock_data.py, mapping_doc.py, auto_mapper.py,
solution_doc.py, risk_analyzer.py

reference/field_synonyms.json                           auto-mapping synonym thesaurus
                                                         (grows via real corrections, but the
                                                         starting set is generic/template content)
sql/functions/                                          reusable T-SQL library
validators/system/                                       named checks behind hard rules 6/7/12/15
                                                         (validators/<Object>.md grows per-project,
                                                         same "grows via real corrections" principle)
force-app/                                               reusable field metadata pattern
                                                         (MigrationID__c + its FLS grant)
docs/, CLAUDE.md, README.md, ROADMAP.md                  documentation
.env.example, .mcp.json.example                          config templates (not real config)
```

**`sql/transformations/`** is deliberately neither of the above two categories.
It ships **empty** (just `.gitkeep`, same convention as `mapping/`/`metadata/`
below) -- unlike `sql/functions/`, no illustrative example script lives here,
because a numbered transform is always real, project-specific migration logic
for one client's one object, never a generic template to copy from. The
style/pattern an example would show lives instead in
[`docs/MIGRATION_PLAYBOOK.md`](docs/MIGRATION_PLAYBOOK.md)'s "Migration Script
Pattern" section, as documentation rather than a file sitting in the numbered
sequence. Unlike
the fully-gitignored artifacts below, though, these scripts **are** meant to
be committed to git -- just to that project's own repo/branch, not this
framework's shared template repo, and only once real (built against a real
mapping, not left in as a practice/test artifact). A full reset (wiping a
practice run back to a clean slate) erases every numbered script; a real
client project's scripts persist and are never erased without explicit
approval, even to remove just one.

**Generated, org-specific artifacts** — gitignored by default, because every
org's schema and every project's field mappings are different:
```
metadata/*.json          dump-describe output -- one specific org's schema
mapping/*.xlsx           generate-mapping-doc/auto-map output -- one specific
                         project's field-mapping decisions
*.docx (wherever you point generate-solution-doc)  one specific project's
                         solution document -- put your own copy under
                         version control deliberately if you want one
_stage/                  CSV staging, dropped-in reference docs, scratch work
_sqlite/                 SQLite mirror-DB files (SQL_BACKEND=sqlite projects only)
.env                     real credentials
```

A custom `--template` .docx for `generate-solution-doc` (a data architect's
own branded Word template) is the same kind of org/project-specific,
deliberately-versioned-if-you-want-it artifact -- there's no default
location for it, and none is assumed. The document generator's *own*
default template isn't a file at all -- it's built directly from Python in
`solution_doc.py`, so it's already template content, versioned like the
rest of the framework.

**Also generated, but living in the SQL database rather than as files** —
every table below is a deploy target, safe to drop/regenerate by re-running
the command that built it, never the source of truth for anything git
already tracks (most are backend-agnostic; see "SQL backend" below for the
few that are still SQL-Server-only):

| Table | Written by |
|---|---|
| `dbo.FieldProfile`, `dbo.FieldProfileValues` | `profile-salesforce` / `profile-sql-table` |
| `dbo.ObjectDependency`, `dbo.ObjectLoadOrder` | `analyze-load-order` |
| `dbo.SourceRegistry`, `dbo.AutoMapSuggestions` | `auto-map` |
| `dbo.ObjectAutomationRisk` | `analyze-org-risk` |
| `<Object>_Mock` | `generate-mock-data` |
| `<LoadTable>_Result`, `<LoadTable>_Retry` | `bulkops` (no `key_column`) / `bulkops-retry` |

The one exception worth calling out: `auto-map`'s thesaurus
(`reference/field_synonyms.json`) always originates in git, never in the SQL
database — `dbo.AutoMapSuggestions` stores *results*, not the matching rules
themselves.

If a real engagement wants a versioned copy of its own describe snapshots or
mapping workbook, that's a deliberate choice to make for that project — not
something this template repo assumes for you. (`sql/transformations/*.sql`
is the one exception that genuinely *is* meant to be committed even for a
real project — that's the actual migration logic, the whole point of
keeping it in git per-object as you build it out.)

---

## Auth modes

`SF_AUTH_MODE` in `.env`:

- **`cli`** (default) — reuses the org you authed with `sf org login web`. No
  secrets in the repo. Note: the May 27, 2026 CLI security update redacts the
  access token from `sf org display`, so the framework pulls it via
  `sf org auth show-access-token`. Confirm that command's `--json` result shape
  on your installed CLI (`sf_client.py` handles both known shapes). That same
  update also moved the underlying org authorization itself into the host
  OS's native keychain rather than a plaintext file — fine on a host venv
  (this is exactly that), but it means `cli` mode **cannot** be reused
  inside the Docker container (see `docs/DOCKER.md`'s auth-mode section) —
  use `jwt`/`password` there instead.
- **`jwt`** — connected-app JWT bearer flow. The right choice for CI or an
  unattended migration runner. Needs a connected app + cert (`server.key`).
  **As of Spring '26, Salesforce disabled creating new legacy Connected
  Apps** (confirmed live, not assumed — this framework's own JWT setup was
  tested against a Summer '26 org) — use an **External Client App**
  instead (Setup → External Client App Manager), with OAuth + JWT Bearer
  Flow enabled, the certificate uploaded, and (non-obviously) the
  `refresh_token` scope added even though JWT bearer flow doesn't use one
  — Salesforce's login endpoint rejects the JWT assertion without it
  regardless. See `ROADMAP.md` #18 for the full tested walkthrough,
  including the Data-Cloud-specific `cdp_*` scopes if you need those too.
- **`password`** — username + password + security token. Dev fallback only.

---

## SQL backend: SQL Server, SQLite, or PostgreSQL

`SQL_BACKEND` in `.env` — `mssql` (default), `sqlite`, or `postgresql`
(roadmap #69), per project. Every backend-specific SQL construct
(existence checks, identifier quoting, `SELECT INTO` vs
`CREATE TABLE AS SELECT`, autoincrement PK DDL) routes through
`sql_dialect.py`, keyed off the real engine in hand
(`engine.dialect.name`), so the rest of the framework doesn't need to know
or care which one is active.

**Why you'd pick SQLite**: no server to install, no ODBC driver, no
credentials at all — genuinely useful for a quick trial, a CI/test
environment, or a project that just doesn't want a SQL Server install.
**Why you'd pick PostgreSQL**: free and genuinely production-grade
(unlike SQLite, which this project treats as CI/dev-only) — the obvious
choice for a client environment with no other reason to run Windows/SQL
Server infrastructure; a self-hosted instance or a managed one (RDS,
Supabase, Cloud SQL) removes the SQL Server licensing question entirely.
**Why you'd stick with SQL Server**: it's the fully-featured path — the
whole `sql/functions/` cleansing/matching library (Jaro-Winkler, Soundex,
postal cleansing) and several data-architect tools (`profiling.py`,
`auto_mapper.py`, `solution_doc.py`, `parquet_import.py`,
`record_types.py`, `reference_record.py`) are SQL-Server-only today — a
deliberate scope boundary, not a bug. **What does work on SQLite and
PostgreSQL both**: the actual load engine — `replicate`, `bulkops`
(writeback, activity logging, retry), hard rules 6/7's sort-column/
duplicate-key checks (`add-bulk-load-sort-column`/
`check-load-table-duplicate-keys` — no longer stored procedures on any
backend), `import-csv-directory`'s CSV staging, `snowfakery_data.py`'s
relationship-aware mock data (`generate-related-mock-data`),
`risk_analyzer.py`, `migration_run_book.py`, `mapping_doc.py`,
`load_order.py`, `orchestrator-assess`, `reconcile-load-counts`,
`recommend-batch-size`, and `triage-failures` — all live-verified against
a real Postgres 16 instance, not just reasoned from docs (see
`ROADMAP.md` #69 for the full, dated account).

**Config for SQLite mode**:
```bash
SQL_BACKEND=sqlite
SQL_SQLITE_DIR=./_sqlite          # a directory, not a file
SQL_SQLITE_SCHEMAS=dbo            # comma-separated, e.g. dbo,source,staging
```
One `<schema>.db` file gets created per declared schema under
`SQL_SQLITE_DIR`, each real-`ATTACH DATABASE`'d under its own schema name
on every connection — so an existing `--schema` flag or `schema=` kwarg
anywhere in this codebase already means the right thing on either
backend, no different usage. To look at the data directly: the `sqlite3`
CLI, or any SQLite browser (DB Browser for SQLite, DBeaver, etc.) pointed
at the relevant `<schema>.db` file — no `sqlcmd`/SSMS/MCP setup needed.

**Config for PostgreSQL mode**:
```bash
SQL_BACKEND=postgresql
SQL_SERVER=localhost              # reused from the SQL Server fields --
SQL_DATABASE=SF_Migration          # already backend-generic names
SQL_UID=postgres
SQL_PWD=<your password>
SQL_PORT=5432
SQL_POSTGRES_SSLMODE=prefer        # disable/allow/prefer/require/verify-ca/verify-full
```
Built via `sqlalchemy.engine.URL.create()` (`sql_client.py`'s
`_make_postgres_engine()`), not a hand-rolled connection string, so the
password is redacted by SQLAlchemy's own `repr()`/`str()` by default.
`docker-compose.yml` now has a real `postgres` profile too (`docker
compose --profile postgres up -d`) alongside the default `mssql` one —
see `docs/DOCKER.md` for the full quickstart; these values above are for
a host-installed Postgres or one you're already running elsewhere.

See `ROADMAP.md` #28 for the SQLite design writeup and what was found/fixed
building it (a couple of real `bulk_op()` correctness bugs, unrelated to
SQLite specifically, surfaced by testing both backends live), and #69 for
the equivalent PostgreSQL writeup.

---

## Two `bulkops` load engines: `python` (default) and `sfdmu`

`bulkops`'s `--engine` flag picks which engine actually pushes SQL → org.
Both write Id/Error back into the same SQL Load table the same way (Hard
Rule 4), so `reconcile-load-counts`, `triage-failures`, and
`migration_run_book` sync don't need to know or care which one ran.

**`python` (default, unchanged)** — this framework's own Bulk API 2.0
wrapper (`bulkops.py`). No extra install. Supports insert/update/upsert/
delete, purge-by-filter, dynamic batch sizing, and activity logging.

**`sfdmu`** (opt-in, `--engine sfdmu`) — delegates to
[forcedotcom/SFDX-Data-Move-Utility](https://github.com/forcedotcom/SFDX-Data-Move-Utility)
(Apache-2.0, Salesforce's own actively maintained data migration plugin).
Needs `sf plugins install sfdmu` (step 12 above) — nothing else changes.
**v1 scope, deliberately narrower than the python engine**: upsert/update
only (`--external-id` required — every Load table here already carries a
real migration key, so this matches this framework's own convention
everywhere else); insert/delete aren't supported yet (SFDMU's own
CSV-source insert convention relies on an ambiguous "Id column as
placeholder" scheme for matching results back to source rows, murkier
than upsert/update's real external-id match). A polymorphic lookup field
(e.g. `Task.WhatId`) is automatically skipped rather than guessed at
(`sent_columns.pop`'d before the CSV is built) — load those via the
`python` engine as a separate pass.

**Why bother, given the python engine already works?** SFDMU's
relationship engine correctly resolves an already-loaded parent's real
target Id into a child's lookup field (e.g. `Contact_Load.AccountId`,
already populated by Account's own earlier load) — confirmed live against
this project's own dogfood data, not assumed from docs — via a specific,
non-obvious declaration `sfdmu_bridge.py` builds automatically: the parent
object's query needs more than just `Id` (a bare-`Id` query makes SFDMU
treat it as degenerate and exclude it, silently stripping the child's
lookup along with it), `"externalId": "Id"` (the recognized
"already-resolved, match directly" case), `"operation": "Readonly"`, and
its own tiny source CSV (the distinct already-resolved parent Ids actually
referenced — without one, SFDMU has nothing to correlate the match
against and the field silently resolves blank instead of erroring). See
`sfdmu_bridge.py`'s module docstring for the full account of everything
found live building this — including a genuine Salesforce datetime-parse
failure on every row of this integration's own first real test (the exact
same space-separated-vs-`T`-separated bug `bulk_op()`'s own
`_format_datetime_columns_for_csv()` was built to fix, just never applied
to this second CSV export path until it was found live here too).

**Not yet confirmed**: whether SFDMU offers anything comparable to Hard
Rule 6's `[Sort]`-column lock-contention batching — nothing found in the
installed plugin's own source suggests one; a disclosed gap, not assumed
either way.

---

## Usage

```bash
# Inspect the org
python cli.py list-objects
python cli.py describe Account
python cli.py dump-describe Account          # -> metadata/Account.json (gitignored by default -- see "Repository structure")

# Ad hoc query (console, or --csv/--excel to export)
python cli.py query "SELECT Id, Name, Account.Name FROM Contact LIMIT 10"

# Replicate org -> SQL (typed columns)
python cli.py replicate Account
python cli.py replicate Contact --where "CreatedDate = LAST_N_DAYS:30"
python cli.py replicate Opportunity --raw    # all raw-text type (NVARCHAR(MAX) on
                                              # SQL Server, TEXT on SQLite/PostgreSQL); CAST in SQL

# Import a Parquet file -> typed SQL Server table (column types inferred
# from the file's own schema -- no coercion step, unlike Salesforce's
# always-text Bulk API CSV extracts). Drops/recreates by default.
python cli.py import-parquet ./data/accounts.parquet SourceAccounts
python cli.py import-parquet ./data/accounts_part2.parquet SourceAccounts --append

# Profile a field's population/min/max/distinct/value distribution --
# either directly from Salesforce or from an already-replicated SQL table
python cli.py profile-salesforce Account
python cli.py profile-sql-table Account
python cli.py export-profile-excel profile.xlsx

# Recommended load order for a set of objects (parents before children)
python cli.py analyze-load-order Account Contact Opportunity

# Generate mock/demo data via Mockaroo -> dbo.<Object>_Mock (needs MOCKAROO_API_KEY)
python cli.py generate-mock-data Account --count 50

# Field-mapping workbook -- one shared file, one tab per object (reuse the
# same output path across objects; it adds/replaces that object's sheet,
# not the whole file). One row per SOURCE field from the named SQL table,
# blank Target block for a human to fill in -- doesn't guess the mapping.
python cli.py generate-mapping-doc Account mapping/Migration_Mapping.xlsx SourceAccounts
python cli.py generate-mapping-doc Contact mapping/Migration_Mapping.xlsx SourceContacts
python cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/<NNN>_account_load.sql

# Auto-suggest a mapping into that doc's Target block/Notes/Migrate Data
# columns -- requires the source table to already be profiled. Matches by
# exact/normalized name, then reference/field_synonyms.json, then fuzzy
# string matching, and downgrades any match if the source field's profiled
# population/distinct-value data says it isn't worth migrating. Never
# overwrites a row a human already filled in.
python cli.py auto-map Account mapping/Migration_Mapping.xlsx SourceAccounts

# Auto-draft a migration solution/design document (Word) from load-order
# analysis + a mapping doc + profiling data. No binary template lives in
# git -- the default is built entirely from Python (solution_doc.py); pass
# --template to swap in your own branded .docx instead.
python cli.py generate-solution-doc Solution.docx Account Contact Opportunity \
    --mapping-path mapping/Migration_Mapping.xlsx --company "Acme Corp" --appendix

# Transform in SQL (sql/transformations/*.sql) to build *_Load tables --
# T-SQL by default, ANSI SQL/SQLite's dialect on the other two backends

# Load SQL -> org, with Id/Error written back into the load table.
# Every sent column is checked against the target object's live describe()
# before the API is ever called -- a typo'd/removed/non-writable field
# aborts up front instead of burning a real Bulk API batch to find out.
# insert/upsert also require --email-deliverability (see below).
python cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c --email-deliverability system-email-only
python cli.py bulkops Contact insert Contact_Load --key-column LoadId --email-deliverability no-access
python cli.py bulkops Case delete Case_Purge --key-column LoadId

# Delete by external id -- Bulk API 2.0's delete only ever accepts a real
# Id, so this resolves external id values to real Ids via a query first,
# then deletes the resolved rows. A value with no matching org record
# never reaches the API; it's reported back as a clear local error.
python cli.py bulkops Account delete Account_Purge --external-id Legacy_Id__c

# Purge test data by filter -- no delete load table needed. Dry-run first
# (reports the matched count + sample Ids, touches nothing), then delete.
# No delete-everything default: purging a whole object means writing
# "Id != null" explicitly. Standard Recycle-Bin-recoverable delete only.
python cli.py bulkops Account delete --where "AccountNumber LIKE 'MOCKACCT-%'" --dry-run
python cli.py bulkops Account delete --where "AccountNumber LIKE 'MOCKACCT-%'"

# After a load with failures: copy only the failed rows into a fresh
# <table>_Retry table (does not call Salesforce itself), then resubmit
# just that table via a normal, separately-confirmed bulkops call.
python cli.py bulkops-retry Contact_Load
python cli.py bulkops Contact insert Contact_Load_Retry --key-column LoadId

# Before a load: what automation on the target org might interfere?
# (validation rules, Apex triggers, record-triggered Flows, workflow rules,
# approval processes -- object-level inventory, not a formula parser)
python cli.py analyze-org-risk Account Contact Opportunity --mapping-path mapping/Migration_Mapping.xlsx

# Data Cloud (D360) -- all confirmed live against a real Data Cloud org.
# Basic DLO/DMO lookups need no special command (plain `query` works on
# __dlo/__dlm objects); these cover what that path can't do. The three
# query commands need an External Client App with cdp_* OAuth scopes
# (see "Auth modes" above); the status checks are plain core-org SOQL.
python cli.py data-cloud-query "SELECT FromISOCurrencyCode__c FROM StaticCurrencyRates_Home__dlm"
python cli.py list-calculated-insights
python cli.py query-calculated-insight RateCount__cio
python cli.py data-cloud-profile UnifiedssotIndividualIndv__dlm "[ssot__LastName__c=Smith]"
python cli.py list-data-graphs
python cli.py data-cloud-status data-stream          # or: calculated-insight, dso,
python cli.py data-cloud-status identity-resolution  #     data-transform, data-graph
```

Matching slash-command skills exist for the read-only ones (`/list-objects`,
`/describe`, `/dump-describe`, `/record-counts`, `/query`, `/profile`, `/analyze-load-order`,
`/generate-mock-data`, `/generate-related-mock-data`, `/generate-mapping-doc`,
`/check-mapping-balance`, `/auto-map`, `/generate-solution-doc`,
`/bulkops-retry`, `/analyze-org-risk`, `/import-parquet`, `/replicate`,
`/build-load`, `/validate-load`, `/status`, `/data-cloud-query`,
`/data-cloud-status`, `/data-cloud-profile`, `/list-calculated-insights`,
`/query-calculated-insight`, `/list-data-graphs`, `/recommend-batch-size`,
`/suggest-batch-heuristics`, `/generate-migration-run-book`, `/add-migration-run-book-pass`, `/update-migration-run-book`)
— see "Claude Code operating layer" below.

---

## Result mapping — read this before you trust `Error`

Bulk API 2.0 returns **separate** successful/failed record sets with no
guaranteed order between them, so this framework does **not** map results by row
position. It fingerprints each submitted row by its sent business columns and
joins results back on that fingerprint:

- **update / upsert / delete** send `Id` (or an external id) → fingerprint is
  unique → exact mapping.
- **insert** has no Id yet. Put a **unique migration-key column** among the sent
  columns — mapped to a real SF external-id text field (e.g. `Legacy_Id__c`) —
  so the fingerprint is guaranteed unique. A project's own numbered transform
  under `sql/transformations/` (e.g. `SELECT CAST(<mock/source row id> AS ...)
  AS Legacy_Id__c`) is where this pattern actually gets built. Rows identical
  across every sent column are genuinely ambiguous and counted in the
  `ambiguous` field of the summary.

Writeback target: if the load table has the `key_column` (default `LoadId`),
`Id`/`Error` are updated in place. Otherwise a `<table>_Result` table is
written instead.

**Pre-flight check.** Before any of the above, every column about to be sent
is checked against the target object's live `describe()`: does the field
exist, and can this operation actually write it (`createable` for insert,
`updateable` for update/upsert)? Either failure aborts the whole call before
it ever reaches the Bulk API -- Salesforce would reject it for the same
reason anyway, just after spending a real batch to find out. A
required-but-unsent field on insert is reported as a warning, not a hard
stop, since automation could still default it.

**Email Deliverability attestation (insert/upsert only).** insert/upsert
can create brand-new records that trigger outbound email to real external
contacts. Salesforce has no supported API to *read* the org's Email
Deliverability setting (confirmed: retrieved `EmailAdministrationSettings`
live and cross-checked Salesforce's own field reference -- neither has any
such field), so this can't be an automated check -- `--email-deliverability
no-access|system-email-only|all-email` is a required, explicit human
attestation instead, based on actually checking Setup > Email
Administration > Deliverability first. Missing it raises before the API is
ever touched; `all-email` additionally requires
`--confirm-external-email-risk`, since that's the one state that can
genuinely send real mail externally. The confirmed value is echoed back in
the load's own result output either way.

**Retrying a partial failure.** `bulkops-retry <table>` copies only the
failed rows (`Error` populated) from a load table or its `_Result` table
into a fresh `<table>_Retry` table. It does not call Salesforce itself --
resubmit the new table via a normal, separately-confirmed `bulkops` call
once you've looked at *why* those rows failed (the same root cause across
every failure usually means the transform needs a fix, not a blind retry).

**Delete by external id.** Bulk API 2.0's delete operation only ever
accepts the real Salesforce `Id` -- unlike update/upsert, it has no
`externalIdFieldName` equivalent. `bulkops <Object> delete <table>
--external-id <field>` resolves external id values to real Ids via a SOQL
query first, then deletes the resolved rows. A value with no matching org
record never reaches the API at all -- it's reported back as a clear,
locally-generated error on that row, the same shape as any other failure.

---

## Known limitations, honestly

- **Incremental refresh is not built.** Add it as a `replicate` variant
  filtering `SystemModstamp >` the last watermark and `MERGE`-ing into the
  mirror. The hook is obvious in `replicate.py`; it's just not written.
- **Compound fields** (`address`, `location`) are skipped; their components
  (`BillingStreet`, etc.) are replicated instead — same net result,
  different column set than a naive `SELECT *`.
- **Type coercion at load.** Typed replicate maps real Salesforce booleans to
  real Python `True`/`False`, which every backend's driver adapts correctly
  (`BIT` on SQL Server, `INTEGER` on SQLite, native `BOOLEAN` on
  PostgreSQL) — confirmed live: an earlier `0`/`1` integer mapping worked
  fine on SQL Server/SQLite but Postgres's `BOOLEAN` column rejects an
  integer outright, so this had to become a real bool (`ROADMAP.md` #69).
  Datetimes are loaded as ISO strings — on SQL Server this relies on implicit
  conversion into `DATETIME2` (verify on your first datetime-heavy object);
  on SQLite there's no enforced column typing to rely on at all (type
  *affinity*, not enforcement), so a malformed value wouldn't error the way
  SQL Server's/PostgreSQL's strict typing would — use `--raw` and `CAST`
  during transform if you need to double-check this on any backend.
- **Performance.** Replicate loads via `to_sql` + `fast_executemany`. Fine into
  the low millions on SQL Server. For very large objects there, swap the load
  step for `BULK INSERT` against the staged CSVs (the SQL Server service
  account must be able to read the file) or `bcp` — both are markedly faster
  at scale; PostgreSQL's `COPY` is the equivalent lever there, not yet
  exercised in this framework at real volume. On SQLite, `sql_client.py`'s
  connect hook sets `PRAGMA journal_mode=WAL`/`synchronous=NORMAL`/
  `busy_timeout` for real write throughput, but SQLite is still
  single-writer — it's the lighter-weight option, not the higher-throughput
  one.
- **Open bug: `Contact.MigrationID__c` FLS.** Deployed with a bundled `Admin`
  profile FLS grant (see hard rule 8), and both a SOQL query and a
  `FieldPermissions` query confirmed System Administrator had access right
  after deploy — but Setup UI's field-level-security page shows it as hidden
  for that profile. Not yet root-caused (stale UI cache vs. a second
  permission layer the API check didn't surface). `Account.MigrationID__c`
  and `Opportunity.MigrationID__c` don't show this symptom.

---

## Claude Code operating layer

Claude Code drives this repo through a deliberate split: **read-only eyes** on
the mirror DB (SQL Server, SQLite, or PostgreSQL, per project), **reviewed
hands** for mutations.

- `CLAUDE.md` — loaded every session; the rules and canonical commands.
- `.claude/settings.json` — permissions. Read/inspect/replicate and git-read run
  without prompts; `bulkops` (writes to Salesforce), `git commit`/`push`, and
  `sf project deploy` are gated behind an approval prompt; secrets and dangerous
  commands are denied outright.
- `.claude/commands/` — slash commands: `/list-objects`, `/describe <Object>`,
  `/dump-describe <Object>`, `/query <SOQL>`, `/profile <Object>`,
  `/analyze-load-order <Objects...>`, `/generate-mock-data <Object>`,
  `/generate-mapping-doc <Object> <path.xlsx> <SourceTable>`,
  `/check-mapping-balance <Object> <mapping.xlsx> <transform.sql>`,
  `/auto-map <Object> <mapping.xlsx> <SourceTable>`,
  `/generate-solution-doc <output.docx> <Objects...>`,
  `/bulkops-retry <LoadTable>`, `/analyze-org-risk <Objects...>`,
  `/import-parquet <path.parquet> <table>`,
  `/replicate <Object>`, `/build-load <path.sql>`, `/validate-load <LoadTable>`,
  `/recommend-batch-size <Object>`, `/suggest-batch-heuristics`,
  `/generate-migration-run-book <path.xlsx> --tab <name>`,
  `/add-migration-run-book-pass <path.xlsx> --from-tab <name> --to-tab <name>`,
  `/status`.

**Install Claude Code (Windows, native — no WSL needed):**
```powershell
irm https://claude.ai/install.ps1 | iex     # native installer, no Node.js
# also install Git for Windows so Claude Code gets Git Bash as its shell
claude            # authenticate (Pro/Max/Team/Enterprise account)
```
Open the repo folder in VS Code and add the **Claude Code** extension for the
diff viewer, or run `claude` from the integrated terminal. Run `/doctor` to
verify.

**Let Claude Code see SQL Server** — pick a tier:
1. **sqlcmd (zero setup, most reliable on Windows).** Already allowed in
   settings; Claude Code introspects via `sqlcmd -S localhost -E -d SF_Migration -Q "..."`.
2. **DBHub read-only MCP** — nicer schema tools. Register locally so no
   credentials hit the repo:
   ```
   claude mcp add dbhub -- npx -y @bytebase/dbhub --transport stdio --readonly --dsn "<sqlserver-dsn>"
   ```
   (`--` separates the CLI's args from the server's — omit it and arg parsing
   breaks. Confirm the SQL Server DSN scheme in the DBHub README; use a
   read-only login.) `.mcp.json.example` is a reference template.
3. **Microsoft's official SQL Server MCP server** (.NET, first-party) — the
   choice once this graduates from prototyping.

Whichever tier: point the MCP/login at a **read-only** account. Table drops and
loads go through the reviewed Python CLI, never the MCP.

**On a SQLite-backed project (`SQL_BACKEND=sqlite`)**, none of the above
applies — no server, no ODBC driver, no read-only login to provision, no
MCP setup. Claude Code (or you) can just read the `<schema>.db` files
under `SQL_SQLITE_DIR` directly via the `sqlite3` CLI or a plain file
read; the "read-only eyes, reviewed hands" split still holds (introspect
freely, mutations go through the Python CLI), it's just a smaller trust
surface to begin with.

**On a PostgreSQL-backed project (`SQL_BACKEND=postgresql`)**, the same
tiered approach applies with Postgres-native tooling instead: `psql` is the
zero-setup option (parallel to `sqlcmd` above — a read-only login, same
"table drops and loads go through the reviewed Python CLI, never the MCP"
rule), or a Postgres-specific read-only MCP server if you want nicer schema
tools. No SQL Server/ODBC pieces apply on this path at all.

Next-level guardrail (not shipped): a `PreToolUse` hook in `.claude/settings.json`
that vetoes `bulkops` against a production org alias, or any `DROP`/`TRUNCATE`
against a non-`SF_Migration` database.

**Scheduled wakeups for long-running jobs.** Standard Claude Code capability,
not anything built into this framework — worth knowing about specifically
because Data Cloud work (`data-cloud-status`, `ROADMAP.md` #18/#20) involves
genuinely async jobs (Calculated Insight processing, Identity Resolution
runs, DSO/Data Stream refreshes) that take real time to finish. Rather than
sitting idle mid-conversation, Claude Code can schedule itself to wake up
after a delay (seconds up to an hour) and re-run a check — e.g. "poll
`data-cloud-status identity-resolution` every couple of minutes until
`LastRunStatus` leaves `IN_PROGRESS`, then report the final result." Just
ask directly ("keep checking until it's done," "check back in 5 minutes").
Scoped to the current session only — it doesn't persist once the session
ends, and it's not email/SMS/push notification (Claude Code has no built-in
way to text or email you; a Gmail/Calendar integration can be authenticated
separately if that's wanted, but that's a distinct capability from this).

**Optional Gmail/Calendar/Drive integration.** Separately from the above,
Claude Code can connect to a real Gmail/Google Calendar/Google Drive
account via an authenticated MCP connector — not set up for this project,
and not required for anything this framework does, but worth knowing it
exists: an architect could authenticate their own (or a project) account
and have Claude Code read/send email, check a calendar, or pull files from
Drive as part of a session, e.g. a real notification when a long Data Cloud
job finishes rather than only in-session polling. Nothing here does this
today — it's a capability to reach for later if a real need shows up, not
a recommendation to wire it in now.

## Untested paths to verify on first run

1. `sf org auth show-access-token --json` result shape (cli auth mode).
2. Datetime string → `DATETIME2` on your first datetime-heavy replicate
   (SQL Server backend only — SQLite's type affinity has no equivalent
   conversion step to verify).
3. `get_failed_records` / `get_successful_records` kwarg names on your installed
   `simple-salesforce` (this code reads the returned CSV text, avoiding the
   `path=` vs `file=` divergence between versions).
