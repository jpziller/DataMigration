"""Ad hoc SOQL query tool -- results to console, CSV, or Excel.

Scoped to Salesforce CRM objects via the REST Query API (sf.query /
sf.query_all), not Bulk API -- this is for quick lookups and troubleshooting
(the Salesforce Inspector Reloaded / Workbench / DBAmp-query use case), not
large extracts (use `replicate` for that).

Data Cloud (D360) objects use a genuinely different query surface -- Data
Model Objects via the Data Cloud Query API, not standard SOQL against
sf.query() -- and aren't supported here yet.
"""
import csv as csv_module

import pandas as pd


def run_query(sf, soql, fetch_all=False):
    """Run a SOQL query. Returns (records, total_size, truncated).

    records: list of flat dicts -- relationship fields (e.g. Account.Name on
              a Contact query) are flattened to dotted keys.
    total_size: Salesforce's reported total match count.
    truncated: True if fetch_all=False and more records exist than were
               fetched (pass fetch_all=True, or add/tighten a LIMIT, to
               avoid this).
    """
    if fetch_all:
        raw_records = sf.query_all(soql)["records"]
        total_size = len(raw_records)
        truncated = False
    else:
        result = sf.query(soql)
        raw_records = result["records"]
        total_size = result["totalSize"]
        truncated = not result["done"]

    records = [_flatten(r) for r in raw_records]
    return records, total_size, truncated


def _flatten(record, prefix=""):
    flat = {}
    for key, value in record.items():
        if key == "attributes":
            continue
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, prefix=f"{full_key}."))
        else:
            flat[full_key] = value
    return flat


def _ordered_fieldnames(records):
    seen = []
    for r in records:
        for k in r:
            if k not in seen:
                seen.append(k)
    return seen


def to_csv(records, path):
    fieldnames = _ordered_fieldnames(records)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv_module.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return path


def to_excel(records, path):
    df = pd.DataFrame(records, columns=_ordered_fieldnames(records) or None)
    df.to_excel(path, index=False, engine="openpyxl")
    return path
