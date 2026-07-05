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

## 3. Field-mapping spreadsheet tool (not built)

Idea: generate/maintain an Excel workbook — one tab per object — with
source field, target field, type, transformation notes, etc. Then a
"balance check" that diffs the spreadsheet against the actual `sql/
transformations/*.sql` load-table-building code in **both directions**:
- Mapping says a field should be populated, but the SQL doesn't populate it.
- SQL populates a column the mapping doc never mentions.

This keeps the human-readable mapping doc and the executable transform code
from drifting apart over a long project.

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

## 6. Mock/demo data generation (not built)

Idea: use Mockaroo and/or Snowfakery to generate realistic fake data
directly into the SQL Server mirror tables (same shape as a real
`replicate`), then run it through the normal `bulkops` load path into a
sandbox/demo org. Useful for showing off functionality or testing the
framework end-to-end without real client data.
