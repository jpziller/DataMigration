from source_ingestion import (
    check_drift,
    extract_bulk_insert_source_path,
    extract_create_table_columns,
    generate_import_script,
    table_name_for_csv,
)

SCRIPT_TEXT = """/*  header comment, ignored */
IF OBJECT_ID('dbo.orders_test', 'U') IS NOT NULL
    DROP TABLE [dbo].[orders_test];

CREATE TABLE [dbo].[orders_test] (
    [order_id] NVARCHAR(MAX) NULL,
    [customer_name] NVARCHAR(MAX) NULL,
    [amount] NVARCHAR(MAX) NULL
);

BULK INSERT [dbo].[orders_test]
FROM 'C:\\data\\orders_test.csv'
WITH (
    FORMAT = 'csv',
    FIRSTROW = 2,
    FIELDQUOTE = '"',
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    KEEPNULLS
);
"""


def _write_csv(path, header, rows=(("1", "a", "b"),)):
    lines = [",".join(header)] + [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_table_name_for_csv_sanitizes_non_alnum():
    assert table_name_for_csv("/some/dir/Client Export (final).csv") == "Client_Export__final_"


def test_table_name_for_csv_strips_extension_only():
    assert table_name_for_csv("SourceAccounts.csv") == "SourceAccounts"


def test_extract_create_table_columns_ordered():
    assert extract_create_table_columns(SCRIPT_TEXT) == ["order_id", "customer_name", "amount"]


def test_extract_bulk_insert_source_path():
    assert extract_bulk_insert_source_path(SCRIPT_TEXT) == "C:\\data\\orders_test.csv"


def test_extract_create_table_columns_returns_none_when_absent():
    assert extract_create_table_columns("SELECT 1;") is None


def test_generate_import_script_reads_header_and_numbers_sequentially(tmp_path):
    csv_path = _write_csv(tmp_path / "orders.csv", ["order_id", "customer_name", "amount"])
    sql_dir = tmp_path / "sql"

    first = generate_import_script(csv_path, "orders", "TEST-1", sql_dir=str(sql_dir))
    second_csv = _write_csv(tmp_path / "contacts.csv", ["contact_id", "email"])
    second = generate_import_script(second_csv, "contacts", "TEST-1", sql_dir=str(sql_dir))

    assert first.endswith("10_orders_import.sql")
    assert second.endswith("20_contacts_import.sql")
    assert "TEST-1" in open(first, encoding="utf-8").read()


def test_check_drift_ok_when_unchanged(tmp_path):
    csv_path = _write_csv(tmp_path / "orders.csv", ["order_id", "customer_name", "amount"])
    script_path = tmp_path / "script.sql"
    script_path.write_text(SCRIPT_TEXT, encoding="utf-8")

    result = check_drift(csv_path, str(script_path))
    assert result == {
        "ok": True, "added": [], "removed": [], "reordered": False,
        "current_columns": ["order_id", "customer_name", "amount"],
        "script_columns": ["order_id", "customer_name", "amount"],
    }


def test_check_drift_detects_added_and_removed(tmp_path):
    csv_path = _write_csv(tmp_path / "orders.csv", ["order_id", "customer_name", "total_amount"])
    script_path = tmp_path / "script.sql"
    script_path.write_text(SCRIPT_TEXT, encoding="utf-8")

    result = check_drift(csv_path, str(script_path))
    assert result["ok"] is False
    assert result["added"] == ["total_amount"]
    assert result["removed"] == ["amount"]
    assert result["reordered"] is False


def test_check_drift_detects_pure_reorder_with_same_column_set(tmp_path):
    # Same three columns as SCRIPT_TEXT, only the order changed -- BULK
    # INSERT maps columns positionally, so this must be flagged just as
    # seriously as a rename, per source_ingestion.py's own design.
    csv_path = _write_csv(tmp_path / "orders.csv", ["customer_name", "order_id", "amount"])
    script_path = tmp_path / "script.sql"
    script_path.write_text(SCRIPT_TEXT, encoding="utf-8")

    result = check_drift(csv_path, str(script_path))
    assert result["ok"] is False
    assert result["added"] == []
    assert result["removed"] == []
    assert result["reordered"] is True
