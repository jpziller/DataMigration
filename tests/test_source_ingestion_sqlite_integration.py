"""End-to-end coverage for source_ingestion.py's SQLite staging path
(import_directory() -> _run_script()'s chunked pandas read_csv/to_sql
branch) against a real SQLite file. This path was written and reasoned
through when the pluggable SQL backend was built, but -- unlike
replicate.py/bulkops.py/batch_advisor.py/load_table_prep.py/
snowfakery_data.py, all of which were live-verified against a real
SQLite file that same session -- it had never actually been executed
until this test.
"""
import os

import pandas as pd
import pytest

import source_ingestion as si
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


def _write_csv(csv_dir, filename, rows):
    os.makedirs(csv_dir, exist_ok=True)
    path = os.path.join(csv_dir, filename)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_import_directory_creates_and_loads_table_on_sqlite(sqlite_engine, tmp_path):
    csv_dir = str(tmp_path / "csvs")
    sql_dir = str(tmp_path / "sql")
    _write_csv(csv_dir, "SourceAccounts.csv", [
        {"Name": "Acme", "Legacy_Id": "A1", "Notes": ""},
        {"Name": "Globex", "Legacy_Id": "A2", "Notes": "VIP"},
    ])

    results = si.import_directory(sqlite_engine, csv_dir, sql_dir=sql_dir, schema="dbo", ticket="TEST-1")

    assert len(results) == 1
    assert results[0]["status"] == "created"
    assert results[0]["rows"] == 2

    df = pd.read_sql('SELECT * FROM "dbo"."SourceAccounts" ORDER BY Legacy_Id', sqlite_engine)
    assert list(df["Name"]) == ["Acme", "Globex"]
    # An empty CSV field must land as SQL NULL, not an empty string --
    # same "stage raw, KEEPNULLS-equivalent" semantics as the SQL Server
    # BULK INSERT path.
    assert pd.isna(df.loc[df["Legacy_Id"] == "A1", "Notes"].iloc[0])
    assert df.loc[df["Legacy_Id"] == "A2", "Notes"].iloc[0] == "VIP"

    # The generated script is a real, SQLite-flavored DDL-only .sql file.
    generated = [f for f in os.listdir(sql_dir) if f.endswith(".sql")]
    assert len(generated) == 1
    with open(os.path.join(sql_dir, generated[0]), encoding="utf-8") as fh:
        script_text = fh.read()
    assert 'CREATE TABLE "dbo"."SourceAccounts"' in script_text
    # No executable BULK INSERT statement (SQLite has no such SQL syntax) --
    # the doc comment mentions BULK INSERT descriptively, so check for the
    # real statement via the same regex the module itself uses, not a
    # fragile substring match.
    assert si.extract_bulk_insert_source_path(script_text) is None


def test_import_directory_reuses_script_on_second_pass_when_unchanged(sqlite_engine, tmp_path):
    csv_dir = str(tmp_path / "csvs")
    sql_dir = str(tmp_path / "sql")
    _write_csv(csv_dir, "SourceAccounts.csv", [{"Name": "Acme", "Legacy_Id": "A1"}])
    si.import_directory(sqlite_engine, csv_dir, sql_dir=sql_dir, schema="dbo", ticket="TEST-1")

    # Same header, new data -- second pass should reuse the existing script.
    _write_csv(csv_dir, "SourceAccounts.csv", [
        {"Name": "Acme", "Legacy_Id": "A1"},
        {"Name": "Initech", "Legacy_Id": "A3"},
    ])
    results = si.import_directory(sqlite_engine, csv_dir, sql_dir=sql_dir, schema="dbo")

    assert results[0]["status"] == "reused"
    assert results[0]["rows"] == 2
    df = pd.read_sql('SELECT * FROM "dbo"."SourceAccounts" ORDER BY Legacy_Id', sqlite_engine)
    assert list(df["Legacy_Id"]) == ["A1", "A3"]


def test_import_directory_blocks_on_column_drift(sqlite_engine, tmp_path):
    csv_dir = str(tmp_path / "csvs")
    sql_dir = str(tmp_path / "sql")
    _write_csv(csv_dir, "SourceAccounts.csv", [{"Name": "Acme", "Legacy_Id": "A1"}])
    si.import_directory(sqlite_engine, csv_dir, sql_dir=sql_dir, schema="dbo", ticket="TEST-1")

    # A genuinely different header (column added) -- must block, not
    # silently reload with a mismatched script.
    _write_csv(csv_dir, "SourceAccounts.csv", [{"Name": "Acme", "Legacy_Id": "A1", "NewCol": "x"}])
    results = si.import_directory(sqlite_engine, csv_dir, sql_dir=sql_dir, schema="dbo")

    assert results[0]["status"] == "drift_blocked"
    assert results[0]["drift"]["added"] == ["NewCol"]
