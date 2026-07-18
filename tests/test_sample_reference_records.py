"""Coverage for sample_reference_records.py -- a stub covering the real
Salesforce calls (describe()/query()), since the shared StubSF in
stub_salesforce.py doesn't support query() (only describe()/bulk2()).
Same local-stub pattern test_discovery_checklist.py already established
for this exact gap.
"""
import pandas as pd
import pytest

import sample_reference_records as srr
import sql_client
from config import Settings


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, fields_by_object, records=None):
        self._fields_by_object = fields_by_object
        self._records = records or []
        self.last_soql = None

    def __getattr__(self, name):
        return _StubObjectDescribe(self._fields_by_object[name])

    def query(self, soql):
        self.last_soql = soql
        return {"records": self._records}


_FIELDS = [
    {"name": "Id", "type": "id", "label": "Id", "createable": False, "nillable": False, "defaultedOnCreate": False},
    {"name": "Name", "type": "string", "label": "Name", "createable": True, "nillable": False, "defaultedOnCreate": False},
    {"name": "Status__c", "type": "picklist", "label": "Status", "createable": True, "nillable": True, "defaultedOnCreate": False},
    {"name": "AutoNumber__c", "type": "string", "label": "Auto Number", "createable": False, "nillable": False, "defaultedOnCreate": True},
    {"name": "BillingAddress", "type": "address", "label": "Billing Address", "createable": True, "nillable": True, "defaultedOnCreate": False},
]


def _records(n, status_populated=True):
    return [
        {
            "Id": f"001{i:015d}",
            "Name": f"Record {i}",
            "Status__c": "Active" if status_populated else None,
            "AutoNumber__c": f"A-{i:04d}",
        }
        for i in range(n)
    ]


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(sql_backend="sqlite", sql_sqlite_dir=str(tmp_path / "_sqlite"), sql_sqlite_schemas="dbo")
    return sql_client.make_engine(s)


def test_sample_by_explicit_ids_builds_id_in_query():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(2))
    srr.sample_reference_records(sf, "Widget__c", record_ids=["001A", "001B"])
    assert "WHERE Id IN ('001A', '001B')" in sf.last_soql


def test_sample_by_where_builds_where_and_limit_query():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(2))
    srr.sample_reference_records(sf, "Widget__c", where="Status__c = 'Active'", limit=3)
    assert "WHERE Status__c = 'Active' LIMIT 3" in sf.last_soql


def test_sample_default_falls_back_to_recency():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(2))
    srr.sample_reference_records(sf, "Widget__c")
    assert "ORDER BY CreatedDate DESC LIMIT" in sf.last_soql


def test_compound_fields_excluded_from_select():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(1))
    srr.sample_reference_records(sf, "Widget__c", record_ids=["001A"])
    assert "BillingAddress" not in sf.last_soql
    assert "Name" in sf.last_soql


def test_populated_count_reflects_real_sample_data():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(4, status_populated=False))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a", "b", "c", "d"])
    by_field = {f["field"]: f for f in result["fields"]}
    assert by_field["Name"]["populated_count"] == 4
    assert "Status__c" not in by_field  # blank across every sample, excluded by default


def test_show_all_includes_fields_blank_across_every_sample():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(2, status_populated=False))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a", "b"], show_all=True)
    by_field = {f["field"]: f for f in result["fields"]}
    assert by_field["Status__c"]["populated_count"] == 0


def test_field_report_carries_describe_flags():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(1))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a"])
    name_field = next(f for f in result["fields"] if f["field"] == "Name")
    assert name_field["createable"] is True
    assert name_field["nillable"] is False
    assert name_field["defaulted_on_create"] is False
    auto_field = next(f for f in result["fields"] if f["field"] == "AutoNumber__c")
    assert auto_field["createable"] is False
    assert auto_field["defaulted_on_create"] is True


def test_sample_values_deduplicated_and_capped():
    records = [{"Id": "1", "Name": "Same"}, {"Id": "2", "Name": "Same"}, {"Id": "3", "Name": "Different"}]
    sf = _StubSF({"Widget__c": _FIELDS}, records=records)
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["1", "2", "3"])
    name_field = next(f for f in result["fields"] if f["field"] == "Name")
    assert name_field["sample_values"] == ["Same", "Different"]


def test_fields_sorted_by_populated_count_descending():
    records = [
        {"Id": "1", "Name": "A", "Status__c": "Active"},
        {"Id": "2", "Name": "B", "Status__c": None},
    ]
    sf = _StubSF({"Widget__c": _FIELDS}, records=records)
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["1", "2"])
    order = [f["field"] for f in result["fields"]]
    assert order.index("Name") < order.index("Status__c")


def test_automation_none_when_no_engine_given():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(1))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a"])
    assert result["automation"] is None


def test_automation_none_when_table_does_not_exist(sqlite_engine):
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(1))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a"], engine=sqlite_engine, schema="dbo")
    assert result["automation"] is None


def test_automation_summary_counts_only_active_checks(sqlite_engine):
    pd.DataFrame([
        {"ObjectName": "Widget__c", "CheckType": "ValidationRule", "ItemName": "Rule1",
         "IsActive": True, "DirectHit": False, "Detail": "x", "AnalyzedDate": "2026-01-01"},
        {"ObjectName": "Widget__c", "CheckType": "ValidationRule", "ItemName": "Rule2",
         "IsActive": False, "DirectHit": False, "Detail": "x", "AnalyzedDate": "2026-01-01"},
        {"ObjectName": "Widget__c", "CheckType": "ApexTrigger", "ItemName": "Trig1",
         "IsActive": True, "DirectHit": False, "Detail": "x", "AnalyzedDate": "2026-01-01"},
        {"ObjectName": "Other__c", "CheckType": "ValidationRule", "ItemName": "Rule3",
         "IsActive": True, "DirectHit": False, "Detail": "x", "AnalyzedDate": "2026-01-01"},
    ]).to_sql("ObjectAutomationRisk", sqlite_engine, schema="dbo", if_exists="replace", index=False)

    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(1))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["a"], engine=sqlite_engine, schema="dbo")
    assert result["automation"] == {"ValidationRule": 1, "ApexTrigger": 1}


def test_record_ids_reflects_what_was_actually_sampled():
    sf = _StubSF({"Widget__c": _FIELDS}, records=_records(2))
    result = srr.sample_reference_records(sf, "Widget__c", record_ids=["ignored-input-id"])
    assert result["record_ids"] == [r["Id"] for r in _records(2)]
    assert result["sample_size"] == 2
