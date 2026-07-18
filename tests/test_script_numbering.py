import pytest

import script_numbering as sn


def test_existing_numbers_empty_when_directory_missing(tmp_path):
    assert sn.existing_numbers(str(tmp_path / "does_not_exist")) == []


def test_existing_numbers_ignores_non_numbered_files(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "README.md").write_text("")
    (tmp_path / ".gitkeep").write_text("")
    assert sn.existing_numbers(str(tmp_path)) == [10]


def test_existing_numbers_sorted(tmp_path):
    (tmp_path / "030_opportunity_load.sql").write_text("")
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "020_contact_load.sql").write_text("")
    assert sn.existing_numbers(str(tmp_path)) == [10, 20, 30]


def test_next_number_starts_at_gap_when_empty(tmp_path):
    assert sn.next_number(str(tmp_path)) == 10


def test_next_number_is_gap_above_highest_existing(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "020_contact_load.sql").write_text("")
    assert sn.next_number(str(tmp_path)) == 30


def test_next_number_respects_custom_gap(tmp_path):
    (tmp_path / "005_account_load.sql").write_text("")
    assert sn.next_number(str(tmp_path), gap=5) == 10


def test_next_number_insert_between_picks_midpoint(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "020_contact_load.sql").write_text("")
    assert sn.next_number(str(tmp_path), after=10, before=20) == 15


def test_next_number_insert_between_avoids_already_used_midpoint(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "015_patch.sql").write_text("")
    (tmp_path / "020_contact_load.sql").write_text("")
    # Midpoint (15) is taken -- the next-closest free number should win.
    result = sn.next_number(str(tmp_path), after=10, before=20)
    assert result in (14, 16)
    assert result not in sn.existing_numbers(str(tmp_path))


def test_next_number_insert_between_repeated_calls_spread_out(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "020_contact_load.sql").write_text("")
    first = sn.next_number(str(tmp_path), after=10, before=20)
    assert first == 15
    (tmp_path / f"{first:03d}_patch.sql").write_text("")
    second = sn.next_number(str(tmp_path), after=10, before=20)
    assert second != first
    assert second not in sn.existing_numbers(str(tmp_path))


def test_next_number_raises_if_only_after_given(tmp_path):
    with pytest.raises(ValueError, match="Pass both after and before"):
        sn.next_number(str(tmp_path), after=10)


def test_next_number_raises_if_only_before_given(tmp_path):
    with pytest.raises(ValueError, match="Pass both after and before"):
        sn.next_number(str(tmp_path), before=20)


def test_next_number_raises_if_after_not_less_than_before(tmp_path):
    with pytest.raises(ValueError, match="must be less than"):
        sn.next_number(str(tmp_path), after=20, before=10)


def test_next_number_raises_if_after_equals_before(tmp_path):
    with pytest.raises(ValueError, match="must be less than"):
        sn.next_number(str(tmp_path), after=15, before=15)


def test_next_number_raises_when_gap_fully_used(tmp_path):
    (tmp_path / "010_a.sql").write_text("")
    for n in range(11, 20):
        (tmp_path / f"0{n}_x.sql").write_text("")
    (tmp_path / "020_b.sql").write_text("")
    with pytest.raises(ValueError, match="No free number"):
        sn.next_number(str(tmp_path), after=10, before=20)


def test_next_number_raises_when_no_integer_strictly_between(tmp_path):
    with pytest.raises(ValueError, match="No free number"):
        sn.next_number(str(tmp_path), after=10, before=11)


def test_format_number_zero_pads_to_three_digits():
    assert sn.format_number(10) == "010"
    assert sn.format_number(5) == "005"


def test_format_number_widens_past_three_digits():
    assert sn.format_number(1000) == "1000"


def test_matches_token_whole_token_only():
    assert sn.matches_token("Account", "010_account_load.sql")
    assert not sn.matches_token("Order", "030_orderitem_load.sql")


def test_matches_token_case_insensitive():
    assert sn.matches_token("account", "010_Account_Load.sql")


def test_script_filename_for_returns_empty_when_directory_missing(tmp_path):
    assert sn.script_filename_for("Account", str(tmp_path / "nope")) == ""


def test_script_filename_for_returns_empty_when_nothing_matches(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    assert sn.script_filename_for("Contact", str(tmp_path)) == ""


def test_script_filename_for_picks_highest_numbered_match(tmp_path):
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "090_account_load_v2.sql").write_text("")
    assert sn.script_filename_for("Account", str(tmp_path)) == "090_account_load_v2.sql"


def test_script_filename_for_without_known_objects_keeps_original_ambiguous_behavior(tmp_path):
    """Regression guard on the documented default: omitting known_objects
    (or passing None) must reproduce the original, real bug this project
    hit live (ROADMAP #76) -- a higher-numbered compound-name script
    still silently outranks the real, unrelated shorter-object script.
    Existing callers that don't pass known_objects must see zero
    behavior change."""
    (tmp_path / "020_contact_load.sql").write_text("")
    (tmp_path / "110_account_contact_relation_load.sql").write_text("")
    assert sn.script_filename_for("Contact", str(tmp_path)) == "110_account_contact_relation_load.sql"
    assert sn.script_filename_for("Contact", str(tmp_path), known_objects=None) == "110_account_contact_relation_load.sql"


def test_script_filename_for_known_objects_disqualifies_shorter_embedded_match(tmp_path):
    """The real fix: reproduces the exact live collision (a compound
    AccountContactRelation script also matching a bare Account lookup)
    and confirms known_objects resolves it correctly to the real,
    unrelated Account script instead."""
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "110_account_contact_relation_load.sql").write_text("")
    known = {"Account", "AccountContactRelation"}
    assert sn.script_filename_for("Account", str(tmp_path), known_objects=known) == "010_account_load.sql"


def test_script_filename_for_known_objects_only_helps_when_disqualifying_name_is_known(tmp_path):
    """Honest limitation, not silently 'fixed for everyone': if the
    caller's known_objects set doesn't happen to include the longer,
    disqualifying name, the original ambiguity still applies -- this is
    a real but partial fix, not a blanket guarantee."""
    (tmp_path / "010_account_load.sql").write_text("")
    (tmp_path / "110_account_contact_relation_load.sql").write_text("")
    # known_objects given, but WITHOUT the disqualifying longer name
    result = sn.script_filename_for("Account", str(tmp_path), known_objects={"Account"})
    assert result == "110_account_contact_relation_load.sql"


def test_script_filename_for_known_objects_never_disqualifies_a_shorter_or_equal_length_name(tmp_path):
    """A known object that's shorter than or equal in length to
    object_name itself must never disqualify a real match -- only a
    strictly longer name can be more specific than object_name."""
    (tmp_path / "010_account_load.sql").write_text("")
    known = {"Account", "Acct"}
    assert sn.script_filename_for("Account", str(tmp_path), known_objects=known) == "010_account_load.sql"


def test_disqualifying_match_matches_delimited_compound_filename():
    """The real gap matches_token() itself can't cover: a compound
    CamelCase object name has no internal delimiters, but its
    conventional snake_case filename does -- _disqualifying_match() has
    to strip delimiters to compare the two at all."""
    assert sn._disqualifying_match("AccountContactRelation", "110_account_contact_relation_load.sql")


def test_disqualifying_match_matches_merged_compound_filename():
    assert sn._disqualifying_match("AccountContactRelation", "110_accountcontactrelation_load.sql")


def test_disqualifying_match_case_insensitive():
    assert sn._disqualifying_match("giftcommitmentschedule", "170_GiftCommitmentSchedule_Load.sql")


def test_disqualifying_match_false_for_unrelated_name():
    assert not sn._disqualifying_match("GiftTransactionDesignation", "010_account_load.sql")
