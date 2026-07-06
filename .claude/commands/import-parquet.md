---
description: Import a Parquet file into a typed SQL Server table in the mirror DB, inferring column types from the file's own schema.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py import-parquet *), Bash(sqlcmd *)
---
Import `$ARGUMENTS` (a Parquet file path, then a target table name;
`--append` to add to an existing table instead of recreating it).

1. Run: `.venv/Scripts/python.exe cli.py import-parquet $ARGUMENTS`
2. Column types are inferred directly from the Parquet file's own schema
   (via `pyarrow`), not guessed from the data — unlike Salesforce's Bulk
   API 2.0 CSV extracts (always text, needing coercion back to native
   types, see `type_map.py`), Parquet is already typed, so this is a
   straight schema-to-DDL mapping (`parquet_import.py`'s
   `_arrow_type_to_sql`).
3. Default behavior **drops and recreates** the target table — mention
   this plainly if the table might already hold data worth keeping. Use
   `--append` to add rows to an existing, schema-compatible table instead.
4. Report the row count imported and the table name, and remind the user
   this lands data in the mirror DB only (`SF_Migration`) — it's a new
   entry point alongside `replicate` for getting source data into SQL
   Server, not a replacement for the normal `replicate`/transform/`bulkops`
   pipeline. The imported table still needs profiling/mapping/a transform
   like any other source table before it's ready to load into Salesforce.

Writes only to the mirror DB (hard rule 1's mirror-DB-only constraint
applies here too — confirm `SQL_DATABASE` in `.env` if in doubt); doesn't
touch Salesforce at all — safe to run without confirmation.
