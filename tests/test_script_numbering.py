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
