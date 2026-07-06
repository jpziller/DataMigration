"""Field-mapping spreadsheet tool (roadmap #3).

Column structure is modeled on a real-world field-inventory-and-mapping
template (structure/column-names only -- reviewed for format, not content):
one row per SOURCE field, a block of migration-decision columns (populated
%, migrate data/field Y-N, business review/decision), then a blank Target
block (Object/Field API/Label/Type/Description/Notes) for a human to fill
in once a mapping is actually decided. This is the opposite orientation
from an earlier version of this tool (which listed one row per TARGET
field) -- row-per-source-field is the right shape, since the real workflow
is "for each source field, decide if/how it maps," not the reverse.

generate_mapping_workbook() builds this from a SQL Server source table's
real columns (INFORMATION_SCHEMA) against a named Salesforce target object.
If profiling data already exists for that table (see profiling.py),
"Data Profile Populated On"/"Data Profile %" are pre-filled from it -- those
columns exist for exactly that purpose. This does NOT auto-guess the
mapping itself (that's a separate roadmap item) -- only the structure.

check_mapping_balance() diffs a filled-in mapping doc against the actual
`sql/transformations/*.sql` load-table-building code in both directions, so
the human-readable doc and the executable transform can't silently drift
apart:
  - documented_not_implemented: the doc shows a target field as mapped
    (Target block's Field API is filled in), but the transform's INSERT
    INTO column list doesn't populate it.
  - implemented_not_documented: the transform populates a column with no
    row showing it as mapped. This also catches a transform populating a
    field that doesn't exist in the object's current describe() at all --
    a nonexistent field can't have a row, so it always surfaces here.
"""
import os
import re

import openpyxl
from sqlalchemy import text

_INSERT_INTO_RE = re.compile(
    r"INSERT\s+INTO\s+(?:\[?[\w]+\]?\.)?\[?(\w+)\]?\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_INVALID_SHEET_CHARS = re.compile(r"[:\\/?*\[\]]")

_HEADERS = [
    "Source Object", "Field API", "Field Label", "Data Type", "Description",
    "Data Profile Populated On", "Data Profile %", "Notes",
    "Migrate Data", "Migrate Field", "Biz Review Req", "Biz Decision",
    None,  # spacer column between source and target blocks
    "Target Object", "Field API", "Field Label", "Data Type", "Description", "Notes",
]
_TARGET_FIELD_API_COL = 15  # 1-indexed position of the Target block's "Field API" column


def _safe_sheet_name(name):
    return _INVALID_SHEET_CHARS.sub("_", name)[:31]


def _table_exists(cx, schema, table):
    return cx.execute(text("SELECT OBJECT_ID(:t, 'U')"), {"t": f"{schema}.{table}"}).scalar() is not None


def generate_mapping_workbook(sf, target_object, output_path, engine, source_table, schema="dbo"):
    with engine.connect() as cx:
        source_cols = cx.execute(
            text(
                "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table ORDER BY ORDINAL_POSITION"
            ),
            {"schema": schema, "table": source_table},
        ).mappings().all()

        if not source_cols:
            raise ValueError(f"No such table: {schema}.{source_table}")

        profile_by_field = {}
        if _table_exists(cx, schema, "FieldProfile"):
            profile_rows = cx.execute(
                text(
                    f"SELECT FieldName, TotalRows, PopulatedCount, PopulatedPct "
                    f"FROM [{schema}].[FieldProfile] "
                    "WHERE ObjectOrTable = :table AND SourceType = 'sql_table'"
                ),
                {"table": source_table},
            ).mappings().all()
            profile_by_field = {r["FieldName"]: r for r in profile_rows}

    sheet_name = _safe_sheet_name(target_object)
    if os.path.exists(output_path):
        wb = openpyxl.load_workbook(output_path)
        if sheet_name in wb.sheetnames:
            del wb[sheet_name]
    else:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

    ws = wb.create_sheet(sheet_name)
    ws.cell(row=1, column=1, value="Source Object:")
    ws.cell(row=1, column=2, value=source_table)
    ws.cell(row=1, column=3, value="Target Object:")
    ws.cell(row=1, column=4, value=target_object)

    for col_idx, header in enumerate(_HEADERS, start=1):
        if header is not None:
            ws.cell(row=3, column=col_idx, value=header)

    row_idx = 4
    for col in source_cols:
        name = col["COLUMN_NAME"]
        profile = profile_by_field.get(name)
        ws.cell(row=row_idx, column=1, value=source_table)
        ws.cell(row=row_idx, column=2, value=name)
        ws.cell(row=row_idx, column=4, value=col["DATA_TYPE"])
        if profile:
            ws.cell(row=row_idx, column=6, value=f"{profile['PopulatedCount']} of {profile['TotalRows']}")
            pct = profile["PopulatedPct"]
            ws.cell(row=row_idx, column=7, value=float(pct) if pct is not None else None)
        row_idx += 1

    wb.save(output_path)
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


def check_mapping_balance(sf, mapping_path, object_name, transform_sql_path, load_table_name=None):
    wb = openpyxl.load_workbook(mapping_path, data_only=True)
    sheet_name = _safe_sheet_name(object_name)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"No sheet named '{sheet_name}' in {mapping_path}")
    ws = wb[sheet_name]

    documented = set()
    for row in ws.iter_rows(min_row=4):
        value = row[_TARGET_FIELD_API_COL - 1].value
        if value is not None and str(value).strip():
            documented.add(str(value).strip())

    with open(transform_sql_path, encoding="utf-8") as fh:
        sql_text = fh.read()

    implemented_cols = extract_insert_columns(sql_text, load_table_name)
    if implemented_cols is None:
        raise ValueError(f"No INSERT INTO statement found in {transform_sql_path}")
    implemented = set(implemented_cols)

    # Unlike the mapping doc (free text) and the transform's INSERT list
    # (whatever the SQL author typed), describe() is ground truth for what
    # fields actually exist on the target object -- cross-check both sets
    # against it so a typo'd/removed/never-deployed field name gets flagged
    # explicitly, rather than only showing up as an ordinary imbalance.
    real_fields = {f["name"] for f in getattr(sf, object_name).describe()["fields"]}
    not_real_field = (documented | implemented) - real_fields

    # A field that isn't real at all is the more urgent finding -- report it
    # there only, not also as an ordinary documented/implemented imbalance.
    documented -= not_real_field
    implemented -= not_real_field

    return {
        "documented_not_implemented": sorted(documented - implemented),
        "implemented_not_documented": sorted(implemented - documented),
        "not_a_real_field": sorted(not_real_field),
    }
