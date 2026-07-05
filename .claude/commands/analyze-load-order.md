---
description: Compute a recommended load order for a set of Salesforce objects based on their lookup/master-detail dependencies.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py analyze-load-order *), Bash(sqlcmd *)
---
Compute the recommended load order for the objects in `$ARGUMENTS` (a
space-separated list of object API names).

1. Run: `.venv/Scripts/python.exe cli.py analyze-load-order $ARGUMENTS`
2. Report the load order (parents before children), any self-referencing
   fields flagged (need a two-pass load: insert without it, update it in),
   and any unresolved circular dependencies (don't guess how to break these
   — flag them for a human decision).
3. Mention that results are also queryable afterward from
   `dbo.ObjectDependency` (raw edges) / `dbo.ObjectLoadOrder` (computed
   order) without re-running the analysis.

Read-only against the org; writes only to dbo.ObjectDependency/
dbo.ObjectLoadOrder in the mirror DB — safe to run without confirmation.
