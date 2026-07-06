# SQL-centric Salesforce migration framework

*AI Assisted Data Migration*

Copyright (c) 2026 JP Ziller LLC. Released under the [MIT License](LICENSE) —
free to use, modify, and redistribute (including commercially), provided the
copyright notice is retained.

SQL Server is the integration hub. Python handles the two directions of
movement: `replicate` (org → SQL) and `bulkops` (SQL → org, with Id/Error
written back). All transformation logic stays in T-SQL, version-controlled in
`sql/`.

```
org  --replicate-->  SQL Server (typed mirror tables)
                         |
                         |  T-SQL transforms (sql/transformations/*.sql, in git)
                         v
                     *_Load tables  --bulkops-->  org
                         ^                              |
                         |______ Id / Error written back
```

---

## One-time environment setup

Windows host assumed (SQL Server's natural home); notes for Mac/Linux where
they differ. **Follow this order** — later steps depend on earlier ones
(noted inline), so installing out of order means backtracking:

```
Git for Windows ──> clone this repo ──┬─> Python venv + pip install -r requirements.txt
                                       └─> SQL Server Developer Edition ──┬─> SSMS
                                                                          └─> ODBC Driver 18 ──> create SF_Migration DB
Salesforce CLI (sf) ──> auth target org ──> VS Code + Salesforce Extension Pack (auto-detects the auth)
Mockaroo account (optional — only for mock-data generation) ──> API key
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
cert keep `SQL_TRUST_SERVER_CERT=yes` in `.env` (step 12) or connections fail.

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
step 12 — never commit it or paste it into a chat/AI session (see step 12).

**11. Claude Code (optional, but this repo's operating model assumes it)**
Needs Git for Windows (step 1) for its Bash shell. See "Claude Code operating
layer" below for install + setup details.

**12. Configure**
```bash
copy .env.example .env       # cp on Mac/Linux
```
Set `SF_ORG_ALIAS=MIGRATION_TARGET`, your SQL Server values, and (if using
mock data) `MOCKAROO_API_KEY`. `.gitignore` already excludes `.env`,
`_stage/`, and `server.key` — never commit real credentials, and never paste
`.env` contents into a chat session (including with an AI assistant).

---

## Auth modes

`SF_AUTH_MODE` in `.env`:

- **`cli`** (default) — reuses the org you authed with `sf org login web`. No
  secrets in the repo. Note: the May 27, 2026 CLI security update redacts the
  access token from `sf org display`, so the framework pulls it via
  `sf org auth show-access-token`. Confirm that command's `--json` result shape
  on your installed CLI (`sf_client.py` handles both known shapes).
- **`jwt`** — connected-app JWT bearer flow. The right choice for CI or an
  unattended migration runner. Needs a connected app + cert (`server.key`).
- **`password`** — username + password + security token. Dev fallback only.

---

## Usage

```bash
# Inspect the org
python cli.py list-objects
python cli.py describe Account
python cli.py dump-describe Account          # -> metadata/Account.json (commit it)

# Ad hoc query (console, or --csv/--excel to export)
python cli.py query "SELECT Id, Name, Account.Name FROM Contact LIMIT 10"

# Replicate org -> SQL (typed columns)
python cli.py replicate Account
python cli.py replicate Contact --where "CreatedDate = LAST_N_DAYS:30"
python cli.py replicate Opportunity --raw    # all NVARCHAR(MAX); CAST in T-SQL

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
python cli.py check-mapping-balance Account mapping/Migration_Mapping.xlsx sql/transformations/010_account_load.sql

# Transform in T-SQL (sql/transformations/*.sql) to build *_Load tables

# Load SQL -> org, with Id/Error written back into the load table
python cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c
python cli.py bulkops Contact insert Contact_Load --key-column LoadId
python cli.py bulkops Case delete Case_Purge --key-column LoadId
```

Matching slash-command skills exist for the read-only ones (`/query`,
`/profile`, `/analyze-load-order`, `/generate-mock-data`, `/replicate`,
`/build-load`, `/validate-load`, `/status`) — see "Claude Code operating
layer" below.

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
  so the fingerprint is guaranteed unique. `sql/transformations/010_account_load.sql`
  shows the pattern. Rows identical across every sent column are genuinely
  ambiguous and counted in the `ambiguous` field of the summary.

Writeback target: if the load table has the `key_column` (default `LoadId`),
`Id`/`Error` are updated in place. Otherwise a `<table>_Result` table is
written instead.

---

## Known limitations, honestly

- **Incremental refresh is not built.** Add it as a `replicate` variant
  filtering `SystemModstamp >` the last watermark and `MERGE`-ing into the
  mirror. The hook is obvious in `replicate.py`; it's just not written.
- **Compound fields** (`address`, `location`) are skipped; their components
  (`BillingStreet`, etc.) are replicated instead — same net result,
  different column set than a naive `SELECT *`.
- **Type coercion at load.** Typed replicate maps booleans `true/false → 1/0`.
  Datetimes are loaded as ISO strings and rely on SQL Server's implicit
  conversion into `DATETIME2` — verify on your first datetime-heavy object, or
  use `--raw` and `CAST` in T-SQL (which also fits the SQL-centric method).
- **Performance.** Replicate loads via `to_sql` + `fast_executemany`. Fine into
  the low millions. For very large objects, swap the load step for `BULK INSERT`
  against the staged CSVs (the SQL Server service account must be able to read
  the file) or `bcp` — both are markedly faster at scale.
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
SQL Server, **reviewed hands** for mutations.

- `CLAUDE.md` — loaded every session; the rules and canonical commands.
- `.claude/settings.json` — permissions. Read/inspect/replicate and git-read run
  without prompts; `bulkops` (writes to Salesforce), `git commit`/`push`, and
  `sf project deploy` are gated behind an approval prompt; secrets and dangerous
  commands are denied outright.
- `.claude/commands/` — slash commands: `/query <SOQL>`, `/profile <Object>`,
  `/analyze-load-order <Objects...>`, `/generate-mock-data <Object>`,
  `/replicate <Object>`, `/build-load <path.sql>`, `/validate-load <LoadTable>`,
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

Next-level guardrail (not shipped): a `PreToolUse` hook in `.claude/settings.json`
that vetoes `bulkops` against a production org alias, or any `DROP`/`TRUNCATE`
against a non-`SF_Migration` database.

## Untested paths to verify on first run

1. `sf org auth show-access-token --json` result shape (cli auth mode).
2. Datetime string → `DATETIME2` on your first datetime-heavy replicate.
3. `get_failed_records` / `get_successful_records` kwarg names on your installed
   `simple-salesforce` (this code reads the returned CSV text, avoiding the
   `path=` vs `file=` divergence between versions).
