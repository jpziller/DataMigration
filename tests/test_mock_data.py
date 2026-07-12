"""Coverage for mock_data.py against a real SQLite engine -- previously
untested at all (found while building adversarial_mock_data.py, roadmap
#62, which reuses create_mock_table() directly and needed it ported off
raw T-SQL to be real-SQLite-testable in the first place).
"""
import pandas as pd
import pytest

import mock_data
import sql_client
from config import Settings

_ACCOUNT_FIELDS = [
    {"name": "Id", "type": "id", "createable": False, "updateable": False, "nillable": True},
    {"name": "Name", "type": "string", "createable": True, "updateable": True,
     "nillable": False, "defaultedOnCreate": False, "length": 80},
    {"name": "LegacyId__c", "type": "string", "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False, "length": 255},
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


@pytest.fixture(autouse=True)
def _stub_mockaroo(monkeypatch):
    def _fake_generate(schema, count, api_key):
        return [{f["name"]: f"Clean {f['name']}" for f in schema} for _ in range(count)]
    monkeypatch.setattr(mock_data, "generate_mock_data", _fake_generate)


def test_generate_mock_object_data_creates_table_on_sqlite(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    rows, skipped = mock_data.generate_mock_object_data(sf, sqlite_engine, "Account", 5, "fake-key", schema="dbo")
    assert rows == 5
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock"', sqlite_engine)
    assert len(df) == 5
    assert set(df.columns) == {"Name", "LegacyId__c"}  # Id is not createable -- excluded


def test_generate_mock_object_data_second_call_drops_and_recreates(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    mock_data.generate_mock_object_data(sf, sqlite_engine, "Account", 5, "fake-key", schema="dbo")
    mock_data.generate_mock_object_data(sf, sqlite_engine, "Account", 3, "fake-key", schema="dbo")
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock"', sqlite_engine)
    assert len(df) == 3
