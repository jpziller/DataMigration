---
description: Deterministic tier (1-4) assessment for a completed bulkops run -- orchestrator Phase 1, read-only, never changes how bulkops itself is gated.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py orchestrator-assess *)
---
Assess the tier for `$ARGUMENTS` (an object name; optional `--log-id N`,
`--environment uat|prod`).

1. Run: `.venv/Scripts/python.exe cli.py orchestrator-assess $ARGUMENTS`
2. Paste the actual output — the tier number alone isn't the point, the
   full list of reasons that fired is (or didn't fire, for a clean tier 1).
3. If it reports "no dbo.ObjectAutomationRisk data for this object," that
   means `analyze-org-risk` hasn't been run for it yet — mention that as
   the fix, don't just note the missing data.
4. If `coarse_approval_eligible` is `False`, mention that plainly too —
   it means this object has no prior logged history yet, so it isn't
   eligible for anything beyond Stage 1/shadow mode regardless of how
   clean this particular run looks.

Read-only, no Salesforce call, no confirmation needed. See
`docs/ORCHESTRATOR_DESIGN.md` for the full tier taxonomy and what's
deliberately not built yet (Phase 2's actual coarse-approval mechanism).
