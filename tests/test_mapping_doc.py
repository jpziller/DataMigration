from mapping_doc import _safe_sheet_name, extract_insert_columns

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
