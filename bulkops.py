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

PRE-FLIGHT CHECK (roadmap #1's "rebuild instead of port" -- a legacy
column/permission compare tool, rebuilt here as a live describe() check
rather than ported verbatim):
  Before ever calling the Bulk API, every sent column is checked against the
  target object's live describe(): does the field exist at all, and can this
  operation actually write it (createable for insert, updateable for
  update/upsert)? Either failure aborts before spending a real API call --
  Salesforce would reject the whole job or every row for the same reason,
  just after burning a batch and taking longer to find out. This is a schema/
  permission check only, not a data-content one (see
  sql/functions/utilities/CheckLoadTableDuplicateKeys.sql for that). A
  required-but-not-sent field on insert is reported as a warning, not a
  hard stop -- automation could still default it, so it isn't guaranteed to
  fail the way a missing/non-writable field is.

RETRY HELPER (build_retry_table):
  Copies only the failed rows (Error column populated) from a load table or
  its `_Result` table into a fresh `<table>_Retry` table, so a partial
  failure can be resubmitted via a normal `bulk_op()` call against just the
  rows that need it, instead of re-running (and re-charging batches for)
  the whole original load.

DELETE BY EXTERNAL ID:
  Bulk API 2.0's delete operation only ever accepts the real Salesforce Id
  column -- confirmed against Salesforce's own Bulk API 2.0 docs ("bulk
  deletion requests can include only the Id field"), unlike update/upsert,
  which do accept an external id via `externalIdFieldName`. So `delete`
  with `external_id` set doesn't send the external id to the API directly
  -- it resolves those values to real Ids via a SOQL query first
  (`_resolve_external_ids_to_sf_id`), then runs a normal Id-based delete
  against the resolved rows. A value with no matching org record is never
  submitted to the API at all (there's no Id to delete); it's reported
  back as a local "no matching record found" error on that row, the same
  writeback shape as any other failure, not silently dropped.

EMAIL DELIVERABILITY ATTESTATION (insert/upsert only):
  insert/upsert can create brand-new records that trigger outbound email to
  real external contacts (welcome emails, notifications, workflow-driven
  sends) -- see docs/MIGRATION_PLAYBOOK.md's "Email deliverability" note.
  Salesforce has no supported API to *read* the org's Email Deliverability
  setting (confirmed by retrieving EmailAdministrationSettings live against
  a real org and cross-checking Salesforce's own field reference -- neither
  has any such field; the only tool found that can even *set* it
  programmatically drives a headless browser against the Setup UI, which
  is exactly the kind of fragile screen-scraping this framework avoids).
  So this can't be a real automated check -- it's a required, explicit
  human attestation instead: `email_deliverability` must be passed for
  insert/upsert (`"no-access"`, `"system-email-only"`, or `"all-email"`,
  matching Setup's own three states), based on someone actually having
  looked at Setup > Email Administration > Deliverability first. Missing
  it raises and aborts before touching the API. `"all-email"` additionally
  requires `confirm_external_email_risk=True`, or it raises too --
  deliverability set to allow all email is the one state that can
  genuinely send real mail to real people, so it needs a deliberate
  override, not a default. The confirmed value is echoed back in the
  result dict either way, so it's visible in the load's own report.
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


def _resolve_external_ids_to_sf_id(sf, object_name, external_id_field, values, chunk_size=200):
    """Resolve external ID field values to real Salesforce Ids via SOQL --
    see this module's "DELETE BY EXTERNAL ID" docstring section for why
    this is necessary before a delete. Returns {value_as_str: sf_id}; a
    value with no matching org record is simply absent from the result."""
    resolved = {}
    unique_values = sorted({str(v) for v in values if v not in (None, "") and pd.notna(v)})
    for i in range(0, len(unique_values), chunk_size):
        chunk = unique_values[i:i + chunk_size]
        quoted = ", ".join("'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'" for v in chunk)
        soql = f"SELECT Id, {external_id_field} FROM {object_name} WHERE {external_id_field} IN ({quoted})"
        for rec in sf.query(soql).get("records", []):
            resolved[str(rec[external_id_field])] = rec["Id"]
    return resolved


def _preflight_check(sf, object_name, operation, sent_columns, id_column="Id"):
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}

    checked_columns = [c for c in sent_columns if c != id_column]
    not_real_field = [c for c in checked_columns if c not in fields_by_name]
    writable_columns = [c for c in checked_columns if c in fields_by_name]

    if operation == "insert":
        not_writable = [c for c in writable_columns if not fields_by_name[c].get("createable")]
    elif operation in ("update", "upsert"):
        not_writable = [c for c in writable_columns if not fields_by_name[c].get("updateable")]
    else:  # delete only ever sends id_column, already excluded above
        not_writable = []

    required_not_sent = []
    if operation == "insert":
        sent_set = set(sent_columns)
        for f in desc["fields"]:
            if (f.get("createable") and not f.get("nillable", True)
                    and not f.get("defaultedOnCreate") and f["name"] not in sent_set):
                required_not_sent.append(f["name"])

    return {
        "not_a_real_field": not_real_field,
        "not_writable": not_writable,
        "required_not_sent": required_not_sent,
    }


_DELIVERABILITY_LEVELS = ("no-access", "system-email-only", "all-email")


def _check_email_deliverability(operation, email_deliverability, confirm_external_email_risk):
    """See this module's "EMAIL DELIVERABILITY ATTESTATION" docstring
    section -- there is no supported API to read this setting, so this is
    a required human attestation, not an automated check. Returns a note
    string for the result dict, or None if not applicable to this op."""
    if operation not in ("insert", "upsert"):
        return None

    if email_deliverability is None:
        raise ValueError(
            "insert/upsert can create new records that trigger outbound email to real "
            "external contacts. Check Setup > Email Administration > Deliverability first, "
            "then pass --email-deliverability no-access|system-email-only|all-email. "
            "(There is no API to read this setting automatically -- see this module's "
            "docstring for why.)"
        )
    if email_deliverability not in _DELIVERABILITY_LEVELS:
        raise ValueError(f"Invalid email_deliverability value: {email_deliverability!r} "
                         f"(expected one of {_DELIVERABILITY_LEVELS})")
    if email_deliverability == "all-email" and not confirm_external_email_risk:
        raise ValueError(
            "Email Deliverability is set to 'All Email' -- this load could send real "
            "outbound email to external contacts. If that's genuinely intended, re-run "
            "with --confirm-external-email-risk. Otherwise, set Deliverability to "
            "'System Email Only' or 'No Access' in Setup first."
        )

    if email_deliverability == "all-email":
        return "All Email -- confirmed, external email risk explicitly accepted"
    return f"{email_deliverability} -- internal-only confirmed, continuing"


def bulk_op(sf, engine, object_name, operation, source_table,
            send_columns=None, external_id=None,
            key_column="LoadId", id_column="Id", error_column="Error",
            schema="dbo", stage_dir="_stage",
            email_deliverability=None, confirm_external_email_risk=False):
    operation = operation.lower()
    if operation not in ("insert", "update", "upsert", "delete"):
        raise ValueError(f"Unsupported operation: {operation}")

    deliverability_note = _check_email_deliverability(
        operation, email_deliverability, confirm_external_email_risk
    )

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

    # Delete-by-external-id: resolve to real Ids first (see this module's
    # "DELETE BY EXTERNAL ID" docstring section). skip_mask marks rows with
    # no matching org record -- they never reach the API, but still get a
    # clear, locally-generated error written back like any other failure.
    skip_mask = pd.Series(False, index=df.index)
    not_found_count = 0
    if operation == "delete" and external_id:
        if external_id not in df.columns:
            raise ValueError(f"Column {external_id} not in {source_table}")
        resolved = _resolve_external_ids_to_sf_id(sf, object_name, external_id, df[external_id])
        df[id_column] = df[external_id].astype(str).map(resolved)
        skip_mask = df[id_column].isna()
        not_found_count = int(skip_mask.sum())

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

    preflight = _preflight_check(sf, object_name, operation, sent, id_column=id_column)
    fatal_details = []
    if preflight["not_a_real_field"]:
        fatal_details.append(f"not a real field on {object_name}: {preflight['not_a_real_field']}")
    if preflight["not_writable"]:
        verb = "createable" if operation == "insert" else "updateable"
        fatal_details.append(f"not {verb} on {object_name}: {preflight['not_writable']}")
    if fatal_details:
        raise ValueError(
            f"Pre-flight check failed for {source_table} -> {object_name} ({operation}): "
            + "; ".join(fatal_details)
        )

    # Rows that failed external-id resolution never reach the API -- they
    # get a locally-generated error instead (see skip_mask above).
    submit_df = df[~skip_mask] if skip_mask.any() else df

    os.makedirs(stage_dir, exist_ok=True)
    csv_path = os.path.join(stage_dir, f"{source_table}_{operation}.csv")

    if submit_df.empty:
        successes, failures = pd.DataFrame(), pd.DataFrame()
        echo_cols = []
    else:
        payload = submit_df[sent].copy()
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

    df["_result_id"] = pd.Series(dtype=object, index=df.index)
    df["_result_error"] = pd.Series(dtype=object, index=df.index)
    if not submit_df.empty:
        submit_fp = _fingerprint(submit_df, echo_cols)
        df.loc[submit_df.index, "_result_id"] = submit_fp.map(id_by_fp)
        df.loc[submit_df.index, "_result_error"] = submit_fp.map(err_by_fp)
    if skip_mask.any():
        not_found_msg = f"No {object_name} record found with {external_id} matching this row's value"
        df.loc[skip_mask, "_result_error"] = not_found_msg

    n_ok = df["_result_id"].notna().sum()
    n_err = df["_result_error"].notna().sum()

    # Write results back. For delete-by-external-id, the result table should
    # still show the external id value a row was submitted for, even though
    # only the resolved Id was ever sent to the API -- otherwise a "no
    # matching record" row would be unreviewable (blank Id, no external id
    # either).
    report_columns = sent
    if operation == "delete" and external_id and external_id not in sent:
        report_columns = sent + [external_id]

    if key_column in df.columns:
        _writeback_inplace(engine, schema, source_table, df,
                           key_column, id_column, error_column)
        target = f"{schema}.{source_table}"
    else:
        target = _writeback_result_table(engine, schema, source_table, df,
                                          report_columns, id_column, error_column)

    return {
        "operation": operation,
        "object": object_name,
        "submitted": len(submit_df),
        "succeeded": int(n_ok),
        "failed": int(n_err),
        "ambiguous": ambiguous,
        "external_id_not_found": not_found_count,
        "written_to": target,
        "preflight_warnings": preflight["required_not_sent"],
        "email_deliverability": deliverability_note,
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


def build_retry_table(engine, table, schema="dbo", error_column="Error", retry_suffix="_Retry"):
    """Copy only the failed rows from `table` (a load table written back in
    place, or a `<table>_Result` table) into a fresh `<table>_Retry` table --
    for resubmission via a normal bulk_op() call against just what failed,
    not the whole original load. Never resubmits anything itself; that's a
    separate, explicit bulkops call against the returned table name."""
    with engine.connect() as cx:
        has_error_col = cx.execute(
            text("SELECT COL_LENGTH(:t, :c)"),
            {"t": f"{schema}.{table}", "c": error_column},
        ).scalar() is not None
    if not has_error_col:
        raise ValueError(
            f"{schema}.{table} has no [{error_column}] column -- has bulkops been run against it yet?"
        )

    retry_table = f"{table}{retry_suffix}"
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.{retry_table}', 'U') IS NOT NULL "
            f"DROP TABLE [{schema}].[{retry_table}];"
        ))
        cx.execute(text(
            f"SELECT * INTO [{schema}].[{retry_table}] "
            f"FROM [{schema}].[{table}] WHERE [{error_column}] IS NOT NULL;"
        ))
        count = cx.execute(text(f"SELECT COUNT(*) FROM [{schema}].[{retry_table}]")).scalar()
        if count == 0:
            # SELECT INTO creates the table even when the WHERE clause
            # matches nothing -- don't leave a stray empty table behind
            # just because a load had no failures to retry.
            cx.execute(text(f"DROP TABLE [{schema}].[{retry_table}];"))

    return f"{schema}.{retry_table}", count
