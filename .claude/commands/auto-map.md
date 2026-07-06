---
description: Suggest source->target field mappings for a profiled SQL table, and write them into an existing mapping doc's Target block, Notes, and Migrate Data columns.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py auto-map *)
---
Auto-suggest mappings for `$ARGUMENTS` (target object name, mapping .xlsx
path, source SQL table name — all three required).

1. **Hard prerequisite**: the source table must already be profiled
   (`/profile <table>`). If it isn't, the command raises a clear error
   telling you to profile first — don't try to work around this, just run
   `/profile` and retry.
2. Run: `.venv/Scripts/python.exe cli.py auto-map $ARGUMENTS`
3. Matching is layered, most-confident first: exact/normalized name match,
   then a git-tracked synonym thesaurus (`reference/field_synonyms.json` —
   e.g. `zip`/`postal`/`postcode` all resolve to `BillingPostalCode`), then
   fuzzy string matching as a conservative fallback. Every suggestion also
   runs through a data-quality gate using existing profiling data
   (`dbo.FieldProfile`/`dbo.FieldProfileValues`): a field that's barely
   populated, or 100% populated with only one distinct value, gets
   downgraded to "No" or "Review" even if the name matches cleanly —
   a clean name match never overrides bad underlying data.
4. Report the summary line the command prints (N of M fields matched,
   Yes/No/Review counts), then the per-field table if useful. The mapping
   doc's Target block, Notes, and Migrate Data columns are updated in place
   — but any row where a human already filled in the Target block's Field
   API is left untouched; a human decision always wins over a suggestion.
5. Remind the user this is a starting point for review, not a finished
   mapping — every "Yes" and especially every "Review" is worth a glance,
   and any correction they make is a candidate to add as a new alias in
   `reference/field_synonyms.json` so the thesaurus improves over time.

Read-only against the org; writes to `dbo.SourceRegistry`/
`dbo.AutoMapSuggestions` in the mirror DB and to the local mapping .xlsx —
safe to run without confirmation.
