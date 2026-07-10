import openpyxl

from mapping_doc import _safe_sheet_name, check_mapping_balance, extract_insert_columns

SQL = """
-- staging
INSERT INTO dbo.Account_Load (Name, BillingCity, Legacy_Id__c)
SELECT Name, City, LegacyId FROM SourceAccounts;

INSERT INTO [dbo].[Contact_Load] ([FirstName], [LastName])
SELECT FirstName, LastName FROM SourceContacts;
"""


def test_extract_insert_columns_matches_named_table():
    cols = extract_insert_columns(SQL, "Account_Load")
    assert cols == ["Name", "BillingCity", "Legacy_Id__c"]


def test_extract_insert_columns_is_case_insensitive_on_table_name():
    cols = extract_insert_columns(SQL, "account_load")
    assert cols == ["Name", "BillingCity", "Legacy_Id__c"]


def test_extract_insert_columns_strips_brackets():
    cols = extract_insert_columns(SQL, "Contact_Load")
    assert cols == ["FirstName", "LastName"]


def test_extract_insert_columns_defaults_to_first_insert_when_table_none():
    cols = extract_insert_columns(SQL, None)
    assert cols == ["Name", "BillingCity", "Legacy_Id__c"]


def test_extract_insert_columns_returns_none_when_no_match():
    assert extract_insert_columns(SQL, "Opportunity_Load") is None


def test_safe_sheet_name_strips_invalid_excel_characters():
    assert _safe_sheet_name("Account:Contact/Test") == "Account_Contact_Test"


def test_safe_sheet_name_truncates_to_31_chars():
    name = "A" * 40
    result = _safe_sheet_name(name)
    assert len(result) == 31


class _StubObject:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, object_name, fields):
        setattr(self, object_name, _StubObject(fields))


def _write_mapping_workbook(path, object_name, rows):
    """rows: list of (source_field, migrate_data, target_field) starting
    at row 4, matching mapping_doc.py's real column layout (source field
    API = col 2, Migrate Data = col 9, Target Field API = col 15)."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(object_name)
    for i, (source, migrate, target) in enumerate(rows, start=4):
        ws.cell(row=i, column=2, value=source)
        ws.cell(row=i, column=9, value=migrate)
        ws.cell(row=i, column=15, value=target)
    wb.save(path)


def test_check_mapping_balance_detects_duplicate_target_field_in_one_sheet(tmp_path):
    mapping_path = tmp_path / "mapping.xlsx"
    _write_mapping_workbook(mapping_path, "Account", [
        ("first_name", "Yes", "Name"),
        ("company_name", "Yes", "Name"),  # duplicate target -- hard rule 14
    ])
    sql_path = tmp_path / "transform.sql"
    sql_path.write_text("INSERT INTO Account_Load (Name) SELECT x FROM y;", encoding="utf-8")

    sf = _StubSF("Account", [{"name": "Name"}])
    result = check_mapping_balance(sf, str(mapping_path), "Account", str(sql_path))

    assert result["duplicate_target_fields"] == {"Name": ["first_name", "company_name"]}


def test_check_mapping_balance_no_duplicates_when_targets_distinct(tmp_path):
    mapping_path = tmp_path / "mapping.xlsx"
    _write_mapping_workbook(mapping_path, "Account", [
        ("first_name", "Yes", "Name"),
        ("city", "Yes", "BillingCity"),
    ])
    sql_path = tmp_path / "transform.sql"
    sql_path.write_text("INSERT INTO Account_Load (Name, BillingCity) SELECT x, y FROM z;", encoding="utf-8")

    sf = _StubSF("Account", [{"name": "Name"}, {"name": "BillingCity"}])
    result = check_mapping_balance(sf, str(mapping_path), "Account", str(sql_path))

    assert result["duplicate_target_fields"] == {}
    assert result["duplicate_implemented_columns"] == []


def test_check_mapping_balance_detects_duplicate_implemented_column(tmp_path):
    mapping_path = tmp_path / "mapping.xlsx"
    _write_mapping_workbook(mapping_path, "Account", [("first_name", "Yes", "Name")])
    sql_path = tmp_path / "transform.sql"
    # Name listed twice in one INSERT INTO -- would break the real SQL.
    sql_path.write_text("INSERT INTO Account_Load (Name, Name) SELECT x, y FROM z;", encoding="utf-8")

    sf = _StubSF("Account", [{"name": "Name"}])
    result = check_mapping_balance(sf, str(mapping_path), "Account", str(sql_path))

    assert result["duplicate_implemented_columns"] == ["Name"]
