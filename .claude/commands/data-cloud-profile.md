---
description: Look up Unified Profile data by an equality filter -- the CLI alternative to Data Cloud's own Profile Explorer.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py data-cloud-profile *)
---
Look up a Unified Profile using `$ARGUMENTS` (a data model name like
`UnifiedssotIndividualIndv__dlm` plus a filter like
`"[ssot__LastName__c=Smith]"`; if the user gave a person/value but not
the exact syntax, build the filter for them).

1. Run: `.venv/Scripts/python.exe cli.py data-cloud-profile <dataModelName> "<filter>"`
   (add `--fields`, `--limit`, `--offset`, `--orderby` as asked).
2. Paste the actual output into the reply — don't summarize it.
3. A filter is required by the API itself — only equality comparisons,
   AND-combined as `[FieldA=X,FieldB=Y]`. There is no "browse everyone"
   mode; suggest `/query` against the Unified DMO for broader browsing.
4. If unsure which Unified DMOs exist, `/query` on `list-objects` output
   filtered to `Unified*__dlm` names, or run `/describe` on one to see
   its real field names before guessing (CLAUDE.md rule 5).

Read-only — safe to run without confirmation.
