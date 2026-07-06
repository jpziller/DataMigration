---
description: Auto-draft a migration solution/design Word document from load-order analysis, a mapping doc, and profiling data.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-solution-doc *)
---
Generate a solution document for `$ARGUMENTS` (output .docx path, then one or
more Salesforce object names).

1. Run: `.venv/Scripts/python.exe cli.py generate-solution-doc $ARGUMENTS`
   Useful options: `--mapping-path <xlsx>` (pulls per-object field-mapping
   summaries from a `generate-mapping-doc`/`auto-map` workbook — omit it and
   those sections just note mapping isn't documented yet, rather than
   failing), `--company`/`--project`/`--prepared-by` (cover-page text),
   `--appendix` (adds the full field-by-field mapping table — off by
   default, since it can get long), `--template <custom.docx>` (see below).
2. The document is built fresh each run from whatever load-order analysis,
   mapping doc, and profiling data currently exist — it re-runs load-order
   analysis itself (cheap, describe()-only) so the load order is always
   current, but does **not** re-run profiling or mapping (those are
   deliberately separate, more expensive steps you control yourself).
3. Sections: what's being built (object list in load order), how it's being
   done (the SQL-centric methodology, in plain language), a load-order
   table, one subsection per object (source table, row count, mapping
   status, profiling summary), and an optional appendix.
4. **No binary template is checked into this repo.** With no `--template`,
   the document is built entirely from Python (`solution_doc.py`) — fully
   reviewable in git, like everything else this framework generates. A data
   architect who wants their own branding (logo, colors, house style) can
   build a `.docx` in Word containing the same context fields as Jinja2
   tags (`docxtpl` syntax — see `solution_doc.py`'s module docstring for
   the exact tag contract) and pass it via `--template`; disable Word's
   autocorrect before typing tags, since curly-quote autocorrection breaks
   them.
5. Report the object count and whether the default or a custom template was
   used, and call out any unresolved circular dependencies the command
   flags (same signal `/analyze-load-order` surfaces).

Read-only against the org and mirror DB; writes only the output .docx file
— safe to run without confirmation.
