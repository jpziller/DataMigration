---
description: Show the current state of the migration — mirror tables, load tables, row counts, and uncommitted transforms.
allowed-tools: Bash(sqlcmd *), Bash(git status*)
---
## Tables in SF_Migration
!`sqlcmd -S localhost -E -d SF_Migration -h -1 -W -Q "SET NOCOUNT ON; SELECT s.name + '.' + t.name AS tbl, p.rows AS row_count FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1) ORDER BY tbl;"`

## Uncommitted changes
!`git status --short`

## Instructions
From the data above, give a short status readout:
- which objects are replicated (mirror tables) and their row counts
- which `*_Load` tables exist
- any uncommitted transform changes worth committing

Keep it brief — a status line per item, not a report.
