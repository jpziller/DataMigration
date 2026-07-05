# SQL-centric Salesforce migration framework (DBAmp replacement)

*AI Assisted Data Migration*

SQL Server is the integration hub. Python plays the role DBAmp's stored procs
play: `SF_Replicate` (org → SQL) and `SF_BulkOps` (SQL → org, with Id/Error
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

Run in this order. Windows host assumed (SQL Server + DBAmp's natural home);
notes for Mac/Linux where they differ.

**1. Python 3.11+**
Install from python.org (check "Add to PATH"). Then:
```bash
py -m venv .venv && .venv\Scripts\activate      # Windows
# python3 -m venv .venv && source .venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

**2. SQL Server + ODBC Driver 18**
Any current SQL Server edition (Developer edition is free and full-featured).
Then install **Microsoft ODBC Driver 18 for SQL Server** separately — pyodbc
needs it and it does not ship with the engine. Create the database:
```sql
CREATE DATABASE SF_Migration;
```
Driver 18 encrypts by default, so for a local instance with a self-signed cert
keep `SQL_TRUST_SERVER_CERT=yes` in `.env` or connections will fail.

**3. Salesforce CLI (`sf`, v2)**
```bash
npm install --global @salesforce/cli
sf --version          # expect 2.x, API 67.0 (Summer '26) or later
```
`sfdx` is deprecated — use `sf`. Auth the target org once:
```bash
sf org login web --alias MIGRATION_TARGET
# sandbox: sf org login web --alias MIGRATION_TARGET --instance-url https://test.salesforce.com
```

**4. VS Code**
Install VS Code, then the **Salesforce Extension Pack** and the **Python**
extension from the marketplace. Open this folder as the workspace. The SF
extensions pick up the `sf`-authed orgs automatically.

**5. GitHub**
```bash
git init
git remote add origin <your-repo-url>
git add . && git commit -m "migration framework scaffold"
git push -u origin main
```
`.gitignore` already excludes `.env`, `_stage/`, and `server.key`. The point of
git here is the `sql/` tree — every transform reviewed and versioned.

**6. Configure**
```bash
copy .env.example .env       # cp on Mac/Linux
```
Set `SF_ORG_ALIAS=MIGRATION_TARGET` and your SQL Server values.

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

# Replicate org -> SQL (typed columns, DBAmp-style)
python cli.py replicate Account
python cli.py replicate Contact --where "CreatedDate = LAST_N_DAYS:30"
python cli.py replicate Opportunity --raw    # all NVARCHAR(MAX); CAST in T-SQL

# Transform in T-SQL (sql/transformations/*.sql) to build *_Load tables

# Load SQL -> org, with Id/Error written back into the load table
python cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c
python cli.py bulkops Contact insert Contact_Load --key-column LoadId
python cli.py bulkops Case delete Case_Purge --key-column LoadId
```

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

## Fidelity vs. DBAmp — where this differs, honestly

- **`SF_Refresh` (incremental) is not built.** Add it as a `replicate` variant
  filtering `SystemModstamp >` the last watermark and `MERGE`-ing into the
  mirror. The hook is obvious in `replicate.py`; it's just not written.
- **Compound fields** (`address`, `location`) are skipped; their components
  (`BillingStreet`, etc.) are replicated instead. Same net result as DBAmp,
  different column set than a naive `SELECT *`.
- **Type coercion at load.** Typed replicate maps booleans `true/false → 1/0`.
  Datetimes are loaded as ISO strings and rely on SQL Server's implicit
  conversion into `DATETIME2` — verify on your first datetime-heavy object, or
  use `--raw` and `CAST` in T-SQL (which also fits the SQL-centric method).
- **Performance.** Replicate loads via `to_sql` + `fast_executemany`. Fine into
  the low millions. For very large objects, swap the load step for `BULK INSERT`
  against the staged CSVs (the SQL Server service account must be able to read
  the file) or `bcp` — both are markedly faster at scale.

---

## Claude Code operating layer

Claude Code drives this repo through a deliberate split: **read-only eyes** on
SQL Server, **reviewed hands** for mutations.

- `CLAUDE.md` — loaded every session; the rules and canonical commands.
- `.claude/settings.json` — permissions. Read/inspect/replicate and git-read run
  without prompts; `bulkops` (writes to Salesforce), `git commit`/`push`, and
  `sf project deploy` are gated behind an approval prompt; secrets and dangerous
  commands are denied outright.
- `.claude/commands/` — slash commands: `/replicate <Object>`,
  `/build-load <path.sql>`, `/validate-load <LoadTable>`, `/status`.

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
