"""Read Salesforce org metadata (schema-level).

For deploy-level metadata (Flows, Apex, layouts) use the CLI directly:
    sf project retrieve start --metadata CustomObject:Account --target-org <alias>
This module covers the describe/schema side the migration framework needs.
"""
import json
import os

import requests


def list_objects(sf, queryable_only=True):
    objs = sf.describe()["sobjects"]
    if queryable_only:
        objs = [o for o in objs if o.get("queryable")]
    return [(o["name"], o["label"], o.get("createable"), o.get("updateable"))
            for o in objs]


def list_fields(sf, object_name):
    desc = getattr(sf, object_name).describe()
    rows = []
    for f in desc["fields"]:
        rows.append((
            f["name"], f["type"], f.get("length"),
            f.get("createable"), f.get("updateable"),
            ",".join(f.get("referenceTo") or []),
            f.get("externalId", False),
        ))
    return rows


def record_counts(sf, object_names=None):
    """GET /limits/recordCount (roadmap #41) -- one HTTP call for many
    objects' record counts, instead of a SOQL SELECT COUNT() per object.
    Confirmed against Salesforce's own REST API docs (API v40.0+, this
    org runs v67.0): the count is an **approximate, cached snapshot**
    ("may not accurately represent the number of records"), excludes
    deleted/archived rows and associated objects (History/Feed/Share/
    ChangeEvent), and needs the "View Setup and Configuration" permission.
    Fast triage across many objects (e.g. "how big are these roughly,
    before I decide what to profile deeply") -- NOT a substitute for an
    exact SELECT COUNT() when the number actually has to be right (e.g.
    validating a load landed every row); profile_salesforce_object()'s
    own COUNT(Id) stays the authoritative path for that, deliberately
    left untouched here.

    object_names: list of API names, or None for every object in the org
    (Salesforce's own default when sObjects is omitted -- can be a very
    large response for a real org, so cli.py requires an explicit
    --all-objects opt-in rather than making this the default).

    Returns {object_name: count}."""
    resp = requests.get(
        f"{sf.base_url}limits/recordCount",
        headers={"Authorization": f"Bearer {sf.session_id}"},
        params={"sObjects": ",".join(object_names)} if object_names else None,
        timeout=60,  # requests' own default is no timeout at all -- same standard as data_cloud.py/mock_data.py
    )
    resp.raise_for_status()
    return {row["name"]: row["count"] for row in resp.json().get("sObjects", [])}


def validate_external_id_field(sf, object_name, field_name):
    """Confirm field_name is real on object_name AND flagged both
    externalId and unique in the live org's describe() -- the two
    properties a Bulk API 2.0 upsert external ID/migration key actually
    needs (roadmap #50). This hardens Hard Rules 4/6/7, which only ever
    validate the SQL-Server load table's key column -- never whether the
    live org's TARGET field is genuinely configured to serve as a
    migration key. Read-only; does not create or fix the field itself --
    that's a human/admin task, this only gates on it already being
    correct.

    Returns {"ok": bool, "problems": [...]} -- each problem is its own
    plain-English message so a caller can report exactly what's wrong
    rather than a single "not valid" verdict."""
    fields = {f["name"]: f for f in getattr(sf, object_name).describe()["fields"]}

    if field_name not in fields:
        return {
            "ok": False,
            "problems": [
                f"'{field_name}' is not a field on {object_name} in this org "
                "(typo, not deployed, or removed)."
            ],
        }

    field = fields[field_name]
    problems = []
    if not field.get("externalId"):
        problems.append(f"'{field_name}' on {object_name} is not flagged as an External ID field.")
    if not field.get("unique"):
        problems.append(f"'{field_name}' on {object_name} is not flagged as Unique.")

    return {"ok": not problems, "problems": problems}


def dump_describe(sf, object_name, out_dir="metadata"):
    """Write an object's full describe to metadata/<Object>.json for git."""
    os.makedirs(out_dir, exist_ok=True)
    desc = getattr(sf, object_name).describe()
    path = os.path.join(out_dir, f"{object_name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(desc, fh, indent=2, sort_keys=True)
    return path
