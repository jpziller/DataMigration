"""Unit coverage for profiling.py helpers that don't need a live SQL/SF
connection. profiling.py is SQL-Server-only for its real work (see CLAUDE.md),
but _as_count is pure and was added for a real robustness bug worth locking in.
"""
import profiling


def test_as_count_coerces_numeric_string_to_int():
    """Salesforce can return a SOQL COUNT()/COUNT_DISTINCT() value as a
    numeric string, which blew up 'total - populated' (int - str) while
    profiling WorkOrder on the SDO (2026-07-31)."""
    assert profiling._as_count("241") == 241
    assert profiling._as_count(241) == 241
    assert profiling._as_count("241.0") == 241  # tolerate a float-string too
    assert profiling._as_count(241.0) == 241


def test_as_count_preserves_none():
    assert profiling._as_count(None) is None


def test_as_count_degrades_unparseable_to_none_not_crash():
    """A value that isn't a number degrades to None rather than crashing the
    whole profile write for one odd field."""
    assert profiling._as_count("n/a") is None
    assert profiling._as_count(object()) is None
