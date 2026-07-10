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

## 3. Credential inventory

| Credential | Where it lives | How it's obtained | Notes |
|---|---|---|---|
| Salesforce session (default `cli` auth mode) | In-process memory only, for the process lifetime | `sf org auth show-access-token` (delegates to the Salesforce CLI's own token storage) | Never written to `.env`, never logged. The May 2026 CLI security update redacts it from `sf org display`, which is why `sf_client.py` calls the dedicated token command instead. |
| Salesforce JWT cert / connected-app key | `server.key` on disk (path set in `.env`) | Provisioned once by whoever sets up the connected app (an **External Client App** as of Spring '26 — legacy Connected App creation is disabled; see `ROADMAP.md` #18) | `.gitignore`'d (`server.crt`, the public half, is also gitignored — org/app-specific generated material, not template content); never read or printed by this framework outside the auth call itself. |
| Data Cloud tenant token (`data-cloud-query`, `list-calculated-insights`, `query-calculated-insight`, `data-cloud-profile`, `list-data-graphs` — `data-cloud-status`'s six checks don't need it, plain core-org SOQL) | In-process memory only, for the duration of a single CLI invocation | A second OAuth hop off an already-valid core-org session (`POST {instance}/services/a360/token`, `grant_type=urn:salesforce:grant-type:external:cdp`) — see `ROADMAP.md` #18 | `data_cloud.py`; a genuinely separate host (`*.c360a.salesforce.com`) and access token from the core org's, so treat it as its own credential, not an extension of the core session. |
| Salesforce username/password/security token (`password` mode) | `.env` | Manually configured | Documented as the "dev fallback only" mode in `README.md` -- weakest of the three, avoid in any shared/production environment. |
| SQL Server credentials (`SQL_BACKEND=mssql`, the default) | `.env` (`SQL_UID`/`SQL_PWD`), or none at all if `SQL_TRUSTED_CONNECTION=yes` (Windows auth, the default) | Manually configured | Windows/trusted auth is the default and avoids a stored SQL password entirely. |
| Mockaroo API key | `.env` | Manually configured | Only ever sent to Mockaroo's API; scoped to mock-data generation. |

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
source packages (`simple-salesforce`, `SQLAlchemy`, `pyodbc`, `pandas`,
`click`, `openpyxl`, `requests`, `rich`, `docxtpl`, `python-docx`,
`python-dotenv`, `pyarrow`, `snowfakery`, `PyYAML`),
version-pinned with a minimum floor, no vendored/copied third-party source
beyond what's explicitly disclosed: `sql/functions/`'s provenance notes
document that two functions were deliberately rewritten from scratch rather
than ported, because their original source carried third-party copyright
notices (see `sql/functions/README.md`). The one runtime supply-chain
exception is the optional DBHub MCP server (§2), fetched via `npx` rather
than pinned in this repo -- flag it explicitly if evaluating this framework
for adoption.

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
- [ ] Independently review Anthropic's current data handling/retention
      terms for whichever Claude Code plan is in use (§6) -- don't assume.
- [ ] Re-review this entire document before any UI/SSO work (§8) ships.

---

*Last reviewed against the codebase during the 2026-07-09 ruthless-review
pass (covering `validate-external-id`/pytest+CI additions, the `sf_client.py`
shell-argument hardening, and the ODBC password-masking caveat in
`sql_client.py`) -- previously reviewed during the 2026-07-09 full repo
review (Migration Run Book, `record-counts`, `SECURITY.md`/`CONTRIBUTING.md`
additions). Update alongside any change that adds a credential type, a
network listener, or an authentication boundary.*
