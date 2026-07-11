"""Integration coverage for the pluggable SQL backend against a real
SQLite file -- promoted from a scratch verification script once proven
out manually (see the pluggable-SQL-backend plan). Every other test in
this suite is a pure-function/isolated test; this is the one place a real
engine gets exercised end to end, specifically to catch the class of bug
a pure unit test can't (an existence check that silently assumes the
wrong dialect, a writeback that doesn't actually commit, two schemas
bleeding into each other).
"""
import json

import pandas as pd
import pytest

import bulkops as bo
import load_table_prep as ltp
import replicate as rep
import sql_client
from config import Settings
from stub_salesforce import StubBulkHandler, StubSF, describe_fields

_FIELDS = describe_fields(["Name", "LegacyId__c"])


def _stub_sf(handler):
    return StubSF({"Account": _FIELDS}, {"Account": handler})


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo,staging",
    )
    return sql_client.make_engine(s), s


def test_create_table_replicate_bulk_op_writeback_roundtrip(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine

    rep.create_table(engine, "Account", {"fields": _FIELDS}, schema="dbo")

    df = pd.DataFrame({
        "LoadId": [1, 2, 3],
        "LegacyId__c": ["A1", "A2", "A3"],
        "Name": ["Row1", "Row2", "Row3"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = _stub_sf(StubBulkHandler(
        "LegacyId__c,Name,sf__Id\nA1,Row1,001XXXXXXXXXXXAAA\nA3,Row3,001XXXXXXXXXXXCCC\n",
        "LegacyId__c,Name,sf__Error\nA2,Row2,SOME_ERROR:deliberately failed for this test\n",
    ))

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["succeeded"] == 2
    assert summary["failed"] == 1

    # Read back via a FRESH engine/connection -- catches an accidental
    # uncommitted-transaction bug that reading through the same connection
    # would mask.
    fresh_engine = sql_client.make_engine(Settings(
        sql_backend="sqlite", sql_sqlite_dir=str(tmp_path / "_sqlite"), sql_sqlite_schemas="dbo,staging",
    ))
    result = pd.read_sql('SELECT * FROM "dbo"."Account_Load" ORDER BY LoadId', fresh_engine)
    assert result.loc[result["LegacyId__c"] == "A1", "Id"].iloc[0] == "001XXXXXXXXXXXAAA"
    assert result.loc[result["LegacyId__c"] == "A3", "Id"].iloc[0] == "001XXXXXXXXXXXCCC"
    assert result.loc[result["LegacyId__c"] == "A2", "Error"].iloc[0] == "SOME_ERROR:deliberately failed for this test"
    assert pd.isna(result.loc[result["LegacyId__c"] == "A2", "Id"].iloc[0])


def test_build_retry_table_captures_only_failed_rows(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3],
        "LegacyId__c": ["A1", "A2", "A3"],
        "Name": ["Row1", "Row2", "Row3"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = _stub_sf(StubBulkHandler(
        "LegacyId__c,Name,sf__Id\nA1,Row1,001XXXXXXXXXXXAAA\nA3,Row3,001XXXXXXXXXXXCCC\n",
        "LegacyId__c,Name,sf__Error\nA2,Row2,SOME_ERROR:deliberately failed for this test\n",
    ))
    bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )

    retry_table_name, retry_count = bo.build_retry_table(engine, "Account_Load", schema="dbo")
    assert retry_table_name == "dbo.Account_Load_Retry"
    assert retry_count == 1
    retry_df = pd.read_sql('SELECT * FROM "dbo"."Account_Load_Retry"', engine)
    assert list(retry_df["LegacyId__c"]) == ["A2"]


def test_two_schema_logging_isolation(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    assert bo._bulkops_log_table_exists(engine, "dbo") is True
    assert bo._bulkops_log_table_exists(engine, "staging") is False

    df = pd.DataFrame({"LoadId": [1], "LegacyId__c": ["B1"], "Name": ["RowB1"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler(
        "LegacyId__c,Name,sf__Id\nB1,RowB1,001XXXXXXXXXXXDDD\n", ""
    ))
    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["logged"] is True

    log_rows = pd.read_sql('SELECT * FROM "dbo"."BulkOpsLog"', engine)
    assert len(log_rows) == 1
    assert log_rows.iloc[0]["RecordsSucceeded"] == 1


def test_add_bulk_load_sort_column_groups_contiguous_by_parent(sqlite_engine):
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3, 4, 5],
        "AccountId": ["P1", "P2", "P1", "P2", "P1"],
        "Name": ["C1", "C2", "C3", "C4", "C5"],
    })
    df.to_sql("Contact_Load", engine, schema="dbo", if_exists="replace", index=False)

    bad_ranges = ltp.add_bulk_load_sort_column(engine, "Contact_Load", "AccountId", schema="dbo")
    assert bad_ranges == []

    result = pd.read_sql('SELECT * FROM "dbo"."Contact_Load" ORDER BY LoadId', engine)
    assert result["Sort"].notna().all()
    p1_sorts = sorted(result.loc[result["AccountId"] == "P1", "Sort"])
    p2_sorts = sorted(result.loc[result["AccountId"] == "P2", "Sort"])
    assert p1_sorts == [p1_sorts[0], p1_sorts[0] + 1, p1_sorts[0] + 2]
    assert p2_sorts == [p2_sorts[0], p2_sorts[0] + 1]


def test_check_load_table_duplicate_keys_flags_dupes_and_missing(sqlite_engine):
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3, 4],
        "Migrated_Id__c": ["X1", "X1", None, "X2"],
    })
    df.to_sql("Account_Load2", engine, schema="dbo", if_exists="replace", index=False)

    duplicates, missing = ltp.check_load_table_duplicate_keys(engine, "Account_Load2", "Migrated_Id__c", schema="dbo")
    assert duplicates == [{"DuplicateKey": "X1", "Occurrences": 2}]
    assert missing == 1


def test_bulk_op_excludes_sort_and_key_column_from_sent_payload(sqlite_engine, tmp_path):
    """Regression test for the bug found via the Snowfakery volume run:
    bulk_op() previously sent [Sort] (hard rule 6) and, on update/upsert,
    key_column to Salesforce -- both are local/framework-only auxiliary
    columns, never real fields, and would fail _preflight_check() with
    "not a real field" the moment a load table actually had a Sort column."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3],
        "LegacyId__c": ["A1", "A2", "A3"],
        "Name": ["Row1", "Row2", "Row3"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    bad_ranges = ltp.add_bulk_load_sort_column(engine, "Account_Load", "LegacyId__c", schema="dbo")
    assert bad_ranges == []

    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"]))
    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["succeeded"] == 3
    assert summary["failed"] == 0


def test_bulk_op_excludes_sort_column_case_insensitively(sqlite_engine, tmp_path):
    """The Sort exclusion is matched case-insensitively, same as ref_prefix
    -- a differently-cased Sort-like column (never produced by
    add_bulk_load_sort_column() itself, but not guaranteed never to exist
    by some other route) must not silently reintroduce the bug above."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2],
        "LegacyId__c": ["A1", "A2"],
        "Name": ["Row1", "Row2"],
        "sort": [1, 2],  # lowercase, unlike add_bulk_load_sort_column()'s own "Sort"
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"]))
    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0


def test_bulk_op_update_excludes_key_column_but_still_sends_id(sqlite_engine, tmp_path):
    """The key_column exclusion gap was specific to update/upsert (insert
    already excluded it correctly) -- a separate regression test since
    it's a distinct code branch from the insert test above. Id must still
    be sent on update (Salesforce needs it to identify the record); only
    the local LoadId tracking column must not be."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2],
        "Id": ["001000000000000001", "001000000000000002"],
        "Name": ["Row1Updated", "Row2Updated"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = _stub_sf(StubBulkHandler(echo_cols=["Id", "Name"]))
    summary = bo.bulk_op(
        sf, engine, "Account", "update", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
    )
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0


def test_bulk_op_aggregates_successes_and_failures_across_multiple_jobs(sqlite_engine, tmp_path):
    """bulk_op() concatenates success/failure records across every job a
    real Bulk API submission can split into (see its own docstring's
    RESULT MAPPING section) -- nothing in this repo exercised that loop
    with more than one job until now. 6 rows, split into 2 jobs of 3, with
    one failure per job (rows 3 and 6), confirms the aggregation genuinely
    spans job boundaries rather than only ever seeing job 1."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3, 4, 5, 6],
        "LegacyId__c": [f"A{n}" for n in range(1, 7)],
        "Name": [f"Row{n}" for n in range(1, 7)],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = StubSF(
        {"Account": _FIELDS},
        {"Account": StubBulkHandler(
            echo_cols=["LegacyId__c", "Name"], job_count=2, fail_every_n=3,
        )},
    )

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["submitted"] == 6
    assert summary["succeeded"] == 4
    assert summary["failed"] == 2
    assert summary["ambiguous"] == 0

    result = pd.read_sql('SELECT * FROM "dbo"."Account_Load" ORDER BY LoadId', engine)
    # Row 3 (job 1's 3rd row) and row 6 (job 2's 3rd row) failed -- both
    # jobs' failures must show up, not just whichever job is processed first.
    assert result.loc[result["LegacyId__c"] == "A3", "Error"].notna().iloc[0]
    assert result.loc[result["LegacyId__c"] == "A6", "Error"].notna().iloc[0]
    succeeded = result.loc[result["Error"].isna(), "LegacyId__c"].tolist()
    assert sorted(succeeded) == ["A1", "A2", "A4", "A5"]
    assert result.loc[result["LegacyId__c"] == "A1", "Id"].notna().iloc[0]


def test_bulk_op_default_fingerprint_breaks_when_salesforce_reformats_a_sent_column(sqlite_engine, tmp_path):
    """Regression test for a real bug found via a live migration run: Bulk
    API 2.0 echoed a sent datetime "2024-04-23T09:56:37+00:00" back as
    "2024-04-23T09:56:37.000Z" -- same instant, different string. Since
    the default fingerprint joins every sent column, that one reformatted
    column broke matching for the WHOLE row -- confirmed here with a
    minimal repro: fingerprinting by all sent columns (the default) fails
    to match even though the "returned" data is for the exact same row."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1],
        "LegacyId__c": ["A1"],
        "SomeDate": ["2024-04-23T09:56:37+00:00"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    fields = describe_fields(["LegacyId__c", "SomeDate"])
    sf = StubSF({"Account": fields}, {"Account": StubBulkHandler(
        # Salesforce echoes SomeDate back reformatted -- everything else matches.
        "LegacyId__c,SomeDate,sf__Id\nA1,2024-04-23T09:56:37.000Z,001XXXXXXXXXXXAAA\n", "",
    )})

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    # The bug: neither succeeded nor failed -- the fingerprint just never matches.
    assert summary["succeeded"] == 0
    assert summary["failed"] == 0


def test_bulk_op_fingerprint_columns_fixes_the_reformatted_column_case(sqlite_engine, tmp_path):
    """Same scenario as the test above, but passing fingerprint_columns to
    restrict matching to the migration key alone -- the fix."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1],
        "LegacyId__c": ["A1"],
        "SomeDate": ["2024-04-23T09:56:37+00:00"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    fields = describe_fields(["LegacyId__c", "SomeDate"])
    sf = StubSF({"Account": fields}, {"Account": StubBulkHandler(
        "LegacyId__c,SomeDate,sf__Id\nA1,2024-04-23T09:56:37.000Z,001XXXXXXXXXXXAAA\n", "",
    )})

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
        fingerprint_columns=["LegacyId__c"],
    )
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0


def test_bulk_op_fingerprint_columns_rejects_column_not_in_sent(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    df = pd.DataFrame({"LoadId": [1], "LegacyId__c": ["A1"], "Name": ["Row1"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler("LegacyId__c,Name,sf__Id\nA1,Row1,001X\n", ""))

    with pytest.raises(ValueError, match="fingerprint_columns must be a subset"):
        bo.bulk_op(
            sf, engine, "Account", "insert", "Account_Load",
            key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
            email_deliverability="no-access",
            fingerprint_columns=["NotSentColumn"],
        )


def test_bulk_op_summary_includes_failure_error_counts(sqlite_engine, tmp_path):
    """New for orchestrator.py's assess_tier() (roadmap #53): the summary
    dict must surface distinct failure error messages and their counts,
    not just the aggregate failed count -- previously only visible in the
    writeback table."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3, 4],
        "LegacyId__c": ["A1", "A2", "A3", "A4"],
        "Name": ["Row1", "Row2", "Row3", "Row4"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"], fail_every_n=2))

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["failed"] == 2
    assert summary["failure_error_counts"] == {
        "DUPLICATE_VALUE:deliberately failed for this test": 2
    }


def test_bulk_op_failure_error_counts_groups_distinct_messages_separately(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3],
        "LegacyId__c": ["A1", "A2", "A3"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    fields = describe_fields(["LegacyId__c"])
    fail_csv = (
        "LegacyId__c,sf__Error\n"
        "A1,FIRST_ERROR:bad thing one\n"
        "A2,SECOND_ERROR:bad thing two\n"
        "A3,FIRST_ERROR:bad thing one\n"
    )
    sf = StubSF({"Account": fields}, {"Account": StubBulkHandler("", fail_csv)})

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["failed"] == 3
    assert summary["failure_error_counts"] == {
        "FIRST_ERROR:bad thing one": 2,
        "SECOND_ERROR:bad thing two": 1,
    }


def test_bulk_op_failure_error_counts_normalizes_embedded_record_ids(sqlite_engine, tmp_path):
    """Two DUPLICATE_VALUE errors that differ only in which record's real
    Id they collided with must count as the SAME signature, not two
    separate "novel" ones -- otherwise orchestrator.py's known-vs-novel
    check would almost never see a recurring error as known (found in
    review: the raw, unnormalized message embeds per-row-specific data)."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2, 3],
        "LegacyId__c": ["A1", "A2", "A3"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    fields = describe_fields(["LegacyId__c"])
    fail_csv = (
        "LegacyId__c,sf__Error\n"
        "A1,DUPLICATE_VALUE:duplicate value found: record with id: 001XX000003DHPbYAO\n"
        "A2,DUPLICATE_VALUE:duplicate value found: record with id: 001XX000003DHQcYAO\n"
        "A3,SOME_OTHER_ERROR:unrelated\n"
    )
    sf = StubSF({"Account": fields}, {"Account": StubBulkHandler("", fail_csv)})

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["failed"] == 3
    assert summary["failure_error_counts"] == {
        "DUPLICATE_VALUE:duplicate value found: record with id: <ID>": 2,
        "SOME_OTHER_ERROR:unrelated": 1,
    }


def test_bulk_op_handles_result_frames_with_asymmetric_echoed_columns(sqlite_engine, tmp_path):
    """The success-records CSV and failed-records CSV don't always echo
    back the exact same set of sent columns (found in review) -- here the
    success file echoes Name but the failure file doesn't. echo_cols must
    only include columns present in BOTH non-empty result frames, or
    fingerprinting the frame missing a column raises KeyError after the
    real Salesforce write already happened."""
    engine, _ = sqlite_engine
    df = pd.DataFrame({
        "LoadId": [1, 2],
        "LegacyId__c": ["A1", "A2"],
        "Name": ["Row1", "Row2"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)

    success_csv = "LegacyId__c,Name,sf__Id\nA1,Row1,001XX000003DHPbYAO\n"
    failure_csv = "LegacyId__c,sf__Error\nA2,SOME_ERROR:no Name column echoed here\n"
    sf = _stub_sf(StubBulkHandler(success_csv, failure_csv))

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1


def test_bulk_op_failure_error_counts_empty_on_a_fully_clean_run(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    df = pd.DataFrame({"LoadId": [1], "LegacyId__c": ["A1"], "Name": ["Row1"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler("LegacyId__c,Name,sf__Id\nA1,Row1,001X\n", ""))

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["failed"] == 0
    assert summary["failure_error_counts"] == {}


def test_bulk_op_logs_failure_error_counts_as_json_into_bulkopslog(sqlite_engine, tmp_path):
    """failure_error_counts must round-trip through the real BulkOpsLog
    INSERT (JSON-serialized), not just live in bulk_op()'s in-memory
    return value -- orchestrator.py's history reading depends on this
    actually being persisted."""
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")

    df = pd.DataFrame({
        "LoadId": [1, 2],
        "LegacyId__c": ["A1", "A2"],
        "Name": ["Row1", "Row2"],
    })
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"], fail_every_n=2))

    summary = bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )
    assert summary["logged"] is True

    log_rows = pd.read_sql('SELECT * FROM "dbo"."BulkOpsLog"', engine)
    assert len(log_rows) == 1
    logged_counts = json.loads(log_rows.iloc[0]["FailureErrorCounts"])
    assert logged_counts == summary["failure_error_counts"]
