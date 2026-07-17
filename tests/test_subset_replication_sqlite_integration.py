"""Integration coverage for subset_replication.py's real orchestration
(roadmap #34) against a real SQLite engine and a real Bulk-API-2.0-style
download path -- not just the pure WHERE-building logic already covered
by test_subset_replication.py. Uses StubBulkDownloadHandler (see
stub_salesforce.py) to give replicate.py's own read side real test
coverage for the first time, since it had none before this feature.
"""
import pytest
from sqlalchemy import text

import sql_client
import subset_replication as subrep
from config import Settings
from stub_salesforce import StubBulkDownloadHandler, StubSF

_ACCOUNT_FIELDS = [
    {"name": "Id", "type": "id", "nillable": False},
    {"name": "Name", "type": "string", "nillable": True},
]
_CONTACT_FIELDS = [
    {"name": "Id", "type": "id", "nillable": False},
    {"name": "AccountId", "type": "reference", "referenceTo": ["Account"],
     "relationshipOrder": None, "nillable": True},
]
_CAMPAIGN_FIELDS = [
    {"name": "Id", "type": "id", "nillable": False},
    {"name": "Name", "type": "string", "nillable": True},
]

_ACCOUNT_ROWS = [
    {"Id": "001A", "Name": "Acme"},
    {"Id": "001B", "Name": "Beta"},
    {"Id": "001C", "Name": "Gamma"},
]
_CONTACT_ROWS = [
    {"Id": "003c1", "AccountId": "001A"},
    {"Id": "003c2", "AccountId": "001A"},
    {"Id": "003c3", "AccountId": "001B"},
    {"Id": "003c4", "AccountId": "001C"},
]
_CAMPAIGN_ROWS = [
    {"Id": "701X", "Name": "Spring Appeal"},
    {"Id": "701Y", "Name": "Fall Gala"},
]


def _stub_sf(account_rows=None, contact_rows=None, campaign_rows=None):
    return StubSF(
        {"Account": _ACCOUNT_FIELDS, "Contact": _CONTACT_FIELDS, "Campaign": _CAMPAIGN_FIELDS},
        {
            "Account": StubBulkDownloadHandler(account_rows if account_rows is not None else _ACCOUNT_ROWS),
            "Contact": StubBulkDownloadHandler(contact_rows if contact_rows is not None else _CONTACT_ROWS),
            "Campaign": StubBulkDownloadHandler(campaign_rows if campaign_rows is not None else _CAMPAIGN_ROWS),
        },
    )


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(sql_backend="sqlite", sql_sqlite_dir=str(tmp_path / "_sqlite"), sql_sqlite_schemas="dbo")
    return sql_client.make_engine(s), s


def _fetch_all(engine, schema, table, column="Id"):
    # A fresh connection, not the one replicate_subset() used -- catches
    # an uncommitted-transaction bug the same way test_bulkops_sqlite_
    # integration.py's own read-back convention does.
    with engine.connect() as cx:
        rows = cx.execute(text(f'SELECT {column} FROM "{schema}"."{table}"')).fetchall()
    return {r[0] for r in rows}


def test_replicate_subset_root_limit_propagates_to_child(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    sf = _stub_sf()

    counts, notes = subrep.replicate_subset(
        sf, engine, "Account", ["Contact"], str(tmp_path / "_stage"),
        schema="dbo", limit=2, raw=True,
    )

    assert counts == {"Account": 2, "Contact": 3}
    assert notes == {}

    # Account subset is real order-preserved LIMIT 2 -- Acme + Beta, not Gamma.
    assert _fetch_all(engine, "dbo", "Account") == {"001A", "001B"}
    # Contact is constrained to rows whose AccountId is actually in that
    # subset -- c4 (AccountId=001C) must be excluded even though the stub
    # has it, since 001C was never replicated.
    assert _fetch_all(engine, "dbo", "Contact") == {"003c1", "003c2", "003c3"}


def test_replicate_subset_empty_parent_subset_skips_child_api_call(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    sf = _stub_sf()

    counts, notes = subrep.replicate_subset(
        sf, engine, "Account", ["Contact"], str(tmp_path / "_stage"),
        schema="dbo", where="Name = 'DoesNotExist'", raw=True,
    )

    assert counts == {"Account": 0, "Contact": 0}
    assert notes["Contact"] == "0 rows (parent subset empty)"
    assert _fetch_all(engine, "dbo", "Account") == set()
    assert _fetch_all(engine, "dbo", "Contact") == set()


def test_replicate_subset_unrelated_object_replicates_unconstrained(sqlite_engine, tmp_path):
    engine, _ = sqlite_engine
    sf = _stub_sf()

    counts, notes = subrep.replicate_subset(
        sf, engine, "Account", ["Campaign"], str(tmp_path / "_stage"),
        schema="dbo", limit=1, raw=True,
    )

    assert counts == {"Account": 1, "Campaign": 2}
    assert "no relationship constraint applied" in notes["Campaign"]
    # Campaign has no edge to Account at all -- both rows come through
    # untouched by the root's own --limit.
    assert _fetch_all(engine, "dbo", "Campaign") == {"701X", "701Y"}
