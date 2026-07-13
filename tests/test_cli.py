"""Coverage for cli.py's own pure helper functions -- this project has
never unit-tested cli.py directly before (every command is dogfooded
live instead), but _parse_object_value_pairs() is a pure, reusable
utility with no Salesforce/SQL dependency, so it's worth testing in
isolation rather than only through a live command invocation.
"""
import pytest

from cli import _parse_object_value_pairs


def test_parse_object_value_pairs_basic():
    result = _parse_object_value_pairs(["Account=Account_Load", "Contact=Contact_Load"], "--load-table")
    assert result == {"Account": "Account_Load", "Contact": "Contact_Load"}


def test_parse_object_value_pairs_empty():
    assert _parse_object_value_pairs([], "--load-table") == {}


def test_parse_object_value_pairs_rejects_malformed_entry():
    with pytest.raises(Exception, match="--load-table must be Object=Value"):
        _parse_object_value_pairs(["AccountAccount_Load"], "--load-table")


def test_parse_object_value_pairs_rejects_duplicate_object():
    """Found in review: this exact silent-overwrite-on-duplicate-key bug
    was already fixed once for --scenario; --load-table/--migration-key
    had the identical gap at 4 separate call sites before being
    consolidated into this shared helper."""
    with pytest.raises(Exception, match="'Account' was given more than once"):
        _parse_object_value_pairs(["Account=Account_Load", "Account=Account_LoadV2"], "--load-table")


def test_parse_object_value_pairs_uses_option_name_in_error():
    with pytest.raises(Exception, match="--migration-key must be Object=Value"):
        _parse_object_value_pairs(["BadEntry"], "--migration-key")
