"""Integration coverage for load_order.py's write_to_sql()/
analyze_load_order() against a real SQLite engine -- previously untested
at all (found while building migration_brief.py, roadmap #59, which
calls analyze_load_order() directly and needed it real-SQLite-testable
in the first place, same as this session's other incremental
sql_dialect.py ports).
"""
import pandas as pd
import pytest

import load_order as lo
import sql_client
from config import Settings


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, describe_by_object):
        self._describe_by_object = describe_by_object

    def __getattr__(self, name):
        return _StubObjectDescribe(self._describe_by_object[name])


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s)


def test_analyze_load_order_writes_dependency_and_order_tables(sqlite_engine):
    sf = _StubSF({
        "Account": [{"name": "Id", "type": "id"}],
        "Contact": [
            {"name": "Id", "type": "id"},
            {"name": "AccountId", "type": "reference", "referenceTo": ["Account"], "nillable": True},
        ],
    })
    lo.analyze_load_order(sf, sqlite_engine, ["Account", "Contact"], schema="dbo")

    dep = pd.read_sql('SELECT * FROM "dbo"."ObjectDependency"', sqlite_engine)
    assert len(dep) == 1
    assert dep.iloc[0]["ChildObject"] == "Contact"
    assert dep.iloc[0]["ParentObject"] == "Account"

    order = pd.read_sql('SELECT * FROM "dbo"."ObjectLoadOrder"', sqlite_engine)
    by_name = order.set_index("ObjectName")
    assert by_name.loc["Account", "LoadLevel"] < by_name.loc["Contact", "LoadLevel"]


def test_analyze_load_order_second_call_drops_and_recreates(sqlite_engine):
    sf = _StubSF({"Account": [{"name": "Id", "type": "id"}]})
    lo.analyze_load_order(sf, sqlite_engine, ["Account"], schema="dbo")
    lo.analyze_load_order(sf, sqlite_engine, ["Account"], schema="dbo")

    order = pd.read_sql('SELECT * FROM "dbo"."ObjectLoadOrder"', sqlite_engine)
    assert len(order) == 1


def test_analyze_load_order_records_self_reference_not_a_dependency_edge(sqlite_engine):
    sf = _StubSF({
        "Account": [
            {"name": "Id", "type": "id"},
            {"name": "ParentId", "type": "reference", "referenceTo": ["Account"], "nillable": True},
        ],
    })
    lo.analyze_load_order(sf, sqlite_engine, ["Account"], schema="dbo")

    # The raw edge is still recorded in ObjectDependency (child == parent) --
    # it's compute_load_order() that treats it specially, tracking it as a
    # self-reference rather than letting it block topological order.
    dep = pd.read_sql('SELECT * FROM "dbo"."ObjectDependency"', sqlite_engine)
    assert len(dep) == 1
    assert dep.iloc[0]["ChildObject"] == dep.iloc[0]["ParentObject"] == "Account"

    order = pd.read_sql('SELECT * FROM "dbo"."ObjectLoadOrder"', sqlite_engine)
    assert bool(order.iloc[0]["HasSelfReference"]) is True
    assert order.iloc[0]["SelfReferenceFields"] == "ParentId"
