"""Adversarial mock data generation (roadmap #62).

A companion to mock_data.py's happy-path generate-mock-data: takes the
same describe()-derived Mockaroo schema and deliberately corrupts a
chosen subset of rows to provoke known Salesforce Bulk API failure
classes on purpose, so a validation-rule collision or pre-flight-check
gap surfaces during Dev testing -- not for the first time against real
client data, or worse, during a UAT pass.

Every scenario is opt-in via its own field + row count -- nothing is
corrupted unless explicitly asked for, same "no guessing" discipline as
every other generator in this framework. Rows are assigned to scenarios
in disjoint, non-overlapping ranges (in the order given), so a row has
at most one deliberate corruption, tagged in a REF_AdversarialScenario
column -- REF_-prefixed (hard rule 13) so bulkops.py automatically
excludes it from what's sent to Salesforce; the SAME table can go
straight into a real bulkops call without any extra bookkeeping, and
triage-failures' output can be matched back to exactly which scenario
was deliberately provoked, not confused for a real data-quality
surprise. Writes to <Object>_Mock_Adversarial -- never <Object>_Mock,
so this never silently mixes into or overwrites the normal happy-path
mock table generate-mock-data produces.

Five scenarios, chosen to match documented, stable Salesforce Bulk API
error codes triage-failures (#61) already has guidance for:
  - duplicate_key: two or more rows share one migration-key value
    (DUPLICATE_VALUE / tests hard rule 7's dupe-check).
  - oversized_string: a string field's value deliberately exceeds the
    target's real describe() length (STRING_TOO_LONG).
  - missing_required: a genuinely required field (not nillable, no
    default-on-create) is left blank (REQUIRED_FIELD_MISSING).
  - invalid_picklist: a picklist/combobox field gets a value that isn't
    one of its real picklistValues (INVALID_FIELD_VALUE-shaped errors).
  - bad_reference: a reference field (never included in a normal
    happy-path mock run -- there's no target Id to point at yet) is
    filled with a well-formed-looking but real-org-guaranteed-nonexistent
    Id (INVALID_CROSS_REFERENCE_KEY).

Deliberately NOT attempted here: deriving a scenario automatically from
an active validation rule's ErrorDisplayField. risk_analyzer.py's
dbo.ObjectAutomationRisk only persists a ValidationRule's ItemName/
IsActive/Detail (ErrorMessage) today, not ErrorDisplayField -- there's
nothing on file yet to build that suggestion from without either a
second live Tooling API call or a schema change to that table. A
disclosed gap, not an oversight; a natural follow-up once
ErrorDisplayField is persisted there too.
"""
import pandas as pd

import mock_data

_TAG_COLUMN = "REF_AdversarialScenario"
_TAG_COLUMN_LENGTH = 40

_KNOWN_SCENARIOS = (
    "duplicate_key", "oversized_string", "missing_required",
    "invalid_picklist", "bad_reference",
)


def _fake_salesforce_id(seq):
    """An 18-char, alphanumeric-with-digits value shaped like a real
    Salesforce Id (matches bulkops.py's own _SF_ID_TOKEN_RE), but never a
    real record's Id -- for deliberately provoking
    INVALID_CROSS_REFERENCE_KEY on a reference field. seq % 10**15 keeps
    the numeric part at a fixed 15 digits no matter how large seq gets
    (found in review: the original f"...{seq:03d}..." format silently
    grew past 18 total characters once seq reached 1000, breaking the
    real-Id-shape invariant for any bad_reference scenario corrupting
    1000+ rows)."""
    return f"{seq % 10**15:015d}AAA"


def _corrupt_duplicate_key(df, row_indices, field):
    if len(row_indices) < 2:
        raise ValueError("duplicate_key needs at least 2 rows to create a real duplicate.")
    shared_value = df.loc[row_indices[0], field]
    for idx in row_indices[1:]:
        df.loc[idx, field] = shared_value


def _corrupt_oversized_string(df, row_indices, field, max_length):
    oversized_value = "X" * (max_length + 50)
    df.loc[row_indices, field] = oversized_value


def _corrupt_missing_required(df, row_indices, field):
    df.loc[row_indices, field] = None


def _corrupt_invalid_picklist(df, row_indices, field):
    df.loc[row_indices, field] = "NOT_A_REAL_PICKLIST_VALUE_ZZZ"


def _corrupt_bad_reference(df, row_indices, field):
    for i, idx in enumerate(row_indices):
        df.loc[idx, field] = _fake_salesforce_id(i)


def generate_adversarial_mock_data(sf, engine, object_name, count, api_key, scenarios, schema="dbo"):
    """Generate count mock rows for object_name (same describe()-derived
    Mockaroo schema as generate_mock_object_data()), then deliberately
    corrupt a disjoint slice of rows per requested scenario.

    scenarios: {scenario_name: {"field": <api name>, "rows": N}, ...} --
    one or more of _KNOWN_SCENARIOS. Every field is validated against the
    object's real describe() before anything is corrupted (a wrong field
    for the chosen scenario raises immediately, rather than silently
    corrupting something that doesn't test what was asked for).

    Returns (rows_written, applied_summary, skipped_fields) --
    applied_summary is [{"scenario", "field", "rows"}, ...] in the order
    scenarios were given; skipped_fields is generate_mock_object_data()'s
    own "no reasonable mock mapping" list, unchanged."""
    if not scenarios:
        raise ValueError("scenarios is empty -- nothing to corrupt. Pass at least one scenario.")
    unknown = set(scenarios) - set(_KNOWN_SCENARIOS)
    if unknown:
        raise ValueError(f"Unknown scenario(s) {sorted(unknown)} -- choose from {list(_KNOWN_SCENARIOS)}.")

    total_corrupt_rows = sum(spec["rows"] for spec in scenarios.values())
    if total_corrupt_rows > count:
        raise ValueError(
            f"Requested {total_corrupt_rows} corrupted row(s) across all scenarios, "
            f"but count is only {count} -- raise --count or reduce the scenario row counts."
        )

    mockaroo_schema, skipped = mock_data.mock_schema_for_object(sf, object_name)
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}

    for scenario_name, spec in scenarios.items():
        field_def = fields_by_name.get(spec["field"])
        if field_def is None:
            raise ValueError(f"'{spec['field']}' isn't a real field on {object_name} (check describe()).")
        if scenario_name == "oversized_string" and not field_def.get("length"):
            raise ValueError(f"'{spec['field']}' has no max length in describe() -- not a string-shaped field.")
        if scenario_name == "missing_required" and (field_def.get("nillable") or field_def.get("defaultedOnCreate")):
            raise ValueError(f"'{spec['field']}' isn't actually required on {object_name} (nillable or defaulted) -- pick a genuinely required field instead.")
        if scenario_name == "invalid_picklist" and field_def["type"] not in ("picklist", "combobox"):
            raise ValueError(f"'{spec['field']}' isn't a picklist/combobox field on {object_name}.")
        if scenario_name == "bad_reference" and field_def["type"] != "reference":
            raise ValueError(f"'{spec['field']}' isn't a reference field on {object_name}.")
        if scenario_name == "duplicate_key" and spec["rows"] < 2:
            # Same "validate before the real Mockaroo API call" discipline
            # as every other scenario check above -- found in review: this
            # specific check used to live inside _corrupt_duplicate_key(),
            # which only runs after generate_mock_data() already burned a
            # real, rate-limited (200/day) Mockaroo request.
            raise ValueError("duplicate_key needs at least 2 rows to create a real duplicate.")

    # bad_reference targets a field mock_data.py deliberately never
    # includes in a normal happy-path schema (no target Ids exist yet to
    # point at) -- add it in here specifically so there's a real column
    # to corrupt.
    extra_fields = [
        fields_by_name[spec["field"]] for name, spec in scenarios.items()
        if name == "bad_reference"
    ]

    records = mock_data.generate_mock_data(mockaroo_schema, count, api_key)
    included_fields = [fields_by_name[f["name"]] for f in mockaroo_schema] + extra_fields

    df = mock_data.truncate_to_field_lengths(pd.DataFrame(records), included_fields)
    for f in extra_fields:
        df[f["name"]] = None  # no target Ids exist yet -- NULL is the safe default for untouched rows
    df[_TAG_COLUMN] = None

    oversized_fields = {spec["field"] for name, spec in scenarios.items() if name == "oversized_string"}
    ddl_fields = [
        {**f, "length": (f.get("length") or 255) + 100} if f["name"] in oversized_fields else f
        for f in included_fields
    ]

    cursor = 0
    applied_summary = []
    for scenario_name, spec in scenarios.items():
        field, n_rows = spec["field"], spec["rows"]
        row_indices = df.index[cursor:cursor + n_rows].tolist()
        cursor += n_rows

        if scenario_name == "duplicate_key":
            _corrupt_duplicate_key(df, row_indices, field)
        elif scenario_name == "oversized_string":
            _corrupt_oversized_string(df, row_indices, field, fields_by_name[field]["length"])
        elif scenario_name == "missing_required":
            _corrupt_missing_required(df, row_indices, field)
        elif scenario_name == "invalid_picklist":
            _corrupt_invalid_picklist(df, row_indices, field)
        elif scenario_name == "bad_reference":
            _corrupt_bad_reference(df, row_indices, field)

        df.loc[row_indices, _TAG_COLUMN] = scenario_name
        applied_summary.append({"scenario": scenario_name, "field": field, "rows": len(row_indices)})

    table_name = f"{object_name}_Mock_Adversarial"
    tag_field = {"name": _TAG_COLUMN, "type": "string", "length": _TAG_COLUMN_LENGTH}
    mock_data.create_mock_table(engine, schema, table_name, ddl_fields + [tag_field])
    df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)

    return len(df), applied_summary, skipped
