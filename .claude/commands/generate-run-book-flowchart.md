---
description: Generate a Mermaid process-flow diagram straight from a Migration Run Book tab's own Stage/Object/Dependency/Status columns.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-run-book-flowchart *)
---
Generate a Run Book flowchart for `$ARGUMENTS` (workbook path, plus
`--tab <name>` and `--output <path.md>`, both required).

1. Run: `.venv/Scripts/python.exe cli.py generate-run-book-flowchart $ARGUMENTS`
2. Confirm the file was written and report the phase/step/edge counts.
3. Remind, if relevant: this is deliberately simple v1 (roadmap #52) --
   one subgraph per phase banner, one node per step (labeled from the
   Object column), edges parsed only from the Dependency column's real
   "After: X, Y" text (the same shape `_load_order_rows()` itself writes
   for the Load phase), never fabricated top-to-bottom chaining. Node
   color matches the workbook's own Status conditional-formatting
   palette (Not Started/In Process/Completed/Issue/N/A), so the diagram
   visually agrees with the spreadsheet rather than inventing a separate
   meaning for color.
4. If any dependency mention couldn't be matched to a row in this tab
   (e.g. an object referenced but not yet in scope for this pass), it's
   dropped rather than guessed at, and reported back as
   "unresolved dependency mention(s)" -- surface this if it's non-empty,
   the same "visible gap, not a silent guess" philosophy as
   `resolve-record-types`' unmatched-`DeveloperName` NULL.
5. Separately, a non-blank Dependency cell that doesn't match the
   "After: X" format at all (a plausible hand-filled free-text note) is
   reported as an "unparsed dependency note" -- distinct from an
   unresolved mention, since this one was never matched to the "After:"
   shape in the first place and may be a real dependency stated in
   prose. Surface this too if it's non-empty.

Read-only, no Salesforce/SQL connection needed — just this local `.xlsx`
file. Safe to run without confirmation. GitHub and most modern Markdown
renderers already render the fenced ` ```mermaid ` block natively; Lucid
also supports paste-to-import. A polished, hand-styled diagram elsewhere
is a named future stretch, not part of this v1.
