"""Coverage for readiness.py (roadmap #65) against a real SQLite engine."""
import openpyxl
import pandas as pd
import pytest

import readiness as rd
import sql_client
import sql_dialect
from config import Settings

_ACCOUNT_FIELDS = [
    {"name": "Id", "type": "id", "createable": False, "updateable": False, "nillable": True},
    {"name": "Name", "type": "string", "createable": True, "updateable": True, "nillable": False, "length": 80},
    {"name": "MigrationID__c", "type": "string", "createable": True, "updateable": True,
     "nillable": True, "length": 40, "externalId": True, "unique": True},
    {"name": "NotExternalId__c", "type": "string", "createable": True, "updateable": True,
     "nillable": True, "length": 40, "externalId": False, "unique": False},
]


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, object_name, fields):
        setattr(self, object_name, _StubObjectDescribe(fields))


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s)


def _seed_object_dependency(engine, edges):
    pd.DataFrame(edges, columns=["ChildObject", "ParentObject"]).to_sql(
        "ObjectDependency", engine, schema="dbo", if_exists="replace", index=False
    )


# --- Parent-Batch Sort Rule gate ---

def test_sort_gate_not_applicable_without_object_dependency_table(sqlite_engine):
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Account", "Account_Load")
    assert result["ok"] is None
    assert "analyze-load-order" in result["detail"]


def test_sort_gate_not_applicable_when_no_parent(sqlite_engine):
    _seed_object_dependency(sqlite_engine, [])
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Account", "Account_Load")
    assert result["ok"] is None
    assert "No parent in scope" in result["detail"]


def test_sort_gate_fails_when_parent_exists_but_no_sort_column(sqlite_engine):
    _seed_object_dependency(sqlite_engine, [("Contact", "Account")])
    pd.DataFrame({"LoadId": [1]}).to_sql("Contact_Load", sqlite_engine, schema="dbo", index=False)
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Contact", "Contact_Load")
    assert result["ok"] is False


def test_sort_gate_passes_when_sort_column_present(sqlite_engine):
    _seed_object_dependency(sqlite_engine, [("Contact", "Account")])
    pd.DataFrame({"LoadId": [1], "Sort": [1]}).to_sql("Contact_Load", sqlite_engine, schema="dbo", index=False)
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Contact", "Contact_Load")
    assert result["ok"] is True


def test_sort_gate_not_applicable_when_only_self_reference_edges(sqlite_engine):
    # Found via a real dogfood run: analyze-load-order records Account's
    # own self-reference edges (ParentId/MasterRecordId, both
    # Account -> Account) in ObjectDependency -- these are two-pass-load
    # fields (load_order.py's own self_references tracking), never a real
    # cross-object parent to batch against, so an object with ONLY
    # self-reference edges must still report "No parent in scope," not a
    # false Sort-column failure.
    _seed_object_dependency(sqlite_engine, [("Account", "Account"), ("Account", "Account")])
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Account", "Account_Load")
    assert result["ok"] is None
    assert "No parent in scope" in result["detail"]


def test_sort_gate_ignores_self_reference_when_a_real_parent_also_exists(sqlite_engine):
    _seed_object_dependency(sqlite_engine, [("Contact", "Contact"), ("Contact", "Account")])
    pd.DataFrame({"LoadId": [1]}).to_sql("Contact_Load", sqlite_engine, schema="dbo", index=False)
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._sort_column_gate(sqlite_engine, d, "dbo", "Contact", "Contact_Load")
    assert result["ok"] is False  # a real parent (Account) is still in scope


# --- Migration Key Integrity gate ---

def test_duplicate_key_gate_not_checked_without_migration_key(sqlite_engine):
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._duplicate_key_gate(sqlite_engine, d, "dbo", "Account_Load", None)
    assert result["ok"] is None


def test_duplicate_key_gate_fails_on_real_duplicate(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2], "MigrationID__c": ["A1", "A1"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._duplicate_key_gate(sqlite_engine, d, "dbo", "Account_Load", "MigrationID__c")
    assert result["ok"] is False


def test_duplicate_key_gate_passes_when_clean(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2], "MigrationID__c": ["A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._duplicate_key_gate(sqlite_engine, d, "dbo", "Account_Load", "MigrationID__c")
    assert result["ok"] is True


def test_duplicate_key_gate_fails_cleanly_on_nonexistent_column_not_a_crash(sqlite_engine):
    """Found in review: check_load_table_duplicate_keys() now raises for
    a migration-key column that doesn't exist -- this gate must report
    that as an explicit failure, not let it crash the whole multi-object
    readiness assessment."""
    pd.DataFrame({"LoadId": [1, 2], "RealField": ["A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._duplicate_key_gate(sqlite_engine, d, "dbo", "Account_Load", "NonexistentField__c")
    assert result["ok"] is False
    assert "not a column" in result["detail"]


# --- Live Migration Key Validation gate ---

def test_external_id_gate_not_checked_without_migration_key():
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd._external_id_gate(sf, "Account", None)
    assert result["ok"] is None


def test_external_id_gate_fails_when_field_not_flagged():
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd._external_id_gate(sf, "Account", "NotExternalId__c")
    assert result["ok"] is False


def test_external_id_gate_passes_when_flagged_correctly():
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd._external_id_gate(sf, "Account", "MigrationID__c")
    assert result["ok"] is True


# --- analyze-org-risk scan coverage gate ---

def test_org_risk_gate_fails_when_table_missing(sqlite_engine):
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._org_risk_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is False


def test_org_risk_gate_fails_when_never_scanned(sqlite_engine):
    pd.DataFrame([{"ObjectName": "Contact", "CheckType": "ValidationRule", "ItemName": "x"}]).to_sql(
        "ObjectAutomationRisk", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._org_risk_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is False


def test_org_risk_gate_passes_when_scanned(sqlite_engine):
    pd.DataFrame([{"ObjectName": "Account", "CheckType": "ScanCompleted", "ItemName": "x"}]).to_sql(
        "ObjectAutomationRisk", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._org_risk_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is True


# --- check-mapping-balance gate ---

def test_mapping_balance_gate_not_checked_without_mapping_path():
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd._mapping_balance_gate(sf, None, "Account", "Account_Load")
    assert result["ok"] is None


def test_mapping_balance_gate_reports_bad_mapping_path_cleanly_not_a_crash():
    """Found in review: openpyxl.load_workbook() raises FileNotFoundError
    for a bad --mapping-path, not ValueError -- this used to crash the
    whole multi-object assess_migration_readiness() call over one bad
    path, the same bug class already fixed in pass_summary.py. Uses the
    real Account transform script this repo already has under
    sql/transformations/, so script_numbering.script_filename_for()
    actually finds one and the code reaches the mapping-path open."""
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd._mapping_balance_gate(sf, "/does/not/exist.xlsx", "Account", "Account_Load")
    assert result["ok"] is None
    assert "No such file" in result["detail"] or "cannot find" in result["detail"].lower()


# --- Email Deliverability attestation gate ---

def test_email_gate_not_checked_without_bulkopslog(sqlite_engine):
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._email_deliverability_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is None


def test_email_gate_not_applicable_for_delete_operation(sqlite_engine):
    pd.DataFrame([{"LogId": 1, "ObjectName": "Account", "Operation": "delete", "EmailDeliverability": None}]).to_sql(
        "BulkOpsLog", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._email_deliverability_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is None
    assert "delete" in result["detail"]


def test_email_gate_passes_when_attested(sqlite_engine):
    pd.DataFrame([{"LogId": 1, "ObjectName": "Account", "Operation": "insert", "EmailDeliverability": "no-access"}]).to_sql(
        "BulkOpsLog", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._email_deliverability_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is True


def test_email_gate_fails_when_not_attested(sqlite_engine):
    pd.DataFrame([{"LogId": 1, "ObjectName": "Account", "Operation": "insert", "EmailDeliverability": None}]).to_sql(
        "BulkOpsLog", sqlite_engine, schema="dbo", index=False
    )
    d = sql_dialect.for_engine(sqlite_engine)
    result = rd._email_deliverability_gate(sqlite_engine, d, "dbo", "Account")
    assert result["ok"] is False


# --- Full aggregate ---

def test_assess_migration_readiness_ready_when_no_explicit_failures(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd.assess_migration_readiness(sf, sqlite_engine, ["Account"], schema="dbo")[0]
    # org_risk_scanned is the one gate that's an explicit False with zero
    # setup at all (ObjectAutomationRisk never scanned) -- everything else
    # is "not checked" (None) with no other args given.
    assert result["blocking"] == ["org_risk_scanned"]
    assert result["ready"] is False


def test_assess_migration_readiness_ready_true_when_org_risk_scanned(sqlite_engine):
    pd.DataFrame([{"ObjectName": "Account", "CheckType": "ScanCompleted", "ItemName": "x"}]).to_sql(
        "ObjectAutomationRisk", sqlite_engine, schema="dbo", index=False
    )
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd.assess_migration_readiness(sf, sqlite_engine, ["Account"], schema="dbo")[0]
    assert result["ready"] is True
    assert result["blocking"] == []


def test_assess_migration_readiness_ready_true_for_a_clean_first_ever_load(sqlite_engine):
    """Found in review: a Load table that exists but has never been
    through bulkops (the normal, expected state right before a first
    pass -- exactly when this command is meant to be run) used to
    report NOT READY purely because of that, via the row-count-
    reconciliation gate blindly treating every reconciliation flag as
    blocking. "Never loaded yet" must not itself block readiness."""
    pd.DataFrame([{"ObjectName": "Account", "CheckType": "ScanCompleted", "ItemName": "x"}]).to_sql(
        "ObjectAutomationRisk", sqlite_engine, schema="dbo", index=False
    )
    pd.DataFrame({"LoadId": [1, 2], "MigrationID__c": ["A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd.assess_migration_readiness(sf, sqlite_engine, ["Account"], schema="dbo")[0]
    assert result["gates"]["row_count_reconciliation"]["ok"] is True
    assert result["ready"] is True
    assert result["blocking"] == []


def test_assess_migration_readiness_uses_migration_keys_and_load_tables(sqlite_engine):
    pd.DataFrame([{"ObjectName": "Account", "CheckType": "ScanCompleted", "ItemName": "x"}]).to_sql(
        "ObjectAutomationRisk", sqlite_engine, schema="dbo", index=False
    )
    pd.DataFrame({"LoadId": [1, 2], "MigrationID__c": ["A1", "A1"]}).to_sql(
        "Account_LoadV2", sqlite_engine, schema="dbo", index=False
    )
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    result = rd.assess_migration_readiness(
        sf, sqlite_engine, ["Account"], schema="dbo",
        migration_keys={"Account": "MigrationID__c"},
        load_tables={"Account": "Account_LoadV2"},
    )[0]
    assert result["load_table"] == "Account_LoadV2"
    assert result["gates"]["migration_key_integrity"]["ok"] is False
    assert result["gates"]["live_migration_key_validation"]["ok"] is True
    assert "migration_key_integrity" in result["blocking"]
    assert result["ready"] is False
