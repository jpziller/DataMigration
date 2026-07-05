---
description: Generate realistic mock/demo data for a Salesforce object via Mockaroo and load it into a SQL Server table.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-mock-data *)
---
Generate mock data for `$ARGUMENTS` (an object name, optionally with a row
count like `Account 100`).

**First, check whether Mockaroo is connected** — run:
```
.venv/Scripts/python.exe -c "from config import get_settings; print('set:', bool(get_settings().mockaroo_api_key))"
```
This only reports true/false, never the key itself (`.env` is never read or
printed — see CLAUDE.md rule 3).

**If it's not set**, walk the user through connecting it rather than
failing silently:
1. Sign up / log in at mockaroo.com (free tier: 200 requests/day, up to
   5,000 records/request).
2. Get the API key from mockaroo.com/account.
3. Add it to `.env` themselves (never paste it in chat): `MOCKAROO_API_KEY=<key>`
   (a placeholder line already exists in `.env.example`).

**Once it's set**, run:
`.venv/Scripts/python.exe cli.py generate-mock-data $ARGUMENTS`

This derives a mock schema from the object's describe() (only createable
fields; picklists use their real valid values), calls Mockaroo, and loads
the result into `dbo.<Object>_Mock`. Report the row count and any skipped
fields (reference/multipicklist/base64 fields have no reasonable mock
mapping and are listed, not silently dropped).

Writes only to a `<Object>_Mock` table in the mirror DB — never touches
Salesforce. Safe to run without confirmation once Mockaroo is connected.
