---
description: Summarize the results of a load by reading the Id/Error columns of a *_Load table.
allowed-tools: Bash(sqlcmd *)
---
Validate the load table `$ARGUMENTS` after a bulkops run.

Query `dbo.$ARGUMENTS` and report:
- total rows, succeeded (Id populated), failed (Error populated)
- the top error messages grouped by frequency (GROUP BY the Error text)
- 5 example failing rows with their Error text

Then suggest the most likely fix for the most common error. Do not modify data
or re-run the load without an explicit go-ahead.
