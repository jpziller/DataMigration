"""Integration coverage for the pluggable SQL backend against a real
SQLite file -- promoted from a scratch verification script once proven
out manually (see the pluggable-SQL-backend plan). Every other test in
this suite is a pure-function/isolated test; this is the one place a real
engine gets exercised end to end, specifically to catch the class of bug
a pure unit test can't (an existence check that silently assumes the
wrong dialect, a writeback that doesn't actually commit, two schemas
bleeding into each other).
"""
import pandas as pd
import pytest

import bulkops as bo
import load_table_prep as ltp
import replicate as rep
import sql_client
from config import Settings

_FIELDS = [
    {"name": "Id", "type": "id", "length": 18, "createable": False, "updateable": False, "nillable": True},
    {"name": "Name", "type": "string", "length": 255, "createable": True, "updateable": True,
     "nillable": False, "defaultedOnCreate": False},
    {"name": "LegacyId__c", "type": "string", "length": 255, "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False},
]


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubBulk2:
    def __init__(self, handler):
        self._handler = handler

    def __getattr__(self, name):
        return self._handler


class _StubBulkHandler:
    def __init__(self, success_csv, failure_csv):
        self._success_csv = success_csv
        self._failure_csv = failure_csv

    def insert(self, csv_path, batch_size=None):
        return [{"job_id": "JOB1"}]

    def get_successful_records(self, job_id):
        return self._success_csv

    def get_failed_records(self, job_id):
        return self._failure_csv


class _StubSF:
    def __init__(self, fields, handler):
        self._fields = fields
        self.bulk2 = _StubBulk2(handler)

    def __getattr__(self, name):
        return _StubObjectDescribe(self._fields)


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

    sf = _StubSF(_FIELDS, _StubBulkHandler(
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

    sf = _StubSF(_FIELDS, _StubBulkHandler(
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
    sf = _StubSF(_FIELDS, _StubBulkHandler(
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
