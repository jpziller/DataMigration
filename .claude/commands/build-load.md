---
description: Run a T-SQL transform to build a *_Load table, then preview it. Does NOT load to Salesforce.
allowed-tools: Bash(sqlcmd *), Read(sql/**)
---
Build the load table using the transform file `$ARGUMENTS` (a path under
`sql/transformations/`).

1. Read the .sql file first so you understand what table it builds and which
   columns map to which Salesforce fields.
2. Execute it: `sqlcmd -S localhost -E -d SF_Migration -i "$ARGUMENTS"`
3. Identify the load table it created and report: total row count, 5 sample
   rows, and a count of rows missing the external-id / migration-key column
   (those would break result mapping on insert).
4. Summarize what would be sent to Salesforce, then STOP. Loading is a separate,
   explicitly confirmed step — do not run bulkops.
