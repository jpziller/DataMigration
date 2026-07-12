---
description: Deliberately corrupt mock data to provoke known Salesforce Bulk API failure classes on purpose, so validation-rule collisions surface during Dev testing instead of during a real client load.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py generate-adversarial-mock-data *)
---
Generate adversarial mock data for `$ARGUMENTS` (an object name, plus
`--count` and one or more `--scenario scenario:field:rows`).

**First, check whether Mockaroo is connected** (same check
`/generate-mock-data` uses) — run:
```
.venv/Scripts/python.exe -c "from config import get_settings; print('set:', bool(get_settings().mockaroo_api_key))"
```
If it's not set, walk the user through connecting it the same way
`/generate-mock-data` does, rather than failing silently.

**Once it's set**, confirm real field names via `describe`/`dump-describe`
first (the No Invented Field Names Rule, #5) — never guess which field to
pass to a `--scenario`. Then run:
`.venv/Scripts/python.exe cli.py generate-adversarial-mock-data $ARGUMENTS`

Five scenarios, one of `duplicate_key`/`oversized_string`/
`missing_required`/`invalid_picklist`/`bad_reference` per `--scenario`
(repeatable, `scenario:field:rows`):
- `duplicate_key` — two or more rows share one migration-key value
  (DUPLICATE_VALUE).
- `oversized_string` — a value deliberately exceeds the target field's
  real describe() length (STRING_TOO_LONG).
- `missing_required` — a genuinely required field is left blank
  (REQUIRED_FIELD_MISSING) — the field must actually be required
  (not nillable, no default-on-create) or this raises.
- `invalid_picklist` — a picklist/combobox field gets a value that isn't
  one of its real picklistValues.
- `bad_reference` — a reference field (never part of a normal happy-path
  mock run) gets a well-formed-looking but real-org-guaranteed-nonexistent
  Id (INVALID_CROSS_REFERENCE_KEY).

Report the row count, which scenario touched how many rows on which
field, and any skipped fields (same "no reasonable mock mapping" list
`/generate-mock-data` reports).

Writes to `<Object>_Mock_Adversarial` — never `<Object>_Mock`, so this
never mixes into or overwrites the normal happy-path mock table. Every
corrupted row is tagged in a `REF_AdversarialScenario` column
(`REF_`-prefixed, hard rule 13 — `bulkops` never sends it to Salesforce),
so the same table can go straight into a real, separately-confirmed
`bulkops` call to see how the pipeline actually handles each provoked
failure.

Writes only to the mirror DB — never touches Salesforce itself. Safe to
run without confirmation once Mockaroo is connected.
