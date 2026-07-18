# Security Overview

Copyright (c) 2026 JP Ziller LLC. Released under the [MIT License](../LICENSE).

Audience: a security team evaluating whether to allow this framework to run
against a real SQL Server instance and a real Salesforce org. This document
describes what actually exists today, as implemented in this repo -- not an
aspirational target state. It should be updated whenever a change alters a
trust boundary (a new credential type, a new network listener, a UI, SSO,
etc.), not just when someone remembers to.

To report a vulnerability in this framework itself, see
[`SECURITY.md`](../SECURITY.md) (private reporting via GitHub Security
Advisories) -- this document is the architecture overview, not the
reporting channel.

---

## 1. What this is, in one paragraph

A Python CLI, driven interactively by a human operator through Claude Code,
that moves data between a Salesforce org and a local/on-prem SQL Server
database (`SF_Migration`). There is no server process, no listening network
port, and no multi-user access model -- it is a command-line tool one
already-credentialed operator runs at a terminal, the same trust model as
any admin script or `sqlcmd`/Data Loader session.

## 2. Components and trust boundaries

```
Human operator (has their own SQL Server + Salesforce credentials already)
        |
        v
Claude Code (local process; sends conversation + tool output to Anthropic's
             API as part of normal operation -- see §6)
        |
        v
cli.py (Python, runs locally, under the operator's own OS-level permissions)
   |                                   |
   v                                   v
SQL Server "SF_Migration"        Salesforce org (via simple-salesforce /
(local integration hub;           Bulk API 2.0 REST endpoints; also the
 or local SQLite files,           /limits/recordCount REST resource for
 SQL_BACKEND=sqlite,              `record-counts` -- same core-org token,
 roadmap #28 -- no server         same host, no new boundary)
 process, no credential
 of any kind)
```

**Optional containerized variant** (`Dockerfile`/`docker-compose.yml`,
roadmap #68): the same `cli.py`/SQL Server/Salesforce architecture above,
just running inside Docker rather than directly on the operator's host —
not a new top-level actor. One trust-boundary-relevant difference worth
naming here rather than only in `docs/DOCKER.md`: the default `cli`
auth mode's credential (see §3) lives in the host OS's own keychain as of
the May 2026 CLI update, which a Linux container has no way to reach —
`cli` mode is simply unusable inside this container, `jwt`/`password`
only. Nothing else about the trust model changes; see `docs/DOCKER.md`
for the full container-specific auth-mode finding and §9 for this
variant's own supply-chain surface.

Two purely local surfaces worth naming for completeness (no network
involvement beyond what's above): the Migration Run Book
(`migration_run_book.py`) shells out to the local `git` binary
(`remote get-url` / `rev-parse`, fixed argument lists, no shell
interpolation) to stamp commit breadcrumbs into generated workbooks, and
reads/writes local `.xlsx` files -- see §5 for what those workbooks can
contain.

Three optional external services/hops, none in the critical data path by
default:

- **Mockaroo API** (`generate-mock-data`) -- outbound HTTPS call with a field
  *schema* (names/types), never real record data. Returns synthetic rows.
  Off unless `MOCKAROO_API_KEY` is set.
- **DBHub MCP** (`@bytebase/dbhub`, optional, see `.mcp.json.example`) --
  a third-party MCP server for nicer read-only SQL Server browsing from
  inside Claude Code. Fetched at invocation time via `npx` unless a security
  team pins/vendors it first -- treat that supply-chain detail as a real
  review item if this is adopted, same as any `npx`-fetched tool. Configured
  read-only (`--readonly`) and intended to be run with a read-only SQL login.
- **Data Cloud tenant hop** (`data_cloud.py`; `data-cloud-query`,
  `list-calculated-insights`, `query-calculated-insight`,
  `data-cloud-profile`, `list-data-graphs` -- see `ROADMAP.md` #18) --
  an additional OAuth exchange off an already-valid core-org session, to
  a genuinely separate host (`*.c360a.salesforce.com`). Only reached when
  those specific commands are used; extends the same Salesforce leg of
  the diagram above rather than adding a new top-level actor. The six
  `data-cloud-status` checks (Calculated Insight/Data Stream/DSO/
  Identity Resolution/Data Transform/Data Graph) do **not** use this hop
  at all -- confirmed live, they're plain core-org SOQL like everything
  else in this list.
- **SFDMU** (`sfdmu_bridge.py`; `bulkops --engine sfdmu`, see `ROADMAP.md`
  #71) -- an opt-in second load engine, `forcedotcom/SFDX-Data-Move-Utility`,
  installed once via `sf plugins install sfdmu` (a supply-chain
  consideration worth the same scrutiny as DBHub's `npx` fetch above,
  though this one is a signed `sf` CLI plugin rather than an
  invocation-time `npx` pull) and invoked as a subprocess
  (`subprocess.run(["sf", "sfdmu", "run", ...], shell=True on Windows)` --
  a second, independent shell-out surface alongside `sf_client.py`'s own
  `_run_sf()`, both now routed through one shared, arg-allowlisted
  `run_sf_cli()` seam). Unlike DBHub, this is in the live **write** path
  when used: it authenticates against the same already-configured target
  org and pushes real record data to Salesforce via its own CSV staging
  files under `_stage/sfdmu/<object>/` (deleted and rebuilt on every
  call). Off entirely unless `--engine sfdmu` is explicitly passed; the
  default `python` engine (`bulk_op()`) is unaffected either way.

## 3. Credential inventory

| Credential | Where it lives | How it's obtained | Notes |
|---|---|---|---|
| Salesforce session (default `cli` auth mode) | In-process memory only, for the process lifetime | `sf org auth show-access-token` (delegates to the Salesforce CLI's own token storage) | Never written to `.env`, never logged. The May 2026 CLI security update redacts it from `sf org display`, which is why `sf_client.py` calls the dedicated token command instead. **That same update also moved the underlying token storage itself into the host OS's native keychain** (Windows Credential Manager / macOS Keychain / `libsecret`) rather than a plaintext file — fine for a host-installed venv, but it means this credential is **not reachable from inside the optional Docker container** (§2) no matter how `~/.sf` is mounted; `jwt`/`password` mode only there. See `docs/DOCKER.md`'s auth-mode section for the full finding. |
| Salesforce JWT cert / connected-app key | `server.key` on disk (path set in `.env`) | Provisioned once by whoever sets up the connected app (an **External Client App** as of Spring '26 — legacy Connected App creation is disabled; see `ROADMAP.md` #18) | `.gitignore`'d (`server.crt`, the public half, is also gitignored — org/app-specific generated material, not template content); never read or printed by this framework outside the auth call itself. |
| Data Cloud tenant token (`data-cloud-query`, `list-calculated-insights`, `query-calculated-insight`, `data-cloud-profile`, `list-data-graphs` — `data-cloud-status`'s six checks don't need it, plain core-org SOQL) | In-process memory only, for the duration of a single CLI invocation | A second OAuth hop off an already-valid core-org session (`POST {instance}/services/a360/token`, `grant_type=urn:salesforce:grant-type:external:cdp`) — see `ROADMAP.md` #18 | `data_cloud.py`; a genuinely separate host (`*.c360a.salesforce.com`) and access token from the core org's, so treat it as its own credential, not an extension of the core session. |
| Salesforce username/password/security token (`password` mode) | `.env` | Manually configured | Documented as the "dev fallback only" mode in `README.md` -- weakest of the three, avoid in any shared/production environment. |
| SQL Server credentials (`SQL_BACKEND=mssql`, the default) | `.env` (`SQL_UID`/`SQL_PWD`), or none at all if `SQL_TRUSTED_CONNECTION=yes` (Windows auth, the default) | Manually configured | Windows/trusted auth is the default and avoids a stored SQL password entirely. |
| PostgreSQL credentials (`SQL_BACKEND=postgresql`, roadmap #69) | `.env` (`SQL_UID`/`SQL_PWD`, reused from the SQL Server fields above — already backend-generic names), plus `SQL_PORT`/`SQL_POSTGRES_SSLMODE` (connection parameters, not credentials) | Manually configured | Built via `sqlalchemy.engine.URL.create()` (`sql_client.py`'s `_make_postgres_engine()`), not a hand-rolled connection string — the password is a distinct URL field SQLAlchemy already redacts in any `repr()`/`str()` of the engine or its `.url`, confirmed live; a stronger default than the SQL Server path's `odbc_connect` blob, which that function's own comment already flags as unmaskable. No Windows/trusted-auth equivalent — a password is always required unless the Postgres server itself is configured for passwordless local trust auth (a server-side setting, not something this framework controls). |
| Mockaroo API key | `.env` | Manually configured | Only ever sent to Mockaroo's API; scoped to mock-data generation. |

**Two-org config (roadmap #75) — any credential row above can now exist
twice in one `.env`.** Every `SF_*` setting (including the credential
rows above — `SF_PASSWORD`, `SF_SECURITY_TOKEN`, `SF_CONSUMER_KEY`,
`SF_PRIVATE_KEY_FILE`, the JWT cert path) can be role-suffixed
(`SF_PASSWORD_SOURCE`/`SF_PASSWORD_TARGET`, etc. — see
`config.py`'s `resolve_org_settings()`), so a single `.env` can hold two
full credential sets simultaneously — one per org in a source→target
migration — instead of one. Nothing new is written to disk or logged
beyond what the table above already covers (the mechanism only *selects*
which existing `.env` values apply per invocation, via the `--org`/
`--org-alias` CLI flags); the new trust-boundary consideration is that
`resolve_org_settings()` falls back per-field to the base, unsuffixed
value when a role-specific override isn't set — a partially-configured
role override (e.g. `SF_ORG_ALIAS_TARGET` set but not
`SF_CONSUMER_KEY_TARGET`) can silently produce an internally-inconsistent
credential hybrid rather than a clear error. `cli.py`'s `_ctx()` echoes
which role/alias resolved (`[org: target -> alias ...]`) before
connecting, but not which individual fields fell back to the base
value — worth checking manually if source and target orgs use different
auth modes or connected apps.

**`SQL_BACKEND=sqlite` (roadmap #28) has no credential at all** — SQLite is
local-file access (`SQL_SQLITE_DIR`, one `<schema>.db` file per schema),
no server process, no network connection, no auth handshake of any kind.
A smaller trust surface than the SQL Server path by construction, not by
configuration choice — there's no equivalent of `SQL_UID`/`SQL_PWD` to
even get wrong. Filesystem permissions on `SQL_SQLITE_DIR` are the only
access control that applies, same as any other file this framework writes.

Explicitly **not** credentials, listed to preempt the question:
`TICKET_SYSTEM_URL`/`TICKET_SYSTEM_LABEL` in `.env` are a plain display
URL and label written into Migration Run Book headers -- no token, no
authentication, never sent anywhere. If the ticket-system *integration*
idea (`ROADMAP.md` #39) is ever built, its API token would be a genuinely
new credential type and this table must gain a row for it.

`.env`, `server.key`, and `.mcp.json` are all `.gitignore`'d (verified: never
present in this repo's git history). `CLAUDE.md` hard rule 3 additionally
instructs Claude Code itself to never read or print `.env`/`server.key`
contents, and `.claude/settings.json` denies `Read(.env)` and
`Read(**/*.key)` outright at the permission-system level -- that denial is a
real product-enforced control, not just a documented convention.

## 4. Which controls are code-enforced vs. convention-enforced

This distinction matters for a security review, so it's stated plainly
rather than left implicit:

**Enforced by the permission system (`.claude/settings.json`), not just
documentation:**
- `bulkops` (the only command that writes to Salesforce) requires explicit
  human approval every invocation -- it's in the `ask` list, not `allow`.
- `.env`/`*.key` files are denied from being read by Claude Code outright.
- Destructive shell patterns (`rm -rf`, `sudo`, `sf org delete`) are denied.

**Enforced by convention only (CLAUDE.md instructions Claude Code follows,
plus code that assumes correct `.env` configuration) -- not a technical
barrier in the Python code itself:**
- "`replicate`/`DROP`/`CREATE` only against the mirror DB" (hard rule 1):
  `sql_client.py` connects to whatever `SQL_DATABASE` is set in `.env`. There
  is no code-level check preventing it from pointing at a different
  database -- this is a configuration + operator-discipline control, not a
  software one. A security review should treat `.env`'s `SQL_DATABASE`
  value as the actual enforcement point.
- Field-level-security grants bundled with new custom fields (hard rule 8),
  duplicate/NULL migration-key checks before a load (hard rule 7), and the
  parent-sort step before a load (hard rule 6) are all process discipline
  Claude Code is instructed to follow, not something the CLI refuses to run
  without.

Bottom line: today's safety model leans on a combination of a genuinely
enforced permission layer (approval gate + credential-read denial) and an
instructed, reviewable operator discipline (CLAUDE.md) that a human is meant
to be reading and correcting Claude Code against in real time -- not a
fully code-enforced sandbox. That is an appropriate model for "one trusted
operator at a terminal" and would need to change if that assumption changes
(see §7).

## 5. Data flow and classification

- **Replicate** (`replicate.py`) pulls Salesforce org data -- potentially
  real customer/business data -- into SQL Server tables. From that point on,
  **this framework's own security posture is only as strong as the SQL
  Server instance's** -- encryption at rest, network exposure, who else has
  login access, backup handling. This framework does not configure or
  harden SQL Server itself; that's assumed to already meet the org's own
  data-handling standards before anyone points this tool at it.
- **Bulk load** (`bulkops.py`) writes real records into a live Salesforce
  org, gated behind the approval prompt in §4. Result writeback (`Id`/
  `Error`) never carries credentials, only record outcomes.
- **Mock data** (`mock_data.py`) never touches real org data -- it only
  sends field *names/types* to Mockaroo and writes synthetic rows to a
  `_Mock` suffixed table.
- **Generated artifacts** (`metadata/*.json`, `mapping/*.xlsx`, solution
  `.docx` files, exported profile workbooks) can contain real field names,
  sample values, and business context. They're gitignored by default for
  exactly this reason (see `README.md`'s "Repository structure") -- treat
  committing any of them as a deliberate per-project decision, not a
  default.
- **Migration Run Book workbooks** (`generate-migration-run-book` output)
  deserve their own line in that list: beyond business context, they embed
  the **operator's OS username** (`BulkOpsLog`'s `RunBy`, synced into
  Person Responsible by `update-migration-run-book`), the target **org
  alias**, and the Git remote/commit breadcrumbs. Same rule -- committing
  one is a deliberate decision, and one to sanitize first if the repo is
  public.
- **`OrchestratorRunEvent`** (`orchestrator-assess`, roadmap #53, Phase 1
  only -- opt-in per schema, same convention as `BulkOpsLog`) is a
  read-only observation log: it never writes to Salesforce and never
  changes how `bulkops` itself is gated. Its `Reasons` column can embed a
  **real Salesforce record Id** when the underlying failure was a
  `DUPLICATE_VALUE` error (Salesforce's own error text names the specific
  colliding record) -- worth knowing before treating this table's contents
  as low-sensitivity by default, same reasoning as `BulkOpsLog`'s own
  `RunBy`/error text already gets in this section.
- **`generate-discovery-checklist` output** (roadmap #60) echoes a live
  org's active validation rules' `ErrorMessage` text verbatim into the
  generated Markdown checklist. Same class of caveat as the two entries
  above: a client org's own validation-rule error text is outside this
  framework's control, so treat a generated discovery checklist the same
  as any other generated artifact above -- not something to commit
  without reviewing first.

## 6. AI-operator considerations (specific to this being Claude-Code-driven)

Using Claude Code as the operating layer means conversation content --
including tool output shown in the terminal, such as query results,
`describe()` schema dumps, and profiling samples -- is sent to Anthropic's
API as part of normal operation, the same as any other Claude Code session.
This is inherent to the tool, not something specific to this framework, and
is not a flaw to fix here -- but a security team evaluating this repo
should independently review Anthropic's current data usage, retention, and
enterprise/API data-handling terms (they differ by plan and change over
time; this document doesn't attempt to restate them) rather than assume
defaults. Practical mitigations available today without any code change:
run profiling/query commands against aggregates and row counts rather than
raw PII where the task allows it, and prefer a Claude Code plan/deployment
mode whose data-handling terms the org has already reviewed.

## 7. What this is *not*, today

- **No multi-user access control.** The tool grants no access beyond what
  the operator already has via their own Salesforce login and SQL Server
  credentials -- it's a convenience/automation layer on top of existing
  access, not a new access grant.
- **No network listener.** Nothing in this repo binds a port or accepts
  inbound connections. There is currently no web UI (see §8 for where that's
  headed on the roadmap, and why it changes this section entirely).
- **No secrets manager / vault integration.** Credentials rely on `.env`
  file permissions at the OS level and the `sf` CLI's own token storage.
- **No independent audit log** beyond git history of the transformation SQL
  under version control, and Claude Code's own conversation transcript.

## 8. Forward-looking: what changes if the roadmap's UI/SSO item is built

`ROADMAP.md` #25 (a web UI) and #26 (SSO / multi-user access) are explicitly
**not built** as of this document. If/when they are, §4 and §7 above stop
being true in an important way: a listening web process introduces session
management, an actual authentication boundary (today there isn't one -- the
CLI *is* the boundary, enforced by whoever has OS access to run it), and a
realistic need for CSRF/XSS/dependency-vulnerability review that a pure CLI
doesn't have. Treat that build as requiring a fresh pass over this entire
document, not an incremental patch to it -- the trust model changes, not
just the feature surface.

## 9. Supply chain

All dependencies (`requirements.txt`) are established, widely-used open
source packages (`simple-salesforce`, `SQLAlchemy`, `pyodbc`,
`psycopg2-binary` (roadmap #69, PostgreSQL support -- a mature, widely-used
driver with no known CVEs at time of writing; the `-binary` wheel statically
bundles its own libpq/OpenSSL rather than linking the system's, a documented,
non-blocking tradeoff of that package variant, not a vulnerability), `pandas`,
`click`, `openpyxl`, `requests`, `rich`, `docxtpl`, `python-docx`,
`python-dotenv`, `pyarrow`, `snowfakery`, `PyYAML`),
version-pinned with a minimum floor, no vendored/copied third-party source
beyond what's explicitly disclosed: `sql/functions/`'s provenance notes
document that two functions were deliberately rewritten from scratch rather
than ported, because their original source carried third-party copyright
notices (see `sql/functions/README.md`). Two runtime supply-chain
exceptions exist, both optional and off by default: the DBHub MCP server
(§2), fetched via `npx` rather than pinned in this repo; and SFDMU (§2,
`bulkops --engine sfdmu`, `ROADMAP.md` #71), installed once via
`sf plugins install sfdmu` -- a digitally signed `sf` CLI plugin (verified
at install time by the `sf` CLI itself, unlike DBHub's unsigned `npx`
fetch), but still a third-party dependency not pinned in this repo's own
`requirements.txt`, and -- unlike DBHub, which is read-only -- one that
sits in the live Salesforce write path when explicitly enabled. Flag both
explicitly if evaluating this framework for adoption.

**The optional Docker variant** (`Dockerfile`, roadmap #68) has its own
supply-chain surface, separate from the packages above: the base image
(`python:3.12-slim-bookworm`), Microsoft's own ODBC Driver 18/
`mssql-tools18` apt repo (added via a `curl`-fetched GPG key + Microsoft's
own `prod.list`, not pinned to a specific package version), NodeSource's
Node 22 setup script (`curl -fsSL https://deb.nodesource.com/setup_22.x |
bash -`, a `curl | bash` pattern, not vendored/checksum-verified), and
`npm install --global @salesforce/cli` (no version pin — always installs
whatever is current at build time). Flag this the same way as the DBHub
`npx` case above if this container is evaluated for adoption; none of it
is in the critical Salesforce/SQL Server data path itself, but it is
still code executing during the image build.

`.github/workflows/tests.yml` (roadmap #42) runs the pure-logic test suite
on every push/PR: `permissions: contents: read` (least privilege, no
write/deploy access), and its two GitHub Actions (`actions/checkout`,
`actions/setup-python`) are pinned to major-version tags rather than a
commit SHA -- a smaller, well-known trust surface than the DBHub `npx`
case above, but the same class of consideration if this is evaluated for
adoption.

## 10. Checklist for a security reviewer

- [ ] Confirm `.env` file permissions on whatever machine runs this (OS-level
      file ACLs; this framework doesn't manage that).
- [ ] Confirm the SQL Server login used has least-privilege appropriate to
      the environment -- and confirm `SQL_DATABASE` in `.env` actually points
      at the intended mirror DB (§4: this is a configuration control, not a
      code-enforced one).
- [ ] Confirm the Salesforce user/connected app used for whichever
      `SF_AUTH_MODE` is chosen has only the access it actually needs for the
      migration at hand.
- [ ] Review `CLAUDE.md`'s "Hard rules" section as the current list of
      operator-discipline guardrails this framework is built around.
- [ ] If DBHub MCP is adopted, confirm it's configured read-only and that
      the `npx`-fetched package is acceptable under the org's supply-chain
      policy, or pin/vendor it first.
- [ ] If `bulkops --engine sfdmu` is adopted, confirm `sf plugins install
      sfdmu`'s digitally-signed third-party plugin is acceptable under the
      org's supply-chain policy -- unlike DBHub, this one writes to the
      live Salesforce org when used.
- [ ] Independently review Anthropic's current data handling/retention
      terms for whichever Claude Code plan is in use (§6) -- don't assume.
- [ ] Re-review this entire document before any UI/SSO work (§8) ships.

---

*Last reviewed against the codebase during the 2026-07-18 code-review
pass covering the two-org config mechanism (roadmap #75): added §3's new
"any credential row can now exist twice" entry -- found missing by a
multi-angle review of everything merged since the prior pass below (the
mechanism itself had already shipped a few days earlier without a
matching update here). Previously reviewed during the 2026-07-14 SFDMU
integration (roadmap #71, found missing by a ruthless review pass): added
SFDMU's own subprocess/supply-chain surface to §2/§9/§10 -- none of this
existed until that integration landed. Previously reviewed during the
2026-07-13 PostgreSQL backend pass (roadmap #69): added the PostgreSQL
credential row to §3 and its own supply-chain entry (`psycopg2-binary`) to
§9 -- none of this existed as of the Docker-environment pass immediately
below. Previously reviewed during the 2026-07-13 Docker-environment
pass (roadmap #68): added the optional containerized variant to §2, the
cli-mode-in-container credential-reachability finding to §3 (Salesforce's
May 2026 CLI update moved org auth into the host OS keychain, unreachable
from a Linux container — confirmed live), and the Docker image's own
supply-chain surface to §9 — none of this existed in the codebase as of
the prior 2026-07-12 pass below. Previously reviewed during the
2026-07-12 ruthless-review
pass (covering the 8 new roadmap #52/#59-66 features -- `generate-run-book-
flowchart`, `triage-failures`, `generate-adversarial-mock-data`,
`generate-pass-summary`, `reset-dev-cycle`, `reconcile-load-counts`,
`assess-migration-readiness`, `bootstrap-project`,
`generate-discovery-checklist` -- confirmed no SQL injection/unsafe-
deserialization/command-injection/credential-exposure issues, and that none
of the new live-Salesforce-write-capable commands bypass the Live-Org
Write Confirmation Rule via `.claude/settings.json`'s allow-list) --
previously reviewed during the 2026-07-11 ruthless-review pass (covering
Orchestrator Phase 1's `OrchestratorRunEvent` table, the `sql_dialect.py`
identifier-escaping fix, and the `source_ingestion.py` BULK INSERT
string-literal-escaping fix), the 2026-07-09 ruthless-review pass
(covering `validate-external-id`/pytest+CI additions, the `sf_client.py`
shell-argument hardening, and the ODBC password-masking caveat in
`sql_client.py`), and, before that, the 2026-07-09 full repo review
(Migration Run Book, `record-counts`, `SECURITY.md`/`CONTRIBUTING.md`
additions). Update alongside any change that adds a credential type, a
network listener, or an authentication boundary.*
