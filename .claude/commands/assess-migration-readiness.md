---
description: One aggregate go/no-go readiness view per object, re-checking every gate this framework already enforces individually (hard rules 6/7/12, analyze-org-risk coverage, check-mapping-balance, Email Deliverability attestation, row-count reconciliation).
allowed-tools: Bash(.venv/Scripts/python.exe cli.py assess-migration-readiness *)
---
Assess migration readiness for `$ARGUMENTS` (one or more object names,
plus optional `--migration-key Object=Field`, `--mapping-path`, and
`--load-table Object=TableName`).

1. Run: `.venv/Scripts/python.exe cli.py assess-migration-readiness $ARGUMENTS`
2. For each object, report the READY/NOT READY verdict, then every gate
   with its own detail line.
3. Remind, if relevant: a gate reported "not checked"/"not applicable"
   never blocks the overall verdict by itself — only an explicit failure
   does. Without `--migration-key`, the two migration-key gates are
   skipped (not assumed clean); without `--mapping-path`,
   `check-mapping-balance` and the reconciliation gate's source-count
   half are skipped too. Mention which flags would unlock more/stricter
   checking if any object shows several "not checked" gates.
4. This never fixes anything itself — a NOT READY verdict just means
   "here's what to go do before this pass," pointing at the same
   individual commands (`add-bulk-load-sort-column`,
   `check-load-table-duplicate-keys`, `validate-external-id`,
   `analyze-org-risk`, `check-mapping-balance`) each gate re-runs under
   the hood.

Read-only, no new checks invented — a re-presentation of gates this
framework already enforces individually. Safe to run without
confirmation.
