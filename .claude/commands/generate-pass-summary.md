---
description: Draft a plain-English, client-facing pass summary from a Migration Run Book tab's Load-phase results.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-pass-summary *)
---
Generate a pass summary for `$ARGUMENTS` (workbook path, plus `--tab
<name>` and `--output <path.md>`, both required).

1. Run: `.venv/Scripts/python.exe cli.py generate-pass-summary $ARGUMENTS`
   (add `--load-table Object=TableName`, repeatable, for a plain-language
   root cause per failure signature via `triage-failures` instead of just
   a raw failed count — only for objects explicitly named this way, never
   guessed from the Run Book's own Object cell).
2. Confirm the file was written, and relay the headline numbers (object
   count, total/succeeded/failed records) back in the reply.
3. Remind, if relevant: this is plain Markdown for v1, deliberately simple
   (same discipline as `/generate-run-book-flowchart`'s own v1 framing) —
   ready to paste into an email or a client-facing doc, not a polished
   Word document (that's `solution_doc.py`'s machinery, not reused here
   yet).
4. If failures exist but no `--load-table` was given for that object, the
   summary just points at the Run Book's own Notes/Error Details columns
   instead of a root cause — mention that passing `--load-table` would
   add real detail, if the load table for that object still exists.

Read-only, no Salesforce connection needed — just the local `.xlsx` file
and (with `--load-table`) the mirror DB. Safe to run without confirmation.
