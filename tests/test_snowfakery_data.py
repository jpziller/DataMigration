"""Coverage for snowfakery_data.py -- focused on _fix_snowfakery_datetime_strings(),
a real bug fix (see ROADMAP.md #28): Snowfakery's own JSON output
serializes a datetime value via Python's default str(datetime)
representation (space-separated, tz-aware), which is a genuine XSD
dateTime parse failure against Salesforce's Bulk API, not just
non-canonical -- and it's baked in before pandas/sql_dialect.py's own
dtype-based datetime handling ever sees a real datetime64 column.
"""
import pandas as pd

from snowfakery_data import _fix_snowfakery_datetime_strings

_DATETIME_FIELD = {"name": "EmailBouncedDate", "type": "datetime"}
_STRING_FIELD = {"name": "LastName", "type": "string"}


def test_fixes_space_separated_tz_aware_string_to_isoformat_t():
    df = pd.DataFrame({
        "EmailBouncedDate": ["2024-07-29 22:38:35+00:00", "2026-06-17 01:13:23+00:00"],
        "LastName": ["Smith", "Jones"],
    })
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD, _STRING_FIELD])
    assert list(out["EmailBouncedDate"]) == ["2024-07-29T22:38:35+00:00", "2026-06-17T01:13:23+00:00"]
    assert " " not in out["EmailBouncedDate"].iloc[0]
    # non-datetime fields untouched, even though they're plain strings too
    assert list(out["LastName"]) == ["Smith", "Jones"]


def test_leaves_null_and_empty_values_alone():
    df = pd.DataFrame({"EmailBouncedDate": [None, "", "2024-07-29 22:38:35+00:00"]})
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD])
    assert pd.isna(out["EmailBouncedDate"].iloc[0])
    assert out["EmailBouncedDate"].iloc[1] == ""
    assert out["EmailBouncedDate"].iloc[2] == "2024-07-29T22:38:35+00:00"


def test_no_op_when_column_not_present():
    df = pd.DataFrame({"LastName": ["Smith"]})
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD, _STRING_FIELD])
    assert list(out.columns) == ["LastName"]
