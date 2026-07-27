"""Type coercion for the typed replicate path (type_map.py).

Regression coverage for a two-facet bug found live replicating a real NPSP
org's Account rollup fields, both surfacing as pyodbc "Converting decimal
loses precision" under fast_executemany: (1) Bulk API scientific notation
("1.39E+8"), and (2) a value carrying a different scale than its DECIMAL
column ("250.0" into a scale-0 column). Both are fixed by quantizing to the
column's own scale.
"""
from decimal import Decimal

from type_map import _decimal_coercer, _to_int, typed_value_coercers


def test_decimal_coercer_expands_scientific_notation_to_column_scale():
    # currency(18,2): a scientific-notation export lands as a fixed-point
    # Decimal at the column scale (exponent -2), never a positive exponent.
    c = _decimal_coercer(18, 2)
    assert c("1.39E+8") == Decimal("139000000.00")
    assert c("1.39E+8").as_tuple().exponent == -2
    assert c("5.6E+9") == Decimal("5600000000.00")


def test_decimal_coercer_quantizes_value_scale_to_column_scale():
    # "250.0" (scale 1) into a scale-0 column -> scale 0, the facet that
    # still failed after only the exponent was fixed.
    c0 = _decimal_coercer(18, 0)
    assert c0("250.0") == Decimal("250")
    assert c0("250.0").as_tuple().exponent == 0
    # scale-2 column keeps two places
    c2 = _decimal_coercer(18, 2)
    assert c2("250") == Decimal("250.00")
    assert c2("0.1") == Decimal("0.10")


def test_decimal_coercer_float_fallback_for_out_of_range_precision():
    # precision outside (0,38] -> FLOAT column -> plain float, no scale issue
    c = _decimal_coercer(0, 0)
    assert c("1.39E+8") == 139000000.0
    assert isinstance(c("1.39E+8"), float)


def test_decimal_coercer_handles_junk_and_non_strings():
    c = _decimal_coercer(18, 2)
    assert c("not-a-number") is None
    assert c(None) is None
    assert c(123) is None  # coercers only accept the CSV's strings


def test_typed_value_coercers_builds_scale_aware_numeric_coercers():
    desc = {"fields": [
        {"name": "Amount__c", "type": "currency", "precision": 18, "scale": 2},
        {"name": "Count__c", "type": "double", "precision": 18, "scale": 0},
        {"name": "Name", "type": "string"},
        {"name": "When__c", "type": "date"},
    ]}
    coercers = typed_value_coercers(desc)
    assert set(coercers) == {"Amount__c", "Count__c", "When__c"}  # string skipped
    assert coercers["Amount__c"]("1.5") == Decimal("1.50")
    assert coercers["Count__c"]("250.0") == Decimal("250")


def test_to_int_via_float_path():
    assert _to_int("5") == 5
    assert _to_int("5.0") == 5
    assert _to_int(None) is None
