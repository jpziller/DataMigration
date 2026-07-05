"""Bulk load operations: SQL Server load table -> Salesforce.

Reads a SQL "load table", pushes insert / update / upsert / delete to
Salesforce via Bulk API 2.0, then writes the resulting Salesforce Id and Error
back into that table -- the full round trip a migration load needs.

RESULT MAPPING (the part everyone gets wrong):
  Bulk API 2.0 returns separate "successful" and "failed" record sets, each
  echoing the columns you submitted plus sf__Id / sf__Error. There is no
  guaranteed global row order across those two files, so we do NOT map by
  position. Instead we fingerprint each submitted row by the tuple of its sent
  business columns and join the results back on that fingerprint.

  -> update / upsert / delete already send Id (or an external id), so the
     fingerprint is unique and mapping is exact.
  -> insert has no Id yet. Include a UNIQUE migration-key column among the sent
     columns (mapped to a real SF text/external-id field, e.g. Legacy_Id__c) so
     the fingerprint is guaranteed unique. If two submitted rows are identical
     across every sent column, they are genuinely ambiguous and the second is
     reported in `ambiguous`.

Writeback target:
  If `key_column` exists in the load table, Id/Error are UPDATEd in place keyed
  on it. Otherwise a `<table>_Result` table is written instead (no in-place
  update possible without a stable local key).
"""
import io
import os

import pandas as pd
from sqlalchemy import text


def _read_result_csv(csv_text):
    if not csv_text or not csv_text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(csv_text), dtype=str,
                       keep_default_na=False, na_values=[""])


def _fingerprint(df, cols):
    return df[cols].astype(str).agg("\x1f".join, axis=1)


def bulk_op(sf, engine, object_name, operation, source_table,
            send_columns=None, external_id=None,
            key_column="LoadId", id_column="Id", error_column="Error",
            schema="dbo", stage_dir="_stage"):
    operation = operation.lower()
    if operation not in ("insert", "update", "upsert", "delete"):
        raise ValueError(f"Unsupported operation: {operation}")

    # If the load table carries a [Sort] column (see
    # sql/functions/utilities/AddBulkLoadSortColumn.sql), submit rows in that
    # order so parent/child rows land in the same Bulk API batch rather than
    # being scattered across batches that process concurrently and
    # lock-contend on a shared parent record.
    with engine.connect() as cx:
        has_sort_column = cx.execute(
            text("SELECT COL_LENGTH(:t, 'Sort')"),
            {"t": f"{schema}.{source_table}"},
        ).scalar() is not None
    order_by = " ORDER BY [Sort]" if has_sort_column else ""

    df = pd.read_sql(f"SELECT * FROM [{schema}].[{source_table}]{order_by}", engine)

    # Which columns get sent to Salesforce.
    if operation == "delete":
        sent = [id_column]
    elif operation == "insert":
        sent = send_columns or [
            c for c in df.columns
            if c not in (id_column, error_column, key_column)
        ]
    else:  # update / upsert
        sent = send_columns or [c for c in df.columns if c != error_column]

    missing = [c for c in sent if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not in {source_table}: {missing}")

    payload = df[sent].copy()
    os.makedirs(stage_dir, exist_ok=True)
    csv_path = os.path.join(stage_dir, f"{source_table}_{operation}.csv")
    payload.to_csv(csv_path, index=False)

    handler = getattr(sf.bulk2, object_name)
    if operation == "insert":
        results = handler.insert(csv_path)
    elif operation == "update":
        results = handler.update(csv_path)
    elif operation == "upsert":
        if not external_id:
            raise ValueError("upsert requires external_id")
        results = handler.upsert(csv_path, external_id)
    else:  # delete
        results = handler.delete(csv_path)

    # Collect per-job successful + failed records.
    succ_frames, fail_frames = [], []
    for job in results:
        job_id = job["job_id"]
        succ_frames.append(_read_result_csv(handler.get_successful_records(job_id)))
        fail_frames.append(_read_result_csv(handler.get_failed_records(job_id)))
    successes = pd.concat([f for f in succ_frames if not f.empty],
                          ignore_index=True) if any(not f.empty for f in succ_frames) else pd.DataFrame()
    failures = pd.concat([f for f in fail_frames if not f.empty],
                         ignore_index=True) if any(not f.empty for f in fail_frames) else pd.DataFrame()

    # Build fingerprint -> (Id, Error) using the sent business columns that are
    # echoed back in the result files.
    echo_cols = [c for c in sent if (
        (not successes.empty and c in successes.columns) or
        (not failures.empty and c in failures.columns)
    )]
    payload_fp = _fingerprint(payload, echo_cols)

    id_by_fp, err_by_fp, ambiguous = {}, {}, 0
    if not successes.empty:
        for fp, sid in zip(_fingerprint(successes, echo_cols),
                           successes.get("sf__Id", pd.Series(dtype=str))):
            if fp in id_by_fp:
                ambiguous += 1
            id_by_fp[fp] = sid
    if not failures.empty:
        for fp, serr in zip(_fingerprint(failures, echo_cols),
                            failures.get("sf__Error", pd.Series(dtype=str))):
            err_by_fp[fp] = serr

    df["_result_id"] = payload_fp.map(id_by_fp)
    df["_result_error"] = payload_fp.map(err_by_fp)

    n_ok = df["_result_id"].notna().sum()
    n_err = df["_result_error"].notna().sum()

    # Write results back.
    if key_column in df.columns:
        _writeback_inplace(engine, schema, source_table, df,
                           key_column, id_column, error_column)
        target = f"{schema}.{source_table}"
    else:
        target = _writeback_result_table(engine, schema, source_table, df,
                                          sent, id_column, error_column)

    return {
        "operation": operation,
        "object": object_name,
        "submitted": len(df),
        "succeeded": int(n_ok),
        "failed": int(n_err),
        "ambiguous": ambiguous,
        "written_to": target,
    }


def _writeback_inplace(engine, schema, table, df, key_column,
                       id_column, error_column):
    with engine.begin() as cx:
        for col in (id_column, error_column):
            cx.execute(text(
                f"IF COL_LENGTH('{schema}.{table}', '{col}') IS NULL "
                f"ALTER TABLE [{schema}].[{table}] ADD [{col}] NVARCHAR(MAX) NULL;"
            ))
        stmt = text(
            f"UPDATE [{schema}].[{table}] "
            f"SET [{id_column}] = :rid, [{error_column}] = :rerr "
            f"WHERE [{key_column}] = :k"
        )
        rows = [
            {"rid": r["_result_id"] if pd.notna(r["_result_id"]) else None,
             "rerr": r["_result_error"] if pd.notna(r["_result_error"]) else None,
             "k": r[key_column]}
            for _, r in df.iterrows()
        ]
        cx.execute(stmt, rows)


def _writeback_result_table(engine, schema, table, df, sent,
                            id_column, error_column):
    out = df[sent].copy()
    out[id_column] = df["_result_id"]
    out[error_column] = df["_result_error"]
    result_table = f"{table}_Result"
    out.to_sql(result_table, engine, schema=schema,
               if_exists="replace", index=False)
    return f"{schema}.{result_table}"
