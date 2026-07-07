# Roadmap / idea backlog

Notes on future tooling for this framework — captured as ideas to review and
scope later, not committed designs. Nothing here is built yet unless marked.

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
| 6 | Mock/demo data generation | **Built** | `generate-mock-data`, `generate-related-mock-data` | Generates realistic fake records for testing or demos, without touching any real Salesforce data. `generate-mock-data` does one object at a time; `generate-related-mock-data` generates several objects *linked together* (e.g. Accounts that really do have Contacts pointing back at them). |
| 7 | Data profiling toolset | **Built** | `profile-salesforce`, `profile-sql-table`, `export-profile-excel` | Tells you how populated and clean a field actually is — what % of rows have a value, how many distinct values, min/max — before you decide whether it's even worth migrating. Run this before mapping fields, not after. |
| 8 | Ad hoc query tool | **Built** | `query` | Run a quick SOQL query from the command line for a fast lookup, without opening a separate tool like Workbench. |
| 9 | Console output polish | **Built** | (applies to `query`/`profile-*`) | Query/profile results print as a readable table instead of a raw text dump. |
| 10 | Auto-mapping | **Built** | `auto-map` | Suggests a first-draft field mapping automatically (matching names, a synonym list, and a data-quality check) so you're reviewing/correcting a draft instead of starting the mapping spreadsheet from a blank sheet. |
| 11 | Bulk load pre-flight check + retry + delete-by-external-id | **Built** | `bulkops` (built in), `bulkops-retry` | This is the actual "push data into Salesforce" step — insert/update/upsert/delete via Bulk API 2.0. The pre-flight check catches typo'd/non-writable fields *before* burning a real API call; `bulkops-retry` lets you resubmit only the rows that failed instead of the whole load again. |
| 12 | Parquet file import | **Built** | `import-parquet` | Brings a Parquet file's data into SQL Server as typed columns — a second way to get source data in, alongside pulling directly from a Salesforce org. |
| 13 | Email Deliverability attestation gate | **Built** | `bulkops` (built in), hard rule 9 | Forces you to actually go check Setup's Email Deliverability setting before any insert/upsert that could send real email to real people, and pass what it shows as a flag. This is a required human confirmation, not an automatic check — Salesforce has no API to read that setting. |
| 14 | Load activity logging + analytics | Logging **Built** (opt-in); analytics not built | `enable-bulkops-logging`, `disable-bulkops-logging` | Optional, off-by-default record of every `bulkops` run (what, when, how many succeeded/failed) written to a SQL Server table, so you can look back at history instead of relying on console scrollback. Turn it on once per schema; it then logs automatically. |
| 15 | Dynamic batch sizing from org metadata review | Not built, builds on #5/#14 | — | Idea: automatically use a smaller batch size for heavily-automated objects (lots of triggers/Flows) instead of a human having to already know that and set it manually. |
| 16 | Run book (manual + programmatic step tracking) | Not built — blocked on user's template | — | Idea: a living record of every step (manual and scripted) taken during a real migration cutover — who did what, when, what errors came up. Waiting on a real example template before this gets designed. |
| 17 | Fuzzy matching / dedup | Deprioritized, not built | — | Idea: flag "these two records are probably the same person/company" for dedup — deliberately lower priority than everything else here for now. |
| 18 | Data Cloud (D360) query support | **Built** — all 5 findings researched, 4.5 confirmed live (Data Graph query-by-id/lookup-key is written but unverified — no test Data Graph exists yet) | `data-cloud-query`, `list-calculated-insights`, `query-calculated-insight`, `data-cloud-status`, `data-cloud-profile`, `list-data-graphs` | Query Data Cloud objects (DLOs/DMOs), Calculated Insights, Unified Profile data, Data Graph metadata, and check processing status for Data Streams/DSOs/Identity Resolution/Data Transforms/Calculated Insights/Data Graphs — all confirmed live against a real org (`D360_PLAYGROUND`), all real CLI commands now, not ad hoc scripts. |
| 19 | Data Cloud semantic model reference | Not built, depends on #18 | — | Idea: a reference for what a DMO's fields/relationships actually *mean* in business terms, the same way `dump-describe` documents a CRM object's schema today. Needs #18 first. |
| 20 | DSO refresh/error monitoring | **Built** — both the Data Stream (ingestion connector) and the DSO itself, confirmed as genuinely separate objects | `data-cloud-status data-stream`, `data-cloud-status dso` | Check whether a Data Cloud Data Stream or the DSO it feeds last refreshed successfully and whether either hit errors, before trusting the data behind it — confirmed live via plain SOQL, no Data Cloud tenant token needed. |
| 21 | DSO→DLO mapping read + auto-map | Not built — needs API research | — | Idea: read (and maybe suggest) how a DSO's fields map into a DLO — the Data Cloud version of what `auto-map` (#10) already does for CRM field mapping. |
| 22 | SQL-Server-backed local DSO ingestion | Not built — needs API research | — | Idea: push SQL Server data into a Data Cloud DSO for local testing, the same way `bulkops` pushes into Salesforce CRM objects today. |
| 23 | Data Kit / Bundle documentation | Not built, depends on #18/#19 | — | Idea: document what's actually in a Data Cloud Data Kit for a data architect scoping a migration — the Data Cloud version of the mapping spreadsheet (#3). |
| 24 | Calculated Insight scripting + testing + CI/CD | Not built, depends on #18 | — | Idea: version Data Cloud Calculated Insight definitions in git and test them like code, instead of only building them by hand in Data Cloud Setup. |
| 25 | Web UI for less-technical users | Not built (future) | — | Idea: a browser-based front end so someone who isn't comfortable with a terminal or Claude Code could still use this framework's tools. |
| 26 | SSO / multi-user access control | Not built, depends on #25 | — | Idea: once a Web UI exists, this is "who's allowed to log in, and as whom." Not a concern today since it's just a CLI one person runs. |
| 27 | Open query in SSMS (stage + launch) | Not built, depends on #25 | — | Idea: write a query to a file and launch SSMS pointed at it, for someone who'd rather review/run it in SSMS's own editor than in this framework's console output. |
| 28 | Pluggable integration-hub backend (e.g. MongoDB alongside SQL Server) | Not built, deliberately deferred — prototyping is SQL-Server-only for now | — | Idea: someday support a database other than SQL Server as the "hub" this framework is built around, so it isn't permanently locked into one tool. Not needed while still prototyping on one database. |
| 29 | Shared/VM-hosted SQL Server for multi-user access | Not built, deliberately deferred — prototyping is single-user/local for now | — | Idea: for when more than one person needs to work against the *same* mirror database at the same time, instead of everyone having their own local SQL Server. |
| 30 | Additional migration source connectors (Snowflake, MongoDB, etc.) | Not built, deliberately deferred | — | Idea: pull source data from more systems (Snowflake, MongoDB), the same way this framework already pulls from a Salesforce org (`replicate`) or a flat file (`import-parquet`). |
| 31 | Target-count/scaled mock data generation | Not built, builds on #6 | — | Idea: say "keep generating mock Accounts until the org has 50,000 total" instead of a fixed count every run — useful for realistic load/performance testing. |
| 32 | Bulk test-data cleanup by filter | Not built, builds on #6/#11 | — | Idea: a quick "delete every mock record I created for this test" command driven by a filter, instead of needing to build a delete load table first. |
| 33 | Scratch org lifecycle + auto-seeded test data | Not built, deliberately deferred | — | Idea: let this framework spin up a disposable Salesforce scratch org and automatically fill it with mock data, instead of assuming an org already exists. |
| 34 | Relationship-consistent subset replication | Not built, builds on #2 | — | Idea: pull a small, realistic *slice* of an org — e.g. 50 pilot Accounts and everything genuinely related to them — instead of either replicating everything or hand-coordinating a `--where` filter across every object yourself. |
| 35 | Relative date shifting utility | Not built | — | Idea: a helper that shifts old dates forward so migrated data still makes sense relative to today — e.g. a contract end date that's already in the past wouldn't make sense to a Flow expecting a future date. |
| 36 | RecordType DeveloperName resolution for cross-org migration | Not built | — | Idea: correctly translate a `RecordTypeId` from the source into the *right* RecordType in the target org. RecordType Ids are org-specific and never match across orgs, so this is a common, easy-to-miss real-migration mistake if not handled. |
| 37 | CLI alternative to Data Cloud's Profile Explorer | **Built** — same command as #18's Unified Profile finding | `data-cloud-profile` | Look up Unified Profile data (a specific person's attributes) via one command instead of Data Cloud Setup's own multi-click Profile Explorer (pick a Data Space, then an entity, then an attribute, repeatedly) — no Data Space parameter needed at all, confirmed live. |
| 38 | Real-data anonymization for demos/scratch orgs | Not built | — | Idea: take a real client org's actual data and scramble the sensitive fields (names, emails, phones) into realistic-looking fakes — same relationships/volume, no real PII — for client demos or scratch-org seeding. Different from #6, which generates synthetic data from scratch rather than replacing real values. |

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
NAME=N [--count NAME=N ...]`:
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

**Built, opt-in only, modeled directly on DBAmp's own logging behavior**:
never on by default, and never a per-call flag either — an architect
turns it on once per schema (`enable-bulkops-logging --schema <schema>`),
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

## 15. Dynamic batch sizing from org metadata review (not built, likely builds on #5/#14)

Problem raised directly: heavily-automated objects (per
`docs/MIGRATION_PLAYBOOK.md`'s row-lock/batching guidance — CPQ/Billing-
style objects often need batch sizes as small as 50 to let triggers/Flows
keep up) currently need a human to know that ahead of time and pass the
right batch size manually. Idea: use what `analyze-org-risk` (#5) already
knows about an object's automation (validation rule count, Apex triggers,
active record-triggered Flows) to automatically dial down `bulkops`'
batch size for objects likely to hit lock contention or Bulk API limits,
instead of always using the same default.

Not yet scoped: `bulk_op()` doesn't currently expose a batch-size
parameter to the Bulk API call at all (`simple_salesforce`'s `bulk2`
handler picks its own default chunking) — first needs confirming whether
`simple_salesforce` exposes batch size control at all, and if not, what
the actual Bulk API 2.0 parameter for it is, before any "dial it down
automatically" logic can be built on top. Depends on #5 already existing
for the automation signal (built) and #14 for the timing data that would
let this be tuned from real observed performance rather than a guess.

## 16. Run book (manual + programmatic step tracking) — blocked on a template

Problem raised directly: today, nothing tracks the *human* side of a
migration — every manual and programmatic step taken during a full load
(sandbox, UAT, prod), who did it, start/end/elapsed time, errors hit,
retries done — the actual "recipe" of a migration, not just what a script
did. This is explicitly framed as high-stakes ("this is what can make or
break a migration") and as something to track per main full load, not per
script.

**Blocked on the user sharing a real run-book template** — same pattern
already established for `mapping_doc.py`/`docs/MIGRATION_PLAYBOOK.md`:
drop a real example into `_stage/`, reviewed for structure/format only
(column names, section layout), never content, before designing anything.
Don't scope this further until that template exists to react to.

Once scoped, the ambition stated directly is worth preserving here rather
than softening: not just a template to fill in by hand, but a spreadsheet
this framework keeps automatically up to date and in line with the actual
load order and steps taken — closer to a generated artifact fed by #14's
log data (and this framework's own load-order analysis, #2) than a
document a human maintains manually. "Practices on scripts" (i.e. dev/test
runs) are explicitly **not** in scope for tracking — only real full loads
against sandbox/UAT/prod count.

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

## 19. Data Cloud semantic model reference (not built, depends on #18)

Idea: understand and expose the semantic model (the layer that gives DMOs
and their relationships business meaning beyond raw schema) as a reference
data architects can query against — both the data and the metadata *about*
it — the same spirit as `metadata.py`/`dump_describe()` does for CRM
objects today, but for Data Cloud's own metadata layer. Needs real API
research first (see #18's caution); likely depends on #18 existing first
since both need the same Data Cloud API access.

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

## 22. SQL-Server-backed local DSO ingestion (not built)

Idea, raised directly: build something equivalent to Data Cloud's local
CSV upload path for a DSO, but sourced from SQL Server instead of a local
file — the same "SQL Server as the integration hub" principle this whole
framework is built around, applied to Data Cloud ingestion instead of CRM
`bulkops`. Real payoff called out directly: this would make `mock_data.py`
(already built, Mockaroo-backed) useful for **Data Cloud** testing too, not
just CRM object testing — generate mock rows into a SQL Server table, then
push them into a DSO locally for testing without touching a real source
system. Needs research into Data Cloud's actual ingestion API for local/
manual uploads (as opposed to a configured Data Stream from a real
connector) before scoping further.

Both mock-data backends (#6) are natural sources for this once the
ingestion API question is answered — `generate-mock-data` for a single
DSO-shaped table, `generate-related-mock-data` (Snowfakery, also #6) for
relationship-aware multi-object DSO test data — neither is CumulusCI-
dependent (CumulusCI itself has no Data Cloud/DSO capability at all,
confirmed directly reviewing its data docs), so nothing here changes; the
blocker is still purely the ingestion API research, not the mock-data
side.

## 23. Data Kit / Bundle documentation (not built, depends on #18/#19)

Idea: surface what's in a Data Cloud Data Kit/Bundle that's actually
relevant to a data architect scoping a migration, and document it the same
way `generate-mapping-doc` documents CRM field mappings — one spreadsheet,
reviewable structure, not a wall of raw metadata. Depends on #18/#19
existing first (need real Data Cloud metadata access before there's
anything to document).

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

## 28. Pluggable integration-hub backend, e.g. MongoDB alongside SQL Server (not built, deliberately deferred)

Raised directly: don't want this framework permanently locked into one
tool as the integration hub, even though SQL Server is the right call
while prototyping. MongoDB is the concrete alternative named as worth
keeping open.

**Why this is a bigger ask than a driver swap.** This framework's entire
identity is "SQL Server is the integration hub, transformation logic lives
in versioned T-SQL" (`README.md`'s opening line, `CLAUDE.md` throughout).
A document store like MongoDB isn't a drop-in alternative behind the same
interface — there's no relational `JOIN`, no `sql/transformations/*.sql`
equivalent (aggregation pipelines or Python-side transforms would have to
fill that role), and every tool that currently emits T-SQL DDL/DML
directly (`replicate.py`'s `to_sql`, every `_ensure_table`-style function
in `risk_analyzer.py`/`bulkops.py`/`load_order.py`, `sql/functions/`'s
whole reusable-function library) would need either a parallel MongoDB-
native implementation or a genuine abstraction layer sitting in front of
both. Scoping this honestly as "a second hub mode," not a small connector
addition, is the point of flagging it here rather than understating it.

**Security considerations, raised directly and worth tracking from the
start of scoping, not bolted on after**: a different auth model entirely
(SCRAM/x.509 vs. today's Windows/SQL-auth-only `sql_client.py`), different
default network exposure (MongoDB has a well-known history of
internet-exposed, unauthenticated instances from insecure defaults —
`docs/SECURITY_OVERVIEW.md` would need its own section on this backend
the moment it's real, not just an update to the credential inventory
table it already has for SQL Server).

**Deliberately not scoped further yet** — prototyping today is
single-backend (SQL Server) on purpose; this is a "keep the door open,
don't design yourself into a corner" marker, not a committed design.
Revisit once there's a real reason (a client already on MongoDB, a
concrete multi-backend requirement) rather than speculatively building
an abstraction layer with only one real implementation behind it.

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

## 32. Bulk test-data cleanup by filter (not built, builds on #6/#11)

Problem: repeated migration-testing cycles (generate mock data → `bulkops`
insert → validate → reset → repeat) currently need a load table with a
key column to drive `bulkops <Object> delete`; there's no quick way to
purge previously-inserted test/mock records by a WHERE-clause-style
filter (e.g. "delete every Account where `MigrationID__c` LIKE
'MOCKACCT-%'") without first building a delete load table from a query.

Surfaced reviewing CumulusCI's `delete_data` task, which does exactly
this: object + WHERE-clause bulk delete, with row-error tolerance and an
optional hard-delete permission set for a full purge bypassing the
Recycle Bin.

Idea: a `bulkops <Object> delete --where "<SOQL WHERE clause>"` mode —
resolve matching Ids via a SOQL query first (the same pattern this
framework's own `_resolve_external_ids_to_sf_id` already established for
delete-by-external-id in #11), then run the existing delete path against
the resolved Ids. Mainly a test/demo-data hygiene convenience, not a
real-migration-load feature — most useful paired with #6's mock data
commands for cleaning up between test runs.

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

## 36. RecordType DeveloperName resolution for cross-org migration (not built)

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
mapping. A well-established migration pattern in general, just not yet
built here.

Idea, likely the single most broadly applicable thing surfaced by this
review, real-migration-relevant rather than a testing convenience: a
helper (a `resolve-record-types`-style CLI verb, or a pre-flight-check-
adjacent step) that queries the target org's real `RecordType` object
(`SELECT Id, DeveloperName, SobjectType FROM RecordType`) and lets a
transform/mapping doc reference a RecordType by its `DeveloperName` (a
real, portable identifier) instead of a raw Id — resolved to the correct
target Id at load time, the same "resolve to a real Id via a query
first" pattern `_resolve_external_ids_to_sf_id` already established for
delete-by-external-id (#11).

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

---

## End-to-end project workflow (vision, not built)

The long-term shape this framework is heading toward — a full project
lifecycle, not just a set of standalone tools. Roughly, in order:

1. **Kick off a project**: generate the mapping document (see #3), with
   places in it for profiling results (#7) to land.
2. **Decide scope**: flag which source objects (SQL or Salesforce) are
   actually being migrated — a documented decision, not an implicit one.
   Generate RAIDD (Risks/Assumptions/Issues/Decisions/Dependencies) entries
   for anything that needs one, for a RAIDD log.
3. **Auto-map** (BUILT, see #10): attempt source → target field mapping
   based on the mapping document, profiling data, and the git-tracked
   synonym thesaurus, as a first draft, not a final answer.
4. **Draft the solution document** (BUILT, see #4): once mapping and
   profiling exist for the objects in scope, auto-draft the migration
   solution/design document from them — a living draft that gets
   regenerated as the mapping/profiling underneath it evolves, not a
   one-time snapshot.
5. **Generate scripts**: build the T-SQL transform for each source →
   target object pairing (following the standard workflow already in
   `CLAUDE.md`: mapping → confirm field names → build → sort → dupe-check).
6. **AI review of transformed data**: review subsets of transformed
   records and check them against the org's build/automation metadata —
   a **Risk Analyzer** distinct from #5 (which looks at org metadata
   ahead of time; this looks at actual transformed *data* against that
   metadata to catch problems #5 wouldn't surface from schema alone).
7. **Human in the loop**: a person reviews everything generated so far and
   polishes each object for real migration — AI proposes and drafts
   proactively, but doesn't load anything without that review.

This ties together #2 (load order), #3 (mapping doc), #4 (solution doc),
#5 (org metadata risk), #7 (profiling), and #10 (auto-mapping) into one
pipeline, plus one remaining new piece: RAIDD log generation. Scoping that
into a concrete build is the next step — this section is the shape of
where it's all going, not a spec for it yet.
