"""Reference-record pull/compare tool (roadmap #51).

An architect sometimes hand-creates a record through the Salesforce UI --
to see how the org's real automation (validation rules, Flows, triggers)
actually shapes a record -- and hands over its Id for review. Nothing
diffs that live record against what this project's own load script would
have produced; today that's eyeballing two field lists side by side.

The Load table's own Id column (bulkops.py's bulk_op() writeback) only
ever gets populated for records actually loaded through bulkops -- a
hand-created reference record was never loaded, so it can't be matched by
Id. It CAN be matched by the migration key (e.g. Legacy_Id__c) if the
architect set that field when creating the record by hand -- read straight
off the live record rather than asking for the value separately.

Treat this purely as a review/debugging aid for fixing the SQL transform,
never as something this framework writes back to.
"""
from sqlalchemy import text


def _load_table_data_columns(engine, schema, load_table, key_column, id_column, error_column, ref_prefix):
    excluded = {key_column, id_column, error_column}
    with engine.connect() as cx:
        columns = cx.execute(
            text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table "
                "ORDER BY ORDINAL_POSITION"
            ),
            {"schema": schema, "table": load_table},
        ).mappings().all()

    if not columns:
        raise ValueError(f"No such table: {schema}.{load_table}")

    return [
        c["COLUMN_NAME"] for c in columns
        if c["COLUMN_NAME"] not in excluded
        and not c["COLUMN_NAME"].upper().startswith(ref_prefix.upper())
    ]


def compare_reference_record(sf, engine, object_name, load_table, record_id, migration_key_field,
                              schema="dbo", key_column="LoadId", id_column="Id", error_column="Error",
                              ref_prefix="REF_"):
    """Diff a live Salesforce record against the Load table row its
    migration_key_field value corresponds to. Returns {"migration_key_value",
    "fields": [{"field", "load_table_value", "live_value", "match"}, ...]}.

    Raises ValueError with a clear message if: a data column isn't a real
    field on object_name (typo/removed -- same describe()-driven pre-flight
    bulk_op() already does for writes, applied here to a read), the record
    doesn't exist, migration_key_field is blank on the live record, or no
    Load table row matches that value.

    ref_prefix (hard rule 13): a REF_-prefixed column is a human-only
    SQL-side audit field, same convention as bulk_op() -- excluded from
    the diff entirely rather than raising "not a real field" against it.
    """
    data_columns = _load_table_data_columns(engine, schema, load_table, key_column, id_column, error_column, ref_prefix)

    real_fields = {f["name"] for f in getattr(sf, object_name).describe()["fields"]}
    not_real = [c for c in data_columns + [migration_key_field] if c not in real_fields]
    if not_real:
        raise ValueError(
            f"Not a real field on {object_name} (typo, removed, or never deployed): {not_real}"
        )

    # Manual SOQL-literal escaping, same convention bulkops.py's
    # _resolve_external_ids_to_sf_id() uses -- simple_salesforce has no
    # bind-parameter API for SOQL, so literals interpolated into query text
    # are escaped by hand rather than left to chance.
    escaped_id = str(record_id).replace("\\", "\\\\").replace("'", "\\'")
    select_fields = ", ".join(dict.fromkeys([migration_key_field] + data_columns))
    live_records = sf.query(f"SELECT {select_fields} FROM {object_name} WHERE Id = '{escaped_id}'")["records"]
    if not live_records:
        raise ValueError(f"No {object_name} record found with Id '{record_id}'.")
    live = live_records[0]

    key_value = live.get(migration_key_field)
    if key_value in (None, ""):
        raise ValueError(
            f"This record has no {migration_key_field} value set -- can't match it to a "
            f"{load_table} row. Set {migration_key_field} on the hand-created record to the "
            "value it's meant to represent, then retry."
        )

    with engine.connect() as cx:
        cols_sql = ", ".join(f"[{c}]" for c in data_columns)
        load_row = cx.execute(
            text(f"SELECT {cols_sql} FROM [{schema}].[{load_table}] WHERE [{migration_key_field}] = :v"),
            {"v": key_value},
        ).mappings().first()
    if load_row is None:
        raise ValueError(
            f"No row in {schema}.{load_table} has {migration_key_field} = '{key_value}' -- "
            "can't compare against a load script result that doesn't exist."
        )

    def _norm(v):
        return None if v in (None, "") else str(v)

    fields = []
    for col in data_columns:
        load_value, live_value = _norm(load_row[col]), _norm(live.get(col))
        fields.append({
            "field": col, "load_table_value": load_value, "live_value": live_value,
            "match": load_value == live_value,
        })

    return {"migration_key_value": key_value, "fields": fields}
