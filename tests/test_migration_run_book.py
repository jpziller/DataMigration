import pytest

from migration_run_book import (
    _COLUMNS,
    _is_separator_row,
    _is_unparseable_dependency_note,
    _mermaid_escape_label,
    _object_matches,
    _parse_dependency_parents,
    _parse_template,
)


def _row(*cells):
    """Build a Markdown pipe-table row with exactly len(_COLUMNS) cells,
    padding with blanks -- avoids hand-counting `|` characters."""
    padded = list(cells) + [""] * (len(_COLUMNS) - len(cells))
    return "| " + " | ".join(padded) + " |"


HEADER = _row(*_COLUMNS)
SEPARATOR = "|" + "---|" * len(_COLUMNS)
ROW = _row("Load", "Account", "", "Not Started", "Yes")


def _write_template(tmp_path, body):
    path = tmp_path / "runbook.md"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_object_matches_exact_case_insensitive():
    assert _object_matches("Account", "account") is True


def test_object_matches_underscore_delimited_filename():
    assert _object_matches("Account", "010_account_load.sql") is True


def test_object_matches_order_does_not_match_orderitem_filename():
    # Regression: a naive substring check let "Order" match inside
    # "030_orderitem_load.sql", which would fill the OrderItem placeholder
    # with an Order log row.
    assert _object_matches("Order", "030_orderitem_load.sql") is False


def test_object_matches_orderitem_matches_its_own_filename():
    assert _object_matches("OrderItem", "030_orderitem_load.sql") is True


def test_object_matches_no_relation_is_false():
    assert _object_matches("Account", "030_orderitem_load.sql") is False


def test_is_separator_row_true_for_dashes():
    cells = ["---", ":---", "---:", ":---:"]
    assert _is_separator_row(cells) is True


def test_is_separator_row_false_for_real_data():
    cells = ["Load", "Account", "Not Started"]
    assert _is_separator_row(cells) is False


def test_parse_template_reads_phase_and_rows(tmp_path):
    body = f"## Load\n{HEADER}\n{SEPARATOR}\n{ROW}\n"
    phases = _parse_template(_write_template(tmp_path, body))

    assert len(phases) == 1
    assert phases[0]["name"] == "Load"
    assert len(phases[0]["rows"]) == 1
    assert phases[0]["rows"][0][1] == "Account"


def test_parse_template_rejects_header_that_does_not_match_schema(tmp_path):
    bad_header = "| Stage | Object |"
    body = f"## Load\n{bad_header}\n|---|---|\n"
    with pytest.raises(ValueError):
        _parse_template(_write_template(tmp_path, body))


def test_parse_template_rejects_data_row_with_wrong_cell_count(tmp_path):
    body = f"## Load\n{HEADER}\n{SEPARATOR}\n| Load | Account |\n"
    with pytest.raises(ValueError):
        _parse_template(_write_template(tmp_path, body))


def test_parse_dependency_parents_none_yields_no_parents():
    assert _parse_dependency_parents("None") == []
    assert _parse_dependency_parents(None) == []
    assert _parse_dependency_parents("") == []


def test_parse_dependency_parents_single():
    assert _parse_dependency_parents("After: Account") == ["Account"]


def test_parse_dependency_parents_multiple_comma_separated():
    assert _parse_dependency_parents("After: Account, Contact") == ["Account", "Contact"]


def test_parse_dependency_parents_ignores_parallel_with_suffix():
    assert _parse_dependency_parents("After: Account; parallel with: Opportunity") == ["Account"]


def test_mermaid_escape_label_escapes_quotes_and_brackets():
    assert _mermaid_escape_label('Say "hi" [now]') == "Say #quot;hi#quot; (now)"


def test_is_unparseable_dependency_note_false_for_none_and_blank():
    assert _is_unparseable_dependency_note("None") is False
    assert _is_unparseable_dependency_note(None) is False
    assert _is_unparseable_dependency_note("") is False


def test_is_unparseable_dependency_note_false_for_real_after_text():
    assert _is_unparseable_dependency_note("After: Account") is False


def test_is_unparseable_dependency_note_true_for_free_text_note():
    """Found in review: a human-written Dependency note that isn't
    "None" and doesn't match the "After: X" convention used to be
    silently indistinguishable from "no dependency" -- both produced an
    empty parent list from _parse_dependency_parents() with no signal
    that a real dependency might have been dropped."""
    assert _is_unparseable_dependency_note("Depends on Account for billing info") is True
