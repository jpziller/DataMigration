"""Read Salesforce org metadata (schema-level).

For deploy-level metadata (Flows, Apex, layouts) use the CLI directly:
    sf project retrieve start --metadata CustomObject:Account --target-org <alias>
This module covers the describe/schema side the migration framework needs.
"""
import json
import os


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


def dump_describe(sf, object_name, out_dir="metadata"):
    """Write an object's full describe to metadata/<Object>.json for git."""
    os.makedirs(out_dir, exist_ok=True)
    desc = getattr(sf, object_name).describe()
    path = os.path.join(out_dir, f"{object_name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(desc, fh, indent=2, sort_keys=True)
    return path
