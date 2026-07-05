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
    if sf_type in ("double", "currency", "percent"):
        return {"name": name, "type": "Number", "min": 0, "max": 100000, "decimals": 2}
    if sf_type == "date":
        return {"name": name, "type": "Date", "min": "1/1/2020", "max": "12/31/2026", "format": "%Y-%m-%d"}
    if sf_type == "datetime":
        return {"name": name, "type": "Datetime", "min": "1/1/2020 12:00 AM", "max": "12/31/2026 12:00 AM",
                "format": "%Y-%m-%dT%H:%M:%S.000+0000"}
    if sf_type == "time":
        return {"name": name, "type": "Time", "format": "%H:%M:%S.000Z"}
    if sf_type in ("picklist",):
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

    cols_sql = ",\n    ".join(
        f'[{f["name"]}] {sf_type_to_sql(f)} NULL' for f in included_fields
    )
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.{table_name}', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[{table_name}];"
        ))
        cx.execute(text(f"CREATE TABLE [{schema}].[{table_name}] (\n    {cols_sql}\n);"))

    df = pd.DataFrame(records)
    df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)

    return len(df), skipped
