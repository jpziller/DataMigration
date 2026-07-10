from data_model_diagram import (
    _guess_fk_relationships,
    _render_entity,
    _render_relationship,
    _wrap_diagram,
)


def test_render_entity_formats_attributes_with_key_labels():
    block = _render_entity("Account", [("id", "Id", "PK"), ("string", "Name", None)])
    assert block == (
        "    Account {\n"
        "        id Id PK\n"
        "        string Name\n"
        "    }"
    )


def test_render_relationship_master_detail_is_solid_line():
    line = _render_relationship("Account", "Opportunity", "AccountId", is_master_detail=True, is_nillable=False)
    assert line == '    Account ||--|{ Opportunity : "AccountId"'


def test_render_relationship_lookup_is_dashed_line():
    line = _render_relationship("Account", "Contact", "AccountId", is_master_detail=False, is_nillable=True)
    assert line == '    Account ||..o{ Contact : "AccountId"'


def test_render_relationship_guessed_appends_label_suffix():
    line = _render_relationship("A", "B", "AId", is_master_detail=False, is_nillable=True, guessed=True)
    assert '"AId (guessed)"' in line


def test_wrap_diagram_includes_title_and_mermaid_fence():
    text = _wrap_diagram("My Model", ["    A {\n    }"], ['    A ||--o{ B : "x"'])
    assert text.startswith("# My Model\n")
    assert "```mermaid" in text
    assert "erDiagram" in text
    assert text.rstrip().endswith("```")


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
