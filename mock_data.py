"""Mock/demo data generation via Mockaroo (roadmap #6).

Derives a Mockaroo field schema from a Salesforce object's describe() --
only createable fields are included, since this is meant to produce rows
you could actually insert -- maps each field's SF type to a reasonable
Mockaroo type (respecting real picklist values where possible), calls the
Mockaroo API for realistic fake data, and loads the result into a
`<Object>_Mock` SQL Server table for demos or test loads.

Requires MOCKAROO_API_KEY in .env. Free tier: 200 requests/day, up to 5,000
records/request -- one call per invocation, no chunking needed at that scale.
"""
import pandas as pd
import requests
from sqlalchemy import text

from type_map import sf_type_to_sql, is_compound

MOCKAROO_URL = "https://api.mockaroo.com/api/generate.json"

# SF types with no good generic Mockaroo mapping -- excluded even if
# createable (reference: no target records exist yet to point at;
# multipicklist/base64/encryptedstring: not worth the complexity for demo
# data). Reported back so the caller knows what was left out and why.
_UNSUPPORTED_TYPES = {"reference", "multipicklist", "base64", "encryptedstring"}

# Standard fields explicitly branded "Data.com" in their own describe()
# label (Jigsaw = "Data.com Key", JigsawCompanyId, CleanStatus) -- this
# framework doesn't migrate Data.com data, so there's nothing worth mocking
# here, and Jigsaw specifically has a real uniqueness constraint in orgs
# with existing Data.com-sourced records that generic mock text can collide
# with (confirmed live: 5/100 mock inserts failed on DUPLICATE_VALUE:Jigsaw).
_DATA_DOT_COM_FIELDS = {"Jigsaw", "JigsawCompanyId", "CleanStatus"}

# Task/Event's own recurrence fields (IsRecurrence + every Recurrence*
# field) are cross-validated as one interdependent cluster, not
# independent fields -- confirmed live: mocking them independently at
# random produces combinations Salesforce actively rejects (e.g.
# "ActivityDate for a recurring task", "Day of week must be blank for
# type Recurs Monthly", "Choose a type of date for repeating this task").
# Safely mocking a *valid* recurrence pattern would need real
# recurrence-rule-aware logic, not a per-field fake value -- out of scope
# here, so the whole cluster is skipped rather than producing rows that
# fail for reasons unrelated to whatever the mock run is actually testing.
_INTERDEPENDENT_FIELD_NAMES = {"IsRecurrence"}
_INTERDEPENDENT_FIELD_PREFIXES = ("Recurrence",)


def _is_interdependent_field(name):
    return name in _INTERDEPENDENT_FIELD_NAMES or name.startswith(_INTERDEPENDENT_FIELD_PREFIXES)

_NAME_HINTS = [
    (("firstname",), {"type": "First Name"}),
    (("lastname",), {"type": "Last Name"}),
    (("email",), {"type": "Email Address"}),
    (("phone", "fax"), {"type": "Phone"}),
    (("website", "url"), {"type": "URL"}),
    (("city",), {"type": "City"}),
    (("state", "province"), {"type": "State"}),
    (("postalcode", "zip"), {"type": "Postal Code"}),
    (("country",), {"type": "Country"}),
    (("street", "address"), {"type": "Street Address"}),
    (("description", "note", "comment"), {"type": "Sentences", "min": 1, "max": 3}),
    (("name",), {"type": "Company Name"}),
]


def _mockaroo_field(field):
    """Map one SF describe field to a Mockaroo field-schema entry, or None
    if there's no reasonable mapping for it."""
    name = field["name"]
    sf_type = field["type"]

    if sf_type == "boolean":
        return {"name": name, "type": "Boolean"}
    if sf_type == "int":
        return {"name": name, "type": "Number", "min": 0, "max": 1000, "decimals": 0}
    if sf_type == "double" and name.lower().endswith(("latitude", "longitude")):
        # Geolocation subfields (BillingLatitude etc.) are rarely populated
        # by clients and aren't worth mocking -- skip rather than generate
        # (a generic precision/scale-based Number would happily produce
        # e.g. 603.39, which Salesforce rejects with
        # NUMBER_OUTSIDE_VALID_RANGE since a real latitude must be between
        # -90 and 90; not worth reaching for Mockaroo's own Latitude/
        # Longitude types just to prove a field can be filled).
        return None
    if sf_type in ("double", "currency", "percent"):
        # Respect the field's real precision/scale -- e.g. a Latitude field
        # is often DECIMAL(18,15), leaving only 3 integer digits of headroom;
        # a flat max=100000 would overflow that column.
        precision = field.get("precision") or 0
        scale = field.get("scale") or 2
        integer_digits = max(precision - scale, 1) if precision else 5
        safe_max = min(10 ** integer_digits - 1, 100000)
        return {"name": name, "type": "Number", "min": 0, "max": safe_max, "decimals": min(scale, 2) if scale else 2}
    if sf_type == "date":
        # Mockaroo has no separate "Date" type -- Datetime with a date-only
        # format string is the documented way to get a date-shaped value.
        return {"name": name, "type": "Datetime", "min": "01/01/2020", "max": "12/31/2026", "format": "%Y-%m-%d"}
    if sf_type == "datetime":
        return {"name": name, "type": "Datetime", "min": "01/01/2020", "max": "12/31/2026",
                "format": "%Y-%m-%dT%H:%M:%S.000+0000"}
    if sf_type == "time":
        return {"name": name, "type": "Time", "format": "%H:%M:%S.000Z"}
    if sf_type == "phone":
        return {"name": name, "type": "Phone"}
    if sf_type == "email":
        return {"name": name, "type": "Email Address"}
    if sf_type == "url":
        return {"name": name, "type": "URL"}
    if sf_type in ("picklist", "combobox"):
        # combobox (e.g. Task.Subject) carries real picklistValues too --
        # it just also accepts free text, unlike a restricted picklist.
        values = [v["value"] for v in field.get("picklistValues", []) if v.get("active", True)]
        if values:
            return {"name": name, "type": "Custom List", "values": values}
        return {"name": name, "type": "Words", "min": 1, "max": 1}
    if sf_type in ("string", "textarea", "id"):
        lowered = name.lower()
        for keywords, spec in _NAME_HINTS:
            if any(k in lowered for k in keywords):
                return {"name": name, **spec}
        return {"name": name, "type": "Words", "min": 2, "max": 4}

    return None


def mock_schema_for_object(sf, object_name):
    """Return (mockaroo_schema, skipped_fields) for a Salesforce object.

    Only createable, non-compound fields are considered; fields whose type
    has no reasonable Mockaroo mapping (see _UNSUPPORTED_TYPES) are skipped
    and reported rather than silently dropped.
    """
    desc = getattr(sf, object_name).describe()
    schema = []
    skipped = []

    for field in desc["fields"]:
        if is_compound(field) or not field.get("createable"):
            continue
        if field["type"] in _UNSUPPORTED_TYPES:
            skipped.append((field["name"], field["type"]))
            continue
        if field["name"] in _DATA_DOT_COM_FIELDS:
            skipped.append((field["name"], "data.com"))
            continue
        if _is_interdependent_field(field["name"]):
            skipped.append((field["name"], "interdependent recurrence field, not mocked"))
            continue
        mapped = _mockaroo_field(field)
        if mapped is None:
            skipped.append((field["name"], field["type"]))
            continue
        schema.append(mapped)

    return schema, skipped


def generate_mock_data(schema, count, api_key):
    if not api_key:
        raise ValueError("MOCKAROO_API_KEY is not set -- add it to .env (see .env.example).")
    if not schema:
        raise ValueError("Empty schema -- nothing to generate.")

    resp = requests.post(
        MOCKAROO_URL,
        params={"key": api_key, "count": count},
        json=schema,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def truncate_to_field_lengths(df, fields):
    """Truncate string columns to each field's real describe() max length.

    Neither mock-data backend (Mockaroo's generators, Faker via Snowfakery)
    knows a target field's real max length (e.g. a URL generator producing
    long querystring-heavy values that overflow a Website field's real
    255-char cap) -- truncate to match, since these values need to fit a
    real Salesforce field eventually, not just the SQL insert. Shared by
    both `mock_data.py` and `snowfakery_data.py` rather than duplicated.
    """
    for f in fields:
        max_len = f.get("length")
        if max_len and f["name"] in df.columns:
            df[f["name"]] = df[f["name"]].apply(
                lambda v, n=max_len: v[:n] if isinstance(v, str) and len(v) > n else v
            )
    return df


def create_mock_table(engine, schema, table_name, fields):
    """CREATE (drop-and-recreate) [schema].[table_name] with one NULL-able
    column per field, typed via type_map.sf_type_to_sql -- shared table-DDL
    step both mock-data backends use for their own <Object>_Mock output."""
    cols_sql = ",\n    ".join(
        f'[{f["name"]}] {sf_type_to_sql(f)} NULL' for f in fields
    )
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[{table_name}];"
        ))
        cx.execute(text(f"CREATE TABLE [{schema}].[{table_name}] (\n    {cols_sql}\n);"))


def generate_mock_object_data(sf, engine, object_name, count, api_key, schema="dbo"):
    """Derive a schema from the object's describe(), generate `count` mock
    rows via Mockaroo, and load them into [schema].[<object_name>_Mock].

    Returns (rows_written, skipped_fields).
    """
    mockaroo_schema, skipped = mock_schema_for_object(sf, object_name)
    records = generate_mock_data(mockaroo_schema, count, api_key)

    table_name = f"{object_name}_Mock"
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}
    included_fields = [fields_by_name[f["name"]] for f in mockaroo_schema]

    create_mock_table(engine, schema, table_name, included_fields)

    df = pd.DataFrame(records)
    df = truncate_to_field_lengths(df, included_fields)
    df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)

    return len(df), skipped
