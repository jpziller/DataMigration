"""Integration coverage for load_table_prep.py (hard rules 6/7) against a
real PostgreSQL server -- mirrors test_load_table_prep.py's SQLite
coverage, plus the one case neither backend had a test for at all until
this file: a genuinely non-contiguous Sort range actually being reported
back correctly (the SQLite file only ever asserted the clean/empty case).
That gap is exactly why a real, live-tested bug shipped and went
unnoticed for a full round of fixes: both add_bulk_load_sort_column()'s
and check_load_table_duplicate_keys()'s verification queries used bare
SQL aliases (ParentKey/MinSort/.../DuplicateKey/Occurrences), which
Postgres lowercases in the result set -- cli.py's exact-case r['ParentKey']
read raised KeyError precisely when there was something real to report,
invisible to any test that only exercised the clean path. See
tests/conftest.py's postgres_engine fixture and ROADMAP.md #69.
"""
import pandas as pd
import pytest
from sqlalchemy import text

import load_table_prep as ltp
import sql_dialect


# --- check_load_table_duplicate_keys (hard rule 7) ---

def test_check_load_table_duplicate_keys_raises_on_nonexistent_column(postgres_engine):
    engine, _, schema = postgres_engine
    pd.DataFrame({"LoadId": [1, 2], "RealField": ["A1", "A2"]}).to_sql(
        "Account_Load", engine, schema=schema, index=False
    )
    with pytest.raises(ValueError, match="is not a column"):
        ltp.check_load_table_duplicate_keys(engine, "Account_Load", "NonexistentField__c", schema=schema)


def test_check_load_table_duplicate_keys_detects_real_duplicates(postgres_engine):
    engine, _, schema = postgres_engine
    pd.DataFrame({"LoadId": [1, 2, 3], "LegacyId__c": ["A1", "A1", "A2"]}).to_sql(
        "Account_Load", engine, schema=schema, index=False
    )
    duplicates, missing = ltp.check_load_table_duplicate_keys(engine, "Account_Load", "LegacyId__c", schema=schema)
    assert len(duplicates) == 1
    # Confirms the actual bug fix: on Postgres, a bare alias used to come
    # back lowercased ("duplicatekey"), so d["DuplicateKey"] raised
    # KeyError right here -- exactly the case this rule exists to catch.
    assert duplicates[0]["DuplicateKey"] == "A1"
    assert duplicates[0]["Occurrences"] == 2
    assert missing == 0


def test_check_load_table_duplicate_keys_clean(postgres_engine):
    engine, _, schema = postgres_engine
    pd.DataFrame({"LoadId": [1, 2], "LegacyId__c": ["A1", "A2"]}).to_sql(
        "Account_Load", engine, schema=schema, index=False
    )
    duplicates, missing = ltp.check_load_table_duplicate_keys(engine, "Account_Load", "LegacyId__c", schema=schema)
    assert duplicates == []
    assert missing == 0


# --- add_bulk_load_sort_column (hard rule 6) ---

def test_add_bulk_load_sort_column_raises_on_nonexistent_parent_column(postgres_engine):
    engine, _, schema = postgres_engine
    pd.DataFrame({"LoadId": [1, 2], "RealField": ["A1", "A2"]}).to_sql(
        "Contact_Load", engine, schema=schema, index=False
    )
    with pytest.raises(ValueError, match="is not a column"):
        ltp.add_bulk_load_sort_column(engine, "Contact_Load", "NonexistentParentId__c", schema=schema)


def test_add_bulk_load_sort_column_adds_column_and_numbers_rows(postgres_engine):
    engine, _, schema = postgres_engine
    pd.DataFrame({
        "LoadId": [1, 2, 3, 4],
        "AccountId__c": ["A1", "A1", "A2", "A2"],
    }).to_sql("Contact_Load", engine, schema=schema, index=False)

    non_contiguous = ltp.add_bulk_load_sort_column(engine, "Contact_Load", "AccountId__c", schema=schema)
    assert non_contiguous == []  # same-parent rows should land contiguously

    df = pd.read_sql(f'SELECT * FROM "{schema}"."Contact_Load" ORDER BY "LoadId"', engine)
    assert "Sort" in df.columns
    assert df["Sort"].notna().all()


def test_verification_query_reports_a_genuine_non_contiguous_range(postgres_engine):
    """add_bulk_load_sort_column() is self-correcting -- it recomputes
    Sort via ROW_NUMBER() OVER (ORDER BY parent_key) on every call, which
    by construction always groups a parent's rows together. So calling
    the function itself can never exercise its own "found a bad range"
    return path in a working implementation; that path exists purely as
    a defense against a bug in the recompute (or manual data corruption).
    To actually test it, seed Sort values with a genuine gap directly and
    run the exact same verification query add_bulk_load_sort_column()
    runs internally (see load_table_prep.py) -- this is precisely the
    path that raised KeyError on Postgres before the quoted-alias fix,
    since cli.py reads the returned dicts by these exact PascalCase keys."""
    engine, _, schema = postgres_engine
    pd.DataFrame({
        "LoadId": [1, 2, 3],
        "AccountId__c": ["A1", "A1", "A1"],
        "Sort": [1, 2, 50],  # a real gap: 3 rows spanning 49, not the expected 2
    }).to_sql("Contact_Load", engine, schema=schema, index=False)

    d = sql_dialect.for_engine(engine)
    qualified = d.qualify(schema, "Contact_Load")
    sort_col = d.quote_ident("Sort")
    parent_col = d.quote_ident("AccountId__c")
    row_count_col = d.quote_ident("RowCount")
    parent_key_col = d.quote_ident("ParentKey")
    min_sort_col = d.quote_ident("MinSort")
    max_sort_col = d.quote_ident("MaxSort")
    sort_span_col = d.quote_ident("SortSpan")
    with engine.connect() as cx:
        rows = cx.execute(text(f"""
            SELECT {parent_col} AS {parent_key_col},
                   MIN({sort_col}) AS {min_sort_col}, MAX({sort_col}) AS {max_sort_col}, COUNT(*) AS {row_count_col},
                   MAX({sort_col}) - MIN({sort_col}) AS {sort_span_col}
            FROM {qualified}
            GROUP BY {parent_col}
            HAVING MAX({sort_col}) - MIN({sort_col}) <> COUNT(*) - 1
        """)).mappings().all()
    bad_ranges = [dict(r) for r in rows]

    assert len(bad_ranges) == 1
    assert bad_ranges[0]["ParentKey"] == "A1"
    assert bad_ranges[0]["MinSort"] == 1
    assert bad_ranges[0]["MaxSort"] == 50
    assert bad_ranges[0]["RowCount"] == 3
    assert bad_ranges[0]["SortSpan"] == 49
