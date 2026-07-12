"""Coverage for dev_cycle.py (roadmap #63) against a real SQLite engine."""
import pandas as pd
import pytest

import dev_cycle as dc
import sql_client
import sql_dialect
from config import Settings
from stub_salesforce import StubSF, describe_fields


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s)


def _seed_table(engine, name):
    pd.DataFrame({"x": [1]}).to_sql(name, engine, schema="dbo", if_exists="replace", index=False)


def test_reset_dev_cycle_tables_drops_every_known_suffix(sqlite_engine):
    engine = sqlite_engine
    for suffix in dc._TABLE_SUFFIXES:
        _seed_table(engine, f"Account{suffix}")
    _seed_table(engine, "Account_Something_Unrelated")  # must NOT be touched

    result = dc.reset_dev_cycle_tables(engine, ["Account"], schema="dbo")
    assert len(result["dropped"]) == len(dc._TABLE_SUFFIXES)

    dialect = sql_dialect.for_engine(engine)
    for suffix in dc._TABLE_SUFFIXES:
        assert dialect.table_exists(engine, "dbo", f"Account{suffix}") is False
    assert dialect.table_exists(engine, "dbo", "Account_Something_Unrelated") is True


def test_reset_dev_cycle_tables_is_idempotent_when_nothing_exists(sqlite_engine):
    engine = sqlite_engine
    result = dc.reset_dev_cycle_tables(engine, ["Account"], schema="dbo")
    assert result == {"dropped": [], "profiling_cleared": []}


def test_reset_dev_cycle_tables_only_touches_named_objects(sqlite_engine):
    engine = sqlite_engine
    _seed_table(engine, "Account_Mock")
    _seed_table(engine, "Contact_Mock")

    result = dc.reset_dev_cycle_tables(engine, ["Account"], schema="dbo")
    assert result["dropped"] == ["dbo.Account_Mock"]

    dialect = sql_dialect.for_engine(engine)
    assert dialect.table_exists(engine, "dbo", "Contact_Mock") is True


def test_reset_dev_cycle_tables_clears_matching_profiling_rows_only(sqlite_engine):
    engine = sqlite_engine
    pd.DataFrame([
        {"ObjectOrTable": "Account", "SourceType": "salesforce", "FieldName": "Name",
         "TotalRows": 10, "PopulatedCount": 10, "PopulatedPct": 100.0},
        {"ObjectOrTable": "Contact", "SourceType": "salesforce", "FieldName": "Name",
         "TotalRows": 5, "PopulatedCount": 5, "PopulatedPct": 100.0},
    ]).to_sql("FieldProfile", engine, schema="dbo", if_exists="replace", index=False)
    pd.DataFrame([
        {"ObjectOrTable": "Account", "SourceType": "salesforce", "FieldName": "Name",
         "Value": "Acme", "Occurrences": 1},
        {"ObjectOrTable": "Contact", "SourceType": "salesforce", "FieldName": "Name",
         "Value": "Bob", "Occurrences": 1},
    ]).to_sql("FieldProfileValues", engine, schema="dbo", if_exists="replace", index=False)

    result = dc.reset_dev_cycle_tables(engine, ["Account"], schema="dbo")
    assert result["profiling_cleared"] == ["Account"]

    remaining = pd.read_sql('SELECT * FROM "dbo"."FieldProfile"', engine)
    assert list(remaining["ObjectOrTable"]) == ["Contact"]
    remaining_values = pd.read_sql('SELECT * FROM "dbo"."FieldProfileValues"', engine)
    assert list(remaining_values["ObjectOrTable"]) == ["Contact"]


def test_reset_dev_cycle_tables_leaves_org_metadata_caches_untouched(sqlite_engine):
    engine = sqlite_engine
    pd.DataFrame([{"ObjectName": "Account", "CheckType": "ValidationRule", "ItemName": "Rule1",
                    "IsActive": 1, "DirectHit": 0, "Detail": None, "AnalyzedDate": "2026-07-12"}]).to_sql(
        "ObjectAutomationRisk", engine, schema="dbo", if_exists="replace", index=False
    )
    _seed_table(engine, "Account_Mock")

    dc.reset_dev_cycle_tables(engine, ["Account"], schema="dbo")

    remaining = pd.read_sql('SELECT * FROM "dbo"."ObjectAutomationRisk"', engine)
    assert len(remaining) == 1


def test_purge_org_test_data_dry_run_touches_nothing(sqlite_engine):
    engine = sqlite_engine
    fields = describe_fields(["LegacyId__c"])
    sf = StubSF({"Account": fields}, {"Account": None})
    sf.query_all_iter = lambda soql: iter([{"Id": "001000000000001"}, {"Id": "001000000000002"}])

    result = dc.purge_org_test_data(sf, engine, "Account", "AccountNumber LIKE 'MOCKACCT-%'", schema="dbo", dry_run=True)
    assert result["matched"] == 2
    assert result["operation"] == "delete (dry run)"

    dialect = sql_dialect.for_engine(engine)
    assert dialect.table_exists(engine, "dbo", "Account_Purge") is False


def test_purge_org_test_data_requires_where_clause(sqlite_engine):
    engine = sqlite_engine
    sf = StubSF({"Account": describe_fields(["LegacyId__c"])}, {"Account": None})
    with pytest.raises(ValueError, match="non-empty WHERE clause"):
        dc.purge_org_test_data(sf, engine, "Account", "", schema="dbo")
