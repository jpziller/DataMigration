---
description: Promote an org-derived data-shape profile to cloud-level, reusable IP under okf/<cloud>/data-shapes/ — strips org-specifics, keeps cloud-true structure/auto-generated-children/date-range pairs.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generalize-data-shape *)
---
Generalize the data-shape profile(s) for `$ARGUMENTS` (one or more object
names, then `--cloud <cloud>`, e.g. `GiftCommitment --cloud nonprofit-cloud`).

1. Run: `.venv/Scripts/python.exe cli.py generalize-data-shape $ARGUMENTS`
2. Paste the actual output — the per-object cloud summary (standard/packaged
   structure, auto-generated children, date-range pairs) is the point.
3. This reads the org-derived `data_shapes/<Object>.json` (build it first with
   `build-data-shape-profile`) and writes `okf/<cloud>/data-shapes/<Object>.json`,
   stripping everything org-specific — the org alias, org custom fields (incl.
   `MigrationID__c`), this org's automation counts / field population, and the
   numeric auto-generation rates — keeping only what's true of the cloud for
   any org. The result is **committed, shareable IP**, not org-specific data:
   commit `okf/<cloud>/data-shapes/` deliberately.
4. Consumers: `gather-okf --objects <Object>` surfaces these alongside the
   prose docs, and `show-data-shape <Object> --cloud <cloud>` reads one when a
   fresh clone has no local org profile yet.

Read-only against Salesforce (no org connection — reads a local profile,
writes a local committed file). Roadmap #83.
