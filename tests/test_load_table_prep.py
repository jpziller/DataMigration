"""Coverage for load_table_prep.py (hard rules 6/7) against a real
SQLite engine -- previously untested at all, found while building
readiness.py (roadmap #65) and discovering a real bug in both functions
here: SQLite silently treats a double-quoted identifier with no
matching column as a plain string literal instead of raising, so a
typo'd/wrong column name used to produce a misleading, non-crashing
wrong answer instead of a clear error.
"""
import pandas as pd
import pytest

import load_table_prep as ltp
import sql_client
from config import Settings


@pytest.fixture
def sqlite_engine(tmp_path):
    s = Settings(
        sql_backend="sqlite",
        sql_sqlite_dir=str(tmp_path / "_sqlite"),
        sql_sqlite_schemas="dbo",
    )
    return sql_client.make_engine(s)


# --- check_load_table_duplicate_keys (hard rule 7) ---

def test_check_load_table_duplicate_keys_raises_on_nonexistent_column(sqlite_engine):
    """The real bug found in review: without this check, SQLite's own
    quoted-identifier-falls-back-to-string-literal quirk made a
    typo'd/wrong key column silently report a fake duplicate (every row
    groups into the same constant) instead of a clear error."""
    pd.DataFrame({"LoadId": [1, 2], "RealField": ["A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    with pytest.raises(ValueError, match="is not a column"):
        ltp.check_load_table_duplicate_keys(sqlite_engine, "Account_Load", "NonexistentField__c", schema="dbo")


def test_check_load_table_duplicate_keys_detects_real_duplicates(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2, 3], "LegacyId__c": ["A1", "A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    duplicates, missing = ltp.check_load_table_duplicate_keys(sqlite_engine, "Account_Load", "LegacyId__c", schema="dbo")
    assert len(duplicates) == 1
    assert duplicates[0]["DuplicateKey"] == "A1"
    assert duplicates[0]["Occurrences"] == 2
    assert missing == 0


def test_check_load_table_duplicate_keys_detects_missing_values(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2], "LegacyId__c": ["A1", None]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    duplicates, missing = ltp.check_load_table_duplicate_keys(sqlite_engine, "Account_Load", "LegacyId__c", schema="dbo")
    assert duplicates == []
    assert missing == 1


def test_check_load_table_duplicate_keys_clean(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2], "LegacyId__c": ["A1", "A2"]}).to_sql(
        "Account_Load", sqlite_engine, schema="dbo", index=False
    )
    duplicates, missing = ltp.check_load_table_duplicate_keys(sqlite_engine, "Account_Load", "LegacyId__c", schema="dbo")
    assert duplicates == []
    assert missing == 0


# --- add_bulk_load_sort_column (hard rule 6) ---

def test_add_bulk_load_sort_column_raises_on_nonexistent_parent_column(sqlite_engine):
    pd.DataFrame({"LoadId": [1, 2], "RealField": ["A1", "A2"]}).to_sql(
        "Contact_Load", sqlite_engine, schema="dbo", index=False
    )
    with pytest.raises(ValueError, match="is not a column"):
        ltp.add_bulk_load_sort_column(sqlite_engine, "Contact_Load", "NonexistentParentId__c", schema="dbo")


def test_add_bulk_load_sort_column_adds_column_and_numbers_rows(sqlite_engine):
    pd.DataFrame({
        "LoadId": [1, 2, 3, 4],
        "AccountId__c": ["A1", "A1", "A2", "A2"],
    }).to_sql("Contact_Load", sqlite_engine, schema="dbo", index=False)

    non_contiguous = ltp.add_bulk_load_sort_column(sqlite_engine, "Contact_Load", "AccountId__c", schema="dbo")
    assert non_contiguous == []  # same-parent rows should land contiguously

    df = pd.read_sql('SELECT * FROM "dbo"."Contact_Load" ORDER BY LoadId', sqlite_engine)
    assert "Sort" in df.columns
    assert df["Sort"].notna().all()
