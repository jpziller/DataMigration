from data_model_diagram import (
    _guess_fk_relationships,
    _object_type_css_class,
    _render_class,
    _render_relationship,
    _wrap_diagram,
)


def test_render_class_formats_attributes_with_key_labels():
    block = _render_class("Account", [("id", "Id", "PK"), ("string", "Name", None)])
    assert block == (
        "    class Account {\n"
        "        +id Id PK\n"
        "        +string Name\n"
        "    }"
    )


def test_render_relationship_master_detail_is_composition():
    line = _render_relationship("Account", "Opportunity", "AccountId", is_master_detail=True, is_nillable=False)
    assert line == '    Account "1" *-- "1..*" Opportunity : "AccountId"'


def test_render_relationship_lookup_is_aggregation():
    line = _render_relationship("Account", "Contact", "AccountId", is_master_detail=False, is_nillable=True)
    assert line == '    Account "1" o-- "0..*" Contact : "AccountId"'


def test_render_relationship_guessed_appends_label_suffix_and_is_aggregation():
    # guessed relationships never claim the stronger composition form,
    # even if is_master_detail were somehow True.
    line = _render_relationship("A", "B", "AId", is_master_detail=True, is_nillable=True, guessed=True)
    assert '"AId (guessed)"' in line
    assert "o--" in line
    assert "*--" not in line


def test_object_type_css_class_external_by_api_suffix():
    assert _object_type_css_class("SAP_Product__x", is_custom=False) == "externalObject"


def test_object_type_css_class_custom_when_describe_flags_it():
    assert _object_type_css_class("Invoice__c", is_custom=True) == "customObject"


def test_object_type_css_class_standard_otherwise():
    assert _object_type_css_class("Account", is_custom=False) == "standardObject"


def test_wrap_diagram_includes_title_fence_and_classdef():
    text = _wrap_diagram(
        "My Model", ["    class A {\n    }"], ['    A "1" *-- "1..*" B : "x"'],
        css_classes_by_entity={"A": "standardObject"},
    )
    assert text.startswith("# My Model\n")
    assert "```mermaid" in text
    assert "classDiagram" in text
    assert "classDef standardObject" in text
    assert "class A:::standardObject" in text
    assert text.rstrip().endswith("```")


def test_wrap_diagram_omits_classdef_section_when_no_css_classes():
    text = _wrap_diagram("My Model", ["    class A {\n    }"], [])
    assert "classDef" not in text
    assert ":::" not in text


def test_guess_fk_relationships_matches_naming_convention():
    columns_by_table = {
        "SourceAccounts": [("int", "account_id")],
        "SourceContacts": [("int", "contact_id"), ("int", "SourceAccountsId")],
    }
    guesses = _guess_fk_relationships(["SourceAccounts", "SourceContacts"], columns_by_table)
    assert guesses == [{"child": "SourceContacts", "parent": "SourceAccounts", "field": "SourceAccountsId"}]


def test_guess_fk_relationships_does_not_match_own_primary_key_style_column():
    # account_id in SourceAccounts itself shouldn't guess a self-relationship
    # just because it matches the "_id" suffix pattern.
    columns_by_table = {"SourceAccounts": [("int", "account_id")]}
    guesses = _guess_fk_relationships(["SourceAccounts"], columns_by_table)
    assert guesses == []


def test_guess_fk_relationships_no_match_when_no_other_table_fits():
    columns_by_table = {
        "SourceContacts": [("int", "some_unrelated_id")],
        "SourceAccounts": [("int", "account_id")],
    }
    guesses = _guess_fk_relationships(["SourceAccounts", "SourceContacts"], columns_by_table)
    assert guesses == []
