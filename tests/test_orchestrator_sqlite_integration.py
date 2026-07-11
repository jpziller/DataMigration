"""Integration coverage for orchestrator.py's database-touching half
against a real SQLite file -- previously untested at all (found in
review): every existing test in test_orchestrator.py only ever calls the
pure assess_tier() function with hand-built dicts. This file exercises
_read_bulkops_history, _has_automation_risk_data, assess_from_log,
enable/disable_orchestrator_logging, and log_run_event against real
BulkOpsLog/ObjectAutomationRisk/OrchestratorRunEvent tables, seeded via
the real bulk_op()/risk_analyzer.write_to_sql() write paths rather than
hand-inserted rows -- the same "real engine, real write path" philosophy
as test_bulkops_sqlite_integration.py.
"""
import pandas as pd
import pytest
from sqlalchemy import text

import bulkops as bo
import orchestrator as orch
import risk_analyzer as ra
import sql_client
import sql_dialect
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


def _run_clean_load(engine, tmp_path, load_id=1, legacy_id="A1"):
    df = pd.DataFrame({"LoadId": [load_id], "LegacyId__c": [legacy_id], "Name": [f"Row{load_id}"]})
    df.to_sql("Account_Load", engine, schema="dbo", if_exists="replace", index=False)
    sf = _stub_sf(StubBulkHandler(f"LegacyId__c,Name,sf__Id\n{legacy_id},Row{load_id},001X{load_id:03d}\n", ""))
    return bo.bulk_op(
        sf, engine, "Account", "insert", "Account_Load",
        key_column="LoadId", schema="dbo", stage_dir=str(tmp_path / "_stage"),
        email_deliverability="no-access",
    )


def _seed_clean_automation_scan(engine, object_name="Account"):
    """A scanned-and-clean analyze-org-risk result -- assess_tier() reads
    "no ObjectAutomationRisk rows at all" as a tier-3 trigger (design doc
    section 2), so a test asserting a clean tier-1 result must seed this
    first, same as a real project would run analyze-org-risk before its
    first bulkops call."""
    ra.write_to_sql(engine, [{
        "object": object_name, "validation_rules": [], "apex_triggers": [],
        "workflow_rules": [], "approval_processes": [], "record_triggered_flows": [],
    }], schema="dbo")


def test_assess_from_log_raises_when_bulkopslog_missing(sqlite_engine):
    engine, _ = sqlite_engine
    with pytest.raises(ValueError, match="enable-bulkops-logging"):
        orch.assess_from_log(engine, "Account")


def test_assess_from_log_raises_when_no_matching_row(sqlite_engine):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    with pytest.raises(ValueError, match="No BulkOpsLog row"):
        orch.assess_from_log(engine, "Account")


def test_assess_from_log_most_recent_row_and_tier1_on_clean_history(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    _seed_clean_automation_scan(engine)
    _run_clean_load(engine, tmp_path, load_id=1)

    log_id, result = orch.assess_from_log(engine, "Account")
    assert log_id == 1
    assert result["tier"] == 1
    # First-ever run for this object -- no prior history yet.
    assert result["coarse_approval_eligible"] is False


def test_assess_from_log_second_clean_run_is_coarse_approval_eligible(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    _seed_clean_automation_scan(engine)
    _run_clean_load(engine, tmp_path, load_id=1, legacy_id="A1")
    _run_clean_load(engine, tmp_path, load_id=2, legacy_id="A2")

    log_id, result = orch.assess_from_log(engine, "Account")
    assert log_id == 2
    assert result["tier"] == 1
    assert result["coarse_approval_eligible"] is True


def test_read_bulkops_history_excludes_rows_after_the_assessed_log_id(sqlite_engine, tmp_path):
    """The exact history-boundary bug found this session: a retroactive
    assessment of an OLDER row must never see a LATER run as if it were
    prior history. before_log_id must be a strict '<', not '!='."""
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    _run_clean_load(engine, tmp_path, load_id=1, legacy_id="A1")
    _run_clean_load(engine, tmp_path, load_id=2, legacy_id="A2")

    history = orch._read_bulkops_history(engine, "Account", schema="dbo", before_log_id=1)
    assert history == []

    history = orch._read_bulkops_history(engine, "Account", schema="dbo", before_log_id=2)
    assert len(history) == 1


def test_has_automation_risk_data_false_before_analyze_org_risk(sqlite_engine):
    engine, _ = sqlite_engine
    assert orch._has_automation_risk_data(engine, "Account", schema="dbo") is False


def test_has_automation_risk_data_true_after_clean_scan_via_scancompleted_marker(sqlite_engine):
    """A clean analyze-org-risk scan (zero automation found) must still
    register as "has data" -- this is exactly the ScanCompleted marker
    row risk_analyzer.py added this session to fix."""
    engine, _ = sqlite_engine
    ra.write_to_sql(engine, [{
        "object": "Account", "validation_rules": [], "apex_triggers": [],
        "workflow_rules": [], "approval_processes": [], "record_triggered_flows": [],
    }], schema="dbo")
    assert orch._has_automation_risk_data(engine, "Account", schema="dbo") is True


def test_enable_orchestrator_logging_then_log_run_event_writes_row(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    _seed_clean_automation_scan(engine)
    _run_clean_load(engine, tmp_path, load_id=1)
    orch.enable_orchestrator_logging(engine, schema="dbo")

    log_id, result = orch.assess_from_log(engine, "Account")
    logged = orch.log_run_event(engine, log_id, "Account", result, schema="dbo")
    assert logged is True

    rows = pd.read_sql('SELECT * FROM "dbo"."OrchestratorRunEvent"', engine)
    assert len(rows) == 1
    assert rows.iloc[0]["ObjectName"] == "Account"
    assert rows.iloc[0]["Tier"] == 1
    assert rows.iloc[0]["TierName"] == "Continue Silently"


def test_log_run_event_is_a_noop_when_logging_not_enabled(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    bo.enable_bulkops_logging(engine, schema="dbo")
    _run_clean_load(engine, tmp_path, load_id=1)

    log_id, result = orch.assess_from_log(engine, "Account")
    logged = orch.log_run_event(engine, log_id, "Account", result, schema="dbo")
    assert logged is False


def test_disable_orchestrator_logging_drops_table(sqlite_engine):
    engine, _ = sqlite_engine
    orch.enable_orchestrator_logging(engine, schema="dbo")
    assert orch._orchestrator_log_table_exists(engine, "dbo") is True
    orch.disable_orchestrator_logging(engine, schema="dbo")
    assert orch._orchestrator_log_table_exists(engine, "dbo") is False


def test_enable_orchestrator_logging_upgrades_existing_table_with_tiername(sqlite_engine):
    """Re-running enable_orchestrator_logging against a table that
    predates the TierName column must add it in place, not error or
    require disable+re-enable (same upgrade-in-place convention as
    enable_bulkops_logging)."""
    engine, _ = sqlite_engine
    dialect = sql_dialect.for_engine(engine)
    qualified = dialect.qualify("dbo", "OrchestratorRunEvent")
    with engine.begin() as cx:
        cx.execute(text(
            f"CREATE TABLE {qualified} ("
            "EventId INTEGER PRIMARY KEY AUTOINCREMENT, LogId INTEGER NOT NULL, "
            "ObjectName TEXT NOT NULL, Tier INTEGER NOT NULL, Reasons TEXT NOT NULL, "
            "Environment TEXT NOT NULL, AssessedAt TEXT NOT NULL, RunBy TEXT NULL"
            ");"
        ))
    assert dialect.column_exists(engine, "dbo", "OrchestratorRunEvent", "TierName") is False

    orch.enable_orchestrator_logging(engine, schema="dbo")
    assert dialect.column_exists(engine, "dbo", "OrchestratorRunEvent", "TierName") is True
