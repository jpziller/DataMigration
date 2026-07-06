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

Not yet built: auto-mapping into this doc (source→target suggestions) —
still a separate roadmap item, see below.

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

## 6. Mock/demo data generation — Mockaroo half BUILT (`mock_data.py`), Snowfakery not started

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
random rows per object) is still just an idea, not started.

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
3. **Auto-map**: attempt source → target field mapping based on the
   mapping document (name/type similarity, describe() metadata, prior
   mappings) as a first draft, not a final answer.
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
#5 (org metadata risk), and #7 (profiling) into one pipeline, plus two new
pieces: RAIDD log generation and auto-mapping. Scoping any single piece of
this into a concrete build is the next step — this section is the shape
of where it's all going, not a spec for any one of them yet.
