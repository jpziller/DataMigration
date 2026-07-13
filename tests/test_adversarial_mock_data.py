"""Coverage for adversarial_mock_data.py (roadmap #62) against a real
SQLite engine. Mockaroo's own HTTP call is stubbed out (monkeypatched)
rather than hit for real -- these tests exercise this module's own
schema validation and corruption logic, not Mockaroo's API.
"""
import pandas as pd
import pytest

import adversarial_mock_data as amd
import mock_data
import sql_client
from config import Settings

_ACCOUNT_FIELDS = [
    {"name": "Id", "type": "id", "createable": False, "updateable": False, "nillable": True},
    {"name": "Name", "type": "string", "createable": True, "updateable": True,
     "nillable": False, "defaultedOnCreate": False, "length": 80},
    {"name": "LegacyId__c", "type": "string", "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False, "length": 255},
    {"name": "Description", "type": "string", "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False, "length": 255},
    {"name": "Industry", "type": "picklist", "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False,
     "picklistValues": [{"value": "Technology", "active": True}, {"value": "Banking", "active": True}]},
    {"name": "ParentId", "type": "reference", "createable": True, "updateable": True,
     "nillable": True, "defaultedOnCreate": False},
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
    """Every test in this file gets a fake Mockaroo response -- clean
    happy-path values per field, one dict per requested row -- instead of
    a real HTTP call."""
    def _fake_generate(schema, count, api_key):
        row = {}
        for field in schema:
            if field["type"] == "Boolean":
                row[field["name"]] = True
            elif field["type"] == "Number":
                row[field["name"]] = 1
            elif field["type"] == "Custom List":
                row[field["name"]] = field["values"][0]
            else:
                row[field["name"]] = f"Clean {field['name']}"
        return [dict(row) for _ in range(count)]
    monkeypatch.setattr(mock_data, "generate_mock_data", _fake_generate)


def test_generate_adversarial_mock_data_requires_at_least_one_scenario(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="scenarios is empty"):
        amd.generate_adversarial_mock_data(sf, sqlite_engine, "Account", 10, "fake-key", {})


def test_generate_adversarial_mock_data_rejects_unknown_scenario(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="Unknown scenario"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 10, "fake-key",
            {"not_a_real_scenario": {"field": "Name", "rows": 2}},
        )


def test_generate_adversarial_mock_data_rejects_too_many_corrupt_rows(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="Requested"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 5, "fake-key",
            {"duplicate_key": {"field": "LegacyId__c", "rows": 10}},
        )


def test_generate_adversarial_mock_data_rejects_duplicate_key_with_fewer_than_2_rows_before_mockaroo_call(sqlite_engine, monkeypatch):
    """Found in review: this check used to live inside _corrupt_duplicate_key(),
    which only runs after generate_mock_data() already burned a real,
    rate-limited (200/day) Mockaroo request -- it must fail before that
    call, same as every other scenario's field-shape validation."""
    def _fail_if_called(schema, count, api_key):
        raise AssertionError("generate_mock_data() must not be called when duplicate_key's row count is invalid.")
    monkeypatch.setattr(mock_data, "generate_mock_data", _fail_if_called)

    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="duplicate_key needs at least 2 rows"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 5, "fake-key",
            {"duplicate_key": {"field": "LegacyId__c", "rows": 1}},
        )


def test_generate_adversarial_mock_data_rejects_non_required_field_for_missing_required(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="isn't actually required"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 10, "fake-key",
            {"missing_required": {"field": "Description", "rows": 2}},
        )


def test_generate_adversarial_mock_data_rejects_non_picklist_for_invalid_picklist(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="picklist/combobox"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 10, "fake-key",
            {"invalid_picklist": {"field": "Name", "rows": 2}},
        )


def test_generate_adversarial_mock_data_rejects_non_reference_for_bad_reference(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    with pytest.raises(ValueError, match="reference field"):
        amd.generate_adversarial_mock_data(
            sf, sqlite_engine, "Account", 10, "fake-key",
            {"bad_reference": {"field": "Name", "rows": 2}},
        )


def test_generate_adversarial_mock_data_duplicate_key(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    rows, summary, skipped = amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 10, "fake-key",
        {"duplicate_key": {"field": "LegacyId__c", "rows": 3}},
    )
    assert rows == 10
    assert summary == [{"scenario": "duplicate_key", "field": "LegacyId__c", "rows": 3}]

    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    tagged = df[df["REF_AdversarialScenario"] == "duplicate_key"]
    assert len(tagged) == 3
    assert tagged["LegacyId__c"].nunique() == 1
    untagged = df[df["REF_AdversarialScenario"].isna()]
    assert len(untagged) == 7


def test_generate_adversarial_mock_data_oversized_string_fits_in_ddl(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    rows, summary, skipped = amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 5, "fake-key",
        {"oversized_string": {"field": "Description", "rows": 2}},
    )
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    tagged = df[df["REF_AdversarialScenario"] == "oversized_string"]
    assert len(tagged) == 2
    # Real describe() length is 255 -- every corrupted value must exceed it.
    assert (tagged["Description"].str.len() > 255).all()


def test_generate_adversarial_mock_data_missing_required(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 5, "fake-key",
        {"missing_required": {"field": "Name", "rows": 2}},
    )
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    tagged = df[df["REF_AdversarialScenario"] == "missing_required"]
    assert len(tagged) == 2
    assert tagged["Name"].isna().all()


def test_generate_adversarial_mock_data_invalid_picklist(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 5, "fake-key",
        {"invalid_picklist": {"field": "Industry", "rows": 2}},
    )
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    tagged = df[df["REF_AdversarialScenario"] == "invalid_picklist"]
    assert (tagged["Industry"] == "NOT_A_REAL_PICKLIST_VALUE_ZZZ").all()
    untagged = df[df["REF_AdversarialScenario"].isna()]
    assert set(untagged["Industry"]) <= {"Technology", "Banking"}


def test_generate_adversarial_mock_data_bad_reference(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 5, "fake-key",
        {"bad_reference": {"field": "ParentId", "rows": 2}},
    )
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    tagged = df[df["REF_AdversarialScenario"] == "bad_reference"]
    assert len(tagged) == 2
    assert tagged["ParentId"].str.len().eq(18).all()
    # Untouched rows get NULL, not a fabricated Id -- ParentId was never
    # part of the normal happy-path schema to begin with.
    untagged = df[df["REF_AdversarialScenario"].isna()]
    assert untagged["ParentId"].isna().all()


def test_generate_adversarial_mock_data_multiple_disjoint_scenarios(sqlite_engine):
    sf = _StubSF("Account", _ACCOUNT_FIELDS)
    rows, summary, skipped = amd.generate_adversarial_mock_data(
        sf, sqlite_engine, "Account", 10, "fake-key",
        {
            "duplicate_key": {"field": "LegacyId__c", "rows": 2},
            "missing_required": {"field": "Name", "rows": 3},
        },
    )
    assert [s["scenario"] for s in summary] == ["duplicate_key", "missing_required"]
    df = pd.read_sql('SELECT * FROM "dbo"."Account_Mock_Adversarial"', sqlite_engine)
    assert (df["REF_AdversarialScenario"] == "duplicate_key").sum() == 2
    assert (df["REF_AdversarialScenario"] == "missing_required").sum() == 3
    assert df["REF_AdversarialScenario"].isna().sum() == 5
    # Rows are disjoint -- a duplicate_key row must not also be missing Name.
    dup_rows = df[df["REF_AdversarialScenario"] == "duplicate_key"]
    assert dup_rows["Name"].notna().all()


def test_fake_salesforce_id_stays_18_chars_past_1000_rows():
    """Found in review: the original format silently grew past 18 total
    characters once seq reached 1000, breaking the real-Id-shape
    invariant bulkops.py's own _SF_ID_TOKEN_RE (and any downstream
    consumer expecting a genuine 15/18-char Id) relies on."""
    assert len(amd._fake_salesforce_id(999)) == 18
    assert len(amd._fake_salesforce_id(1000)) == 18
    assert len(amd._fake_salesforce_id(999999)) == 18
