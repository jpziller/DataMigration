# Roadmap / idea backlog

Notes on future tooling for this framework — captured as ideas to review and
scope later, not committed designs. Nothing here is built yet unless marked.

## Capabilities at a glance

Read this table first — it's the answer to "what can this framework do
today," so a fresh full read of every section below shouldn't be necessary
just to find out what's built. Update this table in the same commit as any
future item that flips status, so it never drifts from the sections it
summarizes.

| # | Item | Status | Command / skill |
|---|---|---|---|
| 1 | Reusable SQL function library | Built (library, no CLI wrapper) | `sql/functions/` |
| 2 | Load-order dependency analyzer | **Built** | `analyze-load-order` |
| 3 | Field-mapping spreadsheet tool | **Built** | `generate-mapping-doc`, `check-mapping-balance` |
| 4 | Solution document generator | **Built** | `generate-solution-doc` |
| 5 | Org metadata risk analyzer | **Built** | `analyze-org-risk` |
| 6 | Mock/demo data generation | **Built** | `generate-mock-data` |
| 7 | Data profiling toolset | **Built** | `profile-salesforce`, `profile-sql-table`, `export-profile-excel` |
| 8 | Ad hoc query tool | **Built** | `query` |
| 9 | Fuzzy matching / dedup | Deprioritized, not built | — |
| 10 | Console output polish | **Built** | (applies to `query`/`profile-*`) |
| 11 | Auto-mapping | **Built** | `auto-map` |
| 12 | Web UI for less-technical users | Not built (future) | — |
| 13 | SSO / multi-user access control | Not built, depends on #12 | — |
| 14 | Bulk load pre-flight check + retry + delete-by-external-id | **Built** | `bulkops` (built in), `bulkops-retry` |
| 15 | Data Cloud (D360) query support | Not built — API surface researched, live verification blocked (no Data Cloud org available) | — |
| 16 | Data Cloud semantic model reference | Not built, depends on #15 | — |
| 17 | DSO refresh/error monitoring | Not built — needs API research | — |
| 18 | DSO→DLO mapping read + auto-map | Not built — needs API research | — |
| 19 | Data Kit / Bundle documentation | Not built, depends on #15/#16 | — |
| 20 | SQL-Server-backed local DSO ingestion | Not built — needs API research | — |
| 21 | Calculated Insight scripting + testing + CI/CD | Not built, depends on #15 | — |
| 22 | Parquet file import | **Built** | `import-parquet` |

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
  `bulkops.py`'s `bulk_op()` — see #14 for the full writeup.

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
#11 below.

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

Snowfakery integration (for relationship-aware multi-object fake data, e.g.
matching Accounts/Contacts/Opportunities together rather than independently
random rows per object) is still just an idea, not started. `Faker` is a
lower-priority alternative worth knowing about too — no API key, no rate
limit, works fully offline — for whenever Mockaroo's 200-requests/day free
tier becomes the actual bottleneck rather than a theoretical one.

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

## 9. Fuzzy matching / dedup (deprioritized, not built)

Explicitly lower priority than everything else here — there's real value
in "free, runs as a SQL Server + Python job" versus paying for a
commercial dedup tool, but matching rules, merge survivorship, and a
review UI are a deep enough rabbit hole that it competes for time against
things with clearer immediate payoff. `sql/functions/matching/` already
has Jaro-Winkler/Soundex/N-gram T-SQL functions from the SQL function
library port. If this ever gets picked up in earnest, `recordlinkage` or
`dedupe` (Python) are worth evaluating against hand-rolled T-SQL matching
before building more of the latter — `rapidfuzz` specifically for a fast
Levenshtein-family option if T-SQL's `JaroWinklerDistance` turns out too
slow at scale.

## 10. Console output polish — BUILT (`rich` in `cli.py`)

`query` and `profile-salesforce`/`profile-sql-table` render results as
`rich` tables instead of raw pandas `to_string()` output (which silently
truncated wide values) or, for profile, no data at all (previously just a
summary count). Long values wrap onto multiple lines rather than getting
cut off. The profile preview is deliberately narrow — field/type/populated
%/distinct count, the four columns that matter for an at-a-glance "is this
worth migrating" call — full detail stays in `dbo.FieldProfile`/
`FieldProfileValues` and `export-profile-excel`, not crammed into a
console table.

## 11. Auto-mapping — BUILT (`auto_mapper.py`)

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

## 12. Web UI for less-technical users (not built)

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
here too once this is picked up (tracked as #13, not folded into this item,
since SSO is its own scoping exercise even once a UI exists to put it in
front of).

## 13. SSO / multi-user access control (not built, depends on #12)

Problem: once #12 exists, "who can open this web console, and as whom"
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

## 14. Bulk load pre-flight check + retry helper — BUILT (`bulkops.py`)

Two additions to `bulk_op()`/`bulkops`, picked over the bigger, riskier #12/
#13 UI work as the next concrete step -- both slot directly into the load
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

## 15. Data Cloud (D360) query support (not built — API surface researched, live verification blocked)

`query_tool.py` is explicitly scoped to CRM objects via the standard REST
Query API today (see its own docstring) — Data Cloud objects (DLOs, DMOs,
Calculated Insights, Unified Profile) use query surfaces this framework
doesn't touch at all yet. Current Salesforce docs (as of this research
pass) call the product **Data 360** now, not Data Cloud — same platform,
newer name; both terms are used interchangeably in this section since
that's what the docs themselves currently do.

**Hard blocker found before any code could be written**: the org this
framework is connected to has **zero Data Cloud objects provisioned** --
`sf.describe()` returns no `__dlo`/`__dlm` objects at all. Every finding
below is verified against current `developer.salesforce.com` docs, not
against a live call — nothing here has actually been executed. Building
or testing real integration code needs a Data Cloud-licensed org to point
at; this item is blocked on that, not on further reading.

**Research finding: this splits into (at least) two genuinely different
API surfaces, not one** — the same lesson `risk_analyzer.py`'s build
already taught (guessing which endpoint a metadata type needs fails
silently or errors outright, never partially works):

1. **Basic DLO/DMO querying is plain SOQL, no separate auth.** DLOs
   (`__dlo` suffix) and DMOs (`__dlm` suffix; fields use the ordinary
   `__c` suffix) are queryable through the *same* core-org REST endpoint
   and access token `query_tool.py` already uses (`sf.query()`) — confirmed
   via Salesforce's own REST API Developer Guide, e.g.:
   ```sql
   SELECT PartyId__c FROM ContactPointEmail__dlm WHERE EmailAddress__c='jjones@email.com' LIMIT 100
   ```
   If this holds up against a real Data Cloud org, extending
   `query_tool.py` for basic DLO/DMO lookups could be a small addition —
   possibly just documentation plus a naming-convention note, not new
   auth plumbing. This is the cheapest, highest-confidence piece to build
   first once a test org exists.

2. **Complex cross-object queries (joins/aggregations/window functions
   spanning DLO+DMO+Calculated Insights together) need a separate Data
   Cloud tenant** — a genuinely different instance URL and access token,
   not the core org's. Token exchange: `POST
   {core-org-instance-url}/services/a360/token` with `grant_type=urn:
   salesforce:grant-type:external:cdp` and the core org's own access
   token as `subject_token` (`subject_token_type=urn:ietf:params:oauth:
   token-type:access_token`), returning `DATA_CLOUD_ACCESS_TOKEN` +
   `DATA_CLOUD_INSTANCE_URL`. Queries then go to that tenant's own
   `/api/v3/query` (or the older Connect REST API's `/services/data/
   v64.0/ssot/query-sql`) with a SQL string in the body, following an
   async job pattern: submit → poll status → fetch rows/chunks → cancel
   if needed. This is a materially bigger lift than CRM's Bulk API 2.0
   pattern this framework already handles, since it's a whole second
   authentication hop layered on top of the first.
3. **Calculated Insights** have their own dedicated endpoint (`GET
   /api/v1/insight/calculated-insights/{ci-name}`) supporting SQL-style
   dimensions/measures/filters and pagination (limit/offset/order by,
   default cap 4,999 rows/call) — not plain SOQL, not the same surface
   as #2 either.
4. **Unified Profile** has a dedicated Profile API (`GET /api/v1/profile/
   {dataModelName}`, AND+equality filters only, 50-field cap per request,
   date format `YYYY-MM-DD HH:MM:SS`) *and* is separately reachable via
   plain SOQL against Unified DMOs directly (same #1 mechanism) — two
   different paths to related data, worth confirming which one actually
   fits this framework's needs once there's an org to test against rather
   than building both speculatively.
5. **Data Graphs** have their own distinct query endpoint plus a separate
   metadata-discovery endpoint (what data graphs exist, what they expose)
   — a third, independent surface from all of the above.

Sources consulted (all current as of this research pass, not relied on
from training knowledge): [Query API Reference](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-queryservices-overview.html),
[SQL Query APIs](https://developer.salesforce.com/docs/data/data-cloud-query-guide/guide/dc-sql-query-apis.html),
[OAuth Token Exchange Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_token_exchange_overview.htm),
[Query Data Cloud via standard REST API](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_cdp_query.htm),
[Calculated Insights API](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-ci-call-overview.html),
[Profile API](https://developer.salesforce.com/docs/atlas.en-us.c360a_api.meta/c360a_api/c360a_api_profile_call_overview.htm),
[Data Cloud object suffixes](https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_concepts_data_cloud_objects.htm),
[Data Graphs API](https://developer.salesforce.com/docs/data/data-cloud-query-guide/references/data-cloud-query-api-reference/c360a-api-data-graphs-overview.html).

**Next step, once a Data Cloud-provisioned org is available**: verify
finding #1 live first (lowest cost, highest confidence) before touching
the token-exchange path at all — same incremental, verify-before-build
approach every other tool in this framework has followed.

## 16. Data Cloud semantic model reference (not built)

Idea: understand and expose the semantic model (the layer that gives DMOs
and their relationships business meaning beyond raw schema) as a reference
data architects can query against — both the data and the metadata *about*
it — the same spirit as `metadata.py`/`dump_describe()` does for CRM
objects today, but for Data Cloud's own metadata layer. Needs real API
research first (see #15's caution); likely depends on #15 existing first
since both need the same Data Cloud API access.

## 17. DSO refresh/error monitoring (not built)

Problem: before trusting data pulled from a DSO (Data Source Object — the
raw ingested layer, see #18), a data architect needs to know when it last
refreshed and whether its last ingestion run had errors — silently working
off stale or partially-failed ingested data is a real risk specific to the
Data Cloud pipeline (source → DSO → DLO → DMO), distinct from anything
`profiling.py` checks about the *content* of already-landed data.

Idea: a check (`analyze-org-risk`-style, or its own command) reporting
last-refresh timestamp and ingestion error count/detail per DSO. Needs
research into which Data Cloud metadata object actually exposes this — not
yet confirmed which one, if any, is queryable the way `FlowDefinitionView`
turned out to be for record-triggered Flows.

## 18. DSO→DLO mapping: read, then auto-map (not built)

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

## 19. Data Kit / Bundle documentation (not built)

Idea: surface what's in a Data Cloud Data Kit/Bundle that's actually
relevant to a data architect scoping a migration, and document it the same
way `generate-mapping-doc` documents CRM field mappings — one spreadsheet,
reviewable structure, not a wall of raw metadata. Depends on #15/#16
existing first (need real Data Cloud metadata access before there's
anything to document).

## 20. SQL-Server-backed local DSO ingestion (not built)

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

## 21. Calculated Insight scripting + testing + CI/CD (not built)

Idea, raised directly: script Calculated Insight definitions (DMQL) here
in the repo — versioned, reviewable, the same principle
`sql/transformations/*.sql` already applies to CRM transform logic — write
query-based tests against them, then deploy the resulting definition via a
CI/CD pipeline rather than hand-building Calculated Insights in Data Cloud
Setup each time. Depends on #15 (Data Cloud querying) existing first, to
actually run the "query tests" part; the CI/CD deployment side would need
its own research into how Calculated Insight metadata is deployed
programmatically (Metadata API component type, if one exists, vs. Setup UI
only today).

## 22. Parquet file import — BUILT (`parquet_import.py`)

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
3. **Auto-map** (BUILT, see #11): attempt source → target field mapping
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
#5 (org metadata risk), #7 (profiling), and #11 (auto-mapping) into one
pipeline, plus one remaining new piece: RAIDD log generation. Scoping that
into a concrete build is the next step — this section is the shape of
where it's all going, not a spec for it yet.
