"""Coverage for pass_summary.py (roadmap #66) -- built on a real
Migration Run Book tab (migration_run_book.py) synced from a real
bulk_op() run, same "real engine, real write path" philosophy as
test_bulkops_sqlite_integration.py.
"""
import pandas as pd
import pytest

import bulkops as bo
import migration_run_book as mrb
import pass_summary as ps
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
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s), s


def _seed_load_order(engine, rows):
    pd.DataFrame(rows, columns=["ObjectName", "LoadLevel", "LoadSequence"]).to_sql(
        "ObjectLoadOrder", engine, schema="dbo", if_exists="replace", index=False
    )
    pd.DataFrame(columns=["ChildObject", "ParentObject"]).to_sql(
        "ObjectDependency", engine, schema="dbo", if_exists="replace", index=False
    )


def test_generate_pass_summary_clean_pass(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    _seed_load_order(engine, rows=[("Account", 0, 1)])
    output_path = str(tmp_path / "run_book.xlsx")
    mrb.generate_migration_run_book(
        output_path, "Dev1", engine=engine, object_names=["Account"], schema="dbo",
        project_name="Acme Migration", target_env="ACME_UAT",
    )

    bo.enable_bulkops_logging(engine, schema="dbo")
    df = pd.DataFrame({"LoadId": [1], "LegacyId__c": ["A1"], "Name": ["Row1"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler("LegacyId__c,Name,sf__Id\nA1,Row1,001X\n", ""))
    bo.bulk_op(sf, engine, "Account", "insert", "Account_Load",
               key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
               email_deliverability="no-access")
    mrb.sync_run_book_from_log(engine, output_path, "Dev1", schema="dbo")

    summary = ps.generate_pass_summary(output_path, "Dev1")
    assert "Acme Migration" in summary
    assert "ACME_UAT" in summary
    assert "1 object(s)" in summary
    assert "1 record(s)" in summary
    assert "No exceptions this pass." in summary
    assert "Known issues" not in summary


def test_generate_pass_summary_reports_failures_without_load_tables(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    _seed_load_order(engine, rows=[("Account", 0, 1)])
    output_path = str(tmp_path / "run_book.xlsx")
    mrb.generate_migration_run_book(output_path, "Dev1", engine=engine, object_names=["Account"], schema="dbo")

    bo.enable_bulkops_logging(engine, schema="dbo")
    df = pd.DataFrame({"LoadId": [1, 2], "LegacyId__c": ["A1", "A2"], "Name": ["Row1", "Row2"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"], fail_every_n=2))
    bo.bulk_op(sf, engine, "Account", "insert", "Account_Load",
               key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
               email_deliverability="no-access")
    mrb.sync_run_book_from_log(engine, output_path, "Dev1", schema="dbo")

    summary = ps.generate_pass_summary(output_path, "Dev1")
    assert "1 had exception(s)" in summary
    assert "Known issues" in summary
    assert "See the Migration Run Book's Notes/Error Details columns" in summary


def test_generate_pass_summary_enriches_with_triage_when_load_table_given(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    _seed_load_order(engine, rows=[("Account", 0, 1)])
    output_path = str(tmp_path / "run_book.xlsx")
    mrb.generate_migration_run_book(output_path, "Dev1", engine=engine, object_names=["Account"], schema="dbo")

    bo.enable_bulkops_logging(engine, schema="dbo")
    df = pd.DataFrame({"LoadId": [1, 2], "LegacyId__c": ["A1", "A2"], "Name": ["Row1", "Row2"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler(echo_cols=["LegacyId__c", "Name"], fail_every_n=2))
    bo.bulk_op(sf, engine, "Account", "insert", "Account_Load",
               key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
               email_deliverability="no-access")
    mrb.sync_run_book_from_log(engine, output_path, "Dev1", schema="dbo")

    # The Run Book's Object cell holds a real script filename (this repo
    # has a committed 010_account_load.sql), not the bare table name --
    # confirming load_tables must be an explicit mapping, never guessed.
    project, target_env, rows = ps._load_phase_summary_rows(output_path, "Dev1")
    object_cell = rows[0]["object"]

    summary = ps.generate_pass_summary(
        output_path, "Dev1", engine=engine, schema="dbo",
        load_tables={object_cell: "Account_Load"},
    )
    assert "DUPLICATE_VALUE" in summary


def test_generate_pass_summary_raises_when_tab_missing(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    _seed_load_order(engine, rows=[("Account", 0, 1)])
    output_path = str(tmp_path / "run_book.xlsx")
    mrb.generate_migration_run_book(output_path, "Dev1", engine=engine, object_names=["Account"], schema="dbo")

    with pytest.raises(ValueError, match="No tab named"):
        ps.generate_pass_summary(output_path, "DoesNotExist")
