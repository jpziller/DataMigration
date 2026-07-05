"""Field-mapping spreadsheet tool (roadmap #3).

generate_mapping_workbook() builds an Excel mapping doc from a Salesforce
object's describe() -- one row per target field (type, required, real
picklist values), with blank Source Field/Source Type/Transformation Notes
columns for a human to fill in. If a source SQL table is given, its columns
are listed on a companion reference sheet. This does NOT auto-guess the
mapping (that's a separate roadmap item) -- it only builds the structure.

check_mapping_balance() diffs a filled-in mapping doc against the actual
`sql/transformations/*.sql` load-table-building code in both directions, so
the human-readable doc and the executable transform can't silently drift
apart:
  - documented_not_implemented: the doc says a field is mapped (has a
    Source Field), but the transform's INSERT INTO column list doesn't
    populate it.
  - implemented_not_documented: the transform populates a column the
    mapping doc doesn't have a row for at all, or has a row for but with no
    Source Field filled in. This also catches a transform populating a
    field that doesn't even exist in the object's current describe() --
    that field won't appear as a row at all, so it always surfaces here.
"""
import os
import re

import pandas as pd
from sqlalchemy import text

from type_map import is_compound

_INSERT_INTO_RE = re.compile(
    r"INSERT\s+INTO\s+(?:\[?[\w]+\]?\.)?\[?(\w+)\]?\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_INVALID_SHEET_CHARS = re.compile(r"[:\\/?*\[\]]")


def _safe_sheet_name(name):
    return _INVALID_SHEET_CHARS.sub("_", name)[:31]


def generate_mapping_workbook(sf, object_name, output_path, engine=None, source_table=None, schema="dbo"):
    desc = getattr(sf, object_name).describe()
    rows = []
    for f in desc["fields"]:
        if is_compound(f):
            continue
        picklist_values = ""
        if f["type"] in ("picklist", "multipicklist"):
            picklist_values = "; ".join(
                v["value"] for v in f.get("picklistValues", []) if v.get("active", True)
            )
        required = bool(f.get("createable")) and not f.get("nillable", True) and f["type"] != "boolean"
        rows.append({
            "Target Field": f["name"],
            "Target Type": f["type"],
            "Required": required,
            "Picklist Values": picklist_values,
            "Source Field": "",
            "Source Type": "",
            "Transformation Notes": "",
        })

    df = pd.DataFrame(rows)

    source_df = None
    if source_table and engine is not None:
        with engine.connect() as cx:
            cols = cx.execute(
                text(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table ORDER BY ORDINAL_POSITION"
                ),
                {"schema": schema, "table": source_table},
            ).mappings().all()
        source_df = pd.DataFrame([{"Source Column": c["COLUMN_NAME"], "SQL Type": c["DATA_TYPE"]} for c in cols])

    # Append as a new sheet in an existing workbook (one workbook, one tab
    # per object) rather than overwriting it -- generating a second object's
    # mapping into the same path must not silently erase the first one's.
    if os.path.exists(output_path):
        writer_kwargs = {"mode": "a", "if_sheet_exists": "replace"}
    else:
        writer_kwargs = {"mode": "w"}

    with pd.ExcelWriter(output_path, engine="openpyxl", **writer_kwargs) as writer:
        df.to_excel(writer, sheet_name=_safe_sheet_name(object_name), index=False)
        if source_df is not None and not source_df.empty:
            source_df.to_excel(writer, sheet_name=_safe_sheet_name(f"{source_table}_Source"), index=False)

    return output_path


def extract_insert_columns(sql_text, table_name=None):
    """Return the column list from an INSERT INTO (...) statement in the
    given SQL text -- the first one matching table_name (case-insensitive,
    schema prefix/brackets ignored), or the first INSERT INTO found if
    table_name is None. Returns None if no match is found."""
    for match in _INSERT_INTO_RE.finditer(sql_text):
        found_table, col_list = match.group(1), match.group(2)
        if table_name is None or found_table.lower() == table_name.lower():
            return [c.strip().strip("[]") for c in col_list.split(",")]
    return None


def check_mapping_balance(mapping_path, object_name, transform_sql_path, load_table_name=None):
    df = pd.read_excel(mapping_path, sheet_name=_safe_sheet_name(object_name))

    documented_mask = df["Source Field"].notna() & (df["Source Field"].astype(str).str.strip() != "")
    documented = set(df.loc[documented_mask, "Target Field"])

    with open(transform_sql_path, encoding="utf-8") as fh:
        sql_text = fh.read()

    implemented_cols = extract_insert_columns(sql_text, load_table_name)
    if implemented_cols is None:
        raise ValueError(f"No INSERT INTO statement found in {transform_sql_path}")
    implemented = set(implemented_cols)

    return {
        "documented_not_implemented": sorted(documented - implemented),
        "implemented_not_documented": sorted(implemented - documented),
    }
