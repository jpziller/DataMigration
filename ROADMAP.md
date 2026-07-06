# Roadmap / idea backlog

Notes on future tooling for this framework — captured as ideas to review and
scope later, not committed designs. Nothing here is built yet unless marked.

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
- **Rebuild instead of port**: a legacy tool-coupled column/permission
  pre-flight check (`SF_ColCompare`) — the concept (validate a load table's columns
  against the target object's createable/updatable fields before
  submitting) is good, but should be a Python pre-flight step in
  `bulkops.py` using `metadata.list_fields()`, which already has this data.

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

## 4. Solution document generator (not built, depends on #2 and #3)

Idea: auto-draft a migration solution/design document from the mapping
spreadsheet + load-order analysis + object metadata, instead of writing it
by hand each time.

## 5. Org metadata risk analyzer (not built)

Problem: before migrating data into fields, you need to know if Flows,
validation rules, or other automation on the target org will fire
unexpectedly during a load (causing errors, cascading updates, or unwanted
side effects).

Idea: a tool that cross-references the fields/objects a migration touches
against the org's automation metadata (Flows, validation rules, maybe Apex
triggers) and produces a report of "here's what might interfere with this
load and why" before you run bulkops for real.

Candidate library: `pandera` or `great_expectations` for declarative data
quality rules ("this field must be non-null," "this must match regex X")
as a complement to `profiling.py`'s stats — rules-as-code instead of
eyeballing profile output, and something a non-technical reviewer could
still read.

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
4. **Generate scripts**: build the T-SQL transform for each source →
   target object pairing (following the standard workflow already in
   `CLAUDE.md`: mapping → confirm field names → build → sort → dupe-check).
5. **AI review of transformed data**: review subsets of transformed
   records and check them against the org's build/automation metadata —
   a **Risk Analyzer** distinct from #5 (which looks at org metadata
   ahead of time; this looks at actual transformed *data* against that
   metadata to catch problems #5 wouldn't surface from schema alone).
6. **Human in the loop**: a person reviews everything generated so far and
   polishes each object for real migration — AI proposes and drafts
   proactively, but doesn't load anything without that review.

This ties together #2 (load order), #3 (mapping doc), #4 (solution doc),
#5 (org metadata risk), #7 (profiling), and #11 (auto-mapping) into one
pipeline, plus one remaining new piece: RAIDD log generation. Scoping that
into a concrete build is the next step — this section is the shape of
where it's all going, not a spec for it yet.
