"""Map a Salesforce describe field to a SQL Server column type.

Builds typed replicate tables from a Salesforce describe. Compound fields (address, location)
are skipped on both the DDL and the SELECT side because Bulk API 2.0 can't
query them directly -- their component fields (BillingStreet, BillingCity, ...)
are queried instead and already appear as their own describe fields.
"""
import datetime
from decimal import Decimal, InvalidOperation

COMPOUND_TYPES = {"address", "location"}


def is_compound(field) -> bool:
    return field["type"] in COMPOUND_TYPES


def sf_type_to_sql(field) -> str:
    t = field["type"]
    length = field.get("length") or 0
    precision = field.get("precision") or 0
    scale = field.get("scale") or 0

    if t in ("id", "reference"):
        return "NVARCHAR(18)"
    if t in ("string", "picklist", "combobox", "phone", "url",
             "email", "encryptedstring"):
        n = length if 0 < length <= 4000 else 4000
        return f"NVARCHAR({n})"
    if t in ("textarea", "multipicklist"):
        return "NVARCHAR(MAX)"
    if t == "boolean":
        return "BIT"
    if t == "int":
        return "INT"
    if t in ("double", "currency", "percent"):
        if 0 < precision <= 38:
            return f"DECIMAL({precision},{scale})"
        return "FLOAT"
    if t == "date":
        return "DATE"
    if t == "datetime":
        return "DATETIME2"
    if t == "time":
        return "TIME"
    if t == "base64":
        return "VARBINARY(MAX)"
    return "NVARCHAR(MAX)"


# --- value coercion for the typed (non-raw) replicate path ---
# Bulk API 2.0 CSV export returns every field as text, and replicate.py reads
# the extract with dtype=str, so int/decimal/date/datetime/time values still
# need converting back to native Python types before to_sql -- otherwise
# pyodbc hands the SQL Server driver a string for a DATETIME2/DECIMAL/INT
# column instead of a real value, which fails as DataError 22018.
# (Booleans are handled separately in replicate.py; that path already works.)

def _to_int(v):
    if not isinstance(v, str):
        return None
    return int(float(v))


def _to_decimal(v):
    if not isinstance(v, str):
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _to_date(v):
    if not isinstance(v, str):
        return None
    return datetime.date.fromisoformat(v[:10])


def _to_datetime(v):
    if not isinstance(v, str):
        return None
    dt = datetime.datetime.fromisoformat(v)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _to_time(v):
    if not isinstance(v, str):
        return None
    t = datetime.time.fromisoformat(v)
    return t.replace(tzinfo=None) if t.tzinfo else t


_COERCER_BY_TYPE = {
    "int": _to_int,
    "double": _to_decimal,
    "currency": _to_decimal,
    "percent": _to_decimal,
    "date": _to_date,
    "datetime": _to_datetime,
    "time": _to_time,
}


def typed_value_coercers(desc) -> dict:
    """Field name -> coercion function, for every column the typed replicate
    path needs to convert out of the CSV's plain text before to_sql."""
    return {
        f["name"]: _COERCER_BY_TYPE[f["type"]]
        for f in desc["fields"]
        if f["type"] in _COERCER_BY_TYPE
    }
