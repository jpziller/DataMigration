"""Coverage for migration_brief.py (roadmap #59) against a real SQLite
engine, using a stub that raises SalesforceResourceNotFound for an
object that doesn't exist -- the real exception bootstrap_project()
catches, not a generic error.
"""
import openpyxl
import pandas as pd
import pytest
from simple_salesforce.exceptions import SalesforceResourceNotFound

import migration_brief as mb
import sql_client
from config import Settings


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    """Raises SalesforceResourceNotFound for any object not in
    describe_by_object -- the real exception a live org raises for a
    typo'd/nonexistent object name."""
    def __init__(self, describe_by_object):
        self._describe_by_object = describe_by_object

    def __getattr__(self, name):
        if name not in self._describe_by_object:
            raise SalesforceResourceNotFound("404", {}, name, {})
        return _StubObjectDescribe(self._describe_by_object[name])


_MINIMAL_FIELDS = [{"name": "Id", "type": "id", "createable": False, "updateable": False, "nillable": True}]


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s)


def _write_brief(tmp_path, body):
    path = tmp_path / "brief.yaml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_parse_migration_brief_reads_full_shape(tmp_path):
    path = _write_brief(tmp_path, """
project: Acme Migration
ticket: PROJ-123
target_org_alias: ACME_UAT
objects:
  - name: Account
    notes: Primary records
  - name: Contact
""")
    brief = mb.parse_migration_brief(path)
    assert brief["project"] == "Acme Migration"
    assert brief["ticket"] == "PROJ-123"
    assert brief["target_org_alias"] == "ACME_UAT"
    assert brief["objects"] == [
        {"name": "Account", "notes": "Primary records"},
        {"name": "Contact", "notes": None},
    ]


def test_parse_migration_brief_accepts_plain_string_object_entries(tmp_path):
    path = _write_brief(tmp_path, "objects:\n  - Account\n  - Contact\n")
    brief = mb.parse_migration_brief(path)
    assert brief["objects"] == [{"name": "Account", "notes": None}, {"name": "Contact", "notes": None}]


def test_parse_migration_brief_raises_when_no_objects(tmp_path):
    path = _write_brief(tmp_path, "project: Acme Migration\n")
    with pytest.raises(ValueError, match="no 'objects' list"):
        mb.parse_migration_brief(path)


def test_parse_migration_brief_raises_on_invalid_object_entry(tmp_path):
    path = _write_brief(tmp_path, "objects:\n  - 42\n")
    with pytest.raises(ValueError, match="Invalid object entry"):
        mb.parse_migration_brief(path)


def test_bootstrap_project_confirms_objects_and_flags_typo(sqlite_engine, tmp_path):
    path = _write_brief(tmp_path, "objects:\n  - Account\n  - Accountt\n")
    sf = _StubSF({"Account": _MINIMAL_FIELDS})
    run_book_path = str(tmp_path / "run_book.xlsx")

    result = mb.bootstrap_project(sf, sqlite_engine, path, run_book_path, "Dev1", schema="dbo")

    assert result["valid_objects"] == ["Account"]
    assert len(result["problems"]) == 1
    assert "Accountt" in result["problems"][0]
    assert result["run_book_path"] == run_book_path

    wb = openpyxl.load_workbook(run_book_path)
    assert "Dev1" in wb.sheetnames


def test_confirm_objects_exist_reports_dunder_style_name_as_a_problem_not_a_crash():
    """Found in review: getattr() on a name colliding with a real Python
    attribute (e.g. "__class__") never even reaches
    SalesforceResourceNotFound -- simple_salesforce's own __getattr__ is
    only a fallback after normal attribute lookup succeeds, so the
    result has no .describe() and raises AttributeError instead. Must be
    reported as an ordinary problem, not crash the whole bootstrap."""
    sf = _StubSF({"Account": _MINIMAL_FIELDS})
    valid, problems = mb._confirm_objects_exist(sf, ["Account", "__class__"])
    assert valid == ["Account"]
    assert len(problems) == 1
    assert "__class__" in problems[0]


def test_confirm_objects_exist_reports_non_string_name_as_a_problem_not_a_crash():
    sf = _StubSF({"Account": _MINIMAL_FIELDS})
    valid, problems = mb._confirm_objects_exist(sf, ["Account", 123])
    assert valid == ["Account"]
    assert len(problems) == 1


def test_bootstrap_project_runs_load_order_and_scaffolds_run_book(sqlite_engine, tmp_path):
    path = _write_brief(tmp_path, "project: Acme Migration\nobjects:\n  - Account\n  - Contact\n")
    sf = _StubSF({"Account": _MINIMAL_FIELDS, "Contact": _MINIMAL_FIELDS})
    run_book_path = str(tmp_path / "run_book.xlsx")

    result = mb.bootstrap_project(sf, sqlite_engine, path, run_book_path, "Dev1", schema="dbo")

    assert result["valid_objects"] == ["Account", "Contact"]
    assert result["load_order"] is not None
    order_rows = pd.read_sql('SELECT * FROM "dbo"."ObjectLoadOrder"', sqlite_engine)
    assert set(order_rows["ObjectName"]) == {"Account", "Contact"}


def test_bootstrap_project_skips_load_order_and_run_book_when_nothing_valid(sqlite_engine, tmp_path):
    path = _write_brief(tmp_path, "objects:\n  - NotReal\n")
    sf = _StubSF({})
    run_book_path = str(tmp_path / "run_book.xlsx")

    result = mb.bootstrap_project(sf, sqlite_engine, path, run_book_path, "Dev1", schema="dbo")

    assert result["valid_objects"] == []
    assert result["load_order"] is None
    assert result["run_book_path"] is None
    import os
    assert not os.path.exists(run_book_path)


def test_bootstrap_project_warns_on_org_alias_mismatch(sqlite_engine, tmp_path):
    path = _write_brief(tmp_path, "target_org_alias: ACME_UAT\nobjects:\n  - Account\n")
    sf = _StubSF({"Account": _MINIMAL_FIELDS})
    run_book_path = str(tmp_path / "run_book.xlsx")

    result = mb.bootstrap_project(
        sf, sqlite_engine, path, run_book_path, "Dev1", schema="dbo",
        configured_org_alias="DEV_SANDBOX",
    )
    assert result["org_alias_warning"] is not None
    assert "ACME_UAT" in result["org_alias_warning"]
    assert "DEV_SANDBOX" in result["org_alias_warning"]


def test_bootstrap_project_no_warning_when_alias_matches(sqlite_engine, tmp_path):
    path = _write_brief(tmp_path, "target_org_alias: ACME_UAT\nobjects:\n  - Account\n")
    sf = _StubSF({"Account": _MINIMAL_FIELDS})
    run_book_path = str(tmp_path / "run_book.xlsx")

    result = mb.bootstrap_project(
        sf, sqlite_engine, path, run_book_path, "Dev1", schema="dbo",
        configured_org_alias="ACME_UAT",
    )
    assert result["org_alias_warning"] is None
