---
description: Replicate a Salesforce object into the SF_Migration mirror DB and report the row count.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py replicate *), Bash(sqlcmd *)
---
Replicate the Salesforce object `$ARGUMENTS` into SQL Server.

1. Run: `.venv/Scripts/python.exe cli.py replicate $ARGUMENTS`
2. Take the first token of `$ARGUMENTS` as the object/table name and verify the
   load with: `sqlcmd -S localhost -E -d SF_Migration -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM dbo.<Object>;"`
3. Report rows loaded, and flag any columns that came back entirely NULL — that
   usually signals a type-coercion issue (check datetime/decimal/bit) or a field
   that isn't populated in the org.

Do not run bulkops or write anything back to Salesforce.
