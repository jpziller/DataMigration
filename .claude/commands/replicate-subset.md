---
description: Replicate a root Salesforce object's subset (--where/--limit) plus every other named object automatically constrained to rows that actually belong to that subset.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py replicate-subset *), Bash(sqlcmd *)
---
Replicate a relationship-consistent subset — `$ARGUMENTS` (root object,
then every related object to also pull, e.g. `Account Contact Opportunity
Case --where "Name LIKE 'Pilot%'" --limit 50`).

1. Run: `.venv/Scripts/python.exe cli.py replicate-subset $ARGUMENTS`
2. Paste the actual output — one line per object with its real row count
   and any note (e.g. "no relationship constraint applied", "0 rows
   (parent subset empty)") — these notes are the point, not a summary.
3. Spot-check one related object's row count makes sense against the
   root's: `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON;
   SELECT COUNT(*) FROM dbo.<Object>;"` — a related object with far more
   rows than expected for the root's subset size usually means it wasn't
   actually constrained (check the "no relationship constraint applied"
   note first before assuming a bug).

Do not run bulkops or write anything back to Salesforce.
