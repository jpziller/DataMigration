"""Map a Salesforce describe field to a SQL Server column type.

Builds typed replicate tables from a Salesforce describe. Compound fields (address, location)
are skipped on both the DDL and the SELECT side because Bulk API 2.0 can't
query them directly -- their component fields (BillingStreet, BillingCity, ...)
are queried instead and already appear as their own describe fields.
"""
import datetime
from decimal import Context, Decimal, InvalidOperation

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


def _decimal_coercer(precision, scale):
    """Build a coercer for a double/currency/percent field that produces a
    value pyodbc's ``fast_executemany`` DECIMAL binding accepts.

    Two facets, both found live replicating a real NPSP org's Account rollup
    fields, both surfacing as ``pyodbc: Converting decimal loses precision``:

    1. Salesforce's Bulk API 2.0 exports large values in scientific notation
       (``"1.39E+8"``) -> a Decimal with a positive exponent.
    2. A value can carry a different scale than its column (``"250.0"``,
       scale 1, into a scale-0 column).

    ``fast_executemany`` pre-binds each DECIMAL parameter and the driver
    rejects any value whose exponent doesn't match the column scale. Quantizing
    to the column's own scale fixes both at once. A field with precision
    outside ``(0, 38]`` maps to a FLOAT column (see :func:`sf_type_to_sql`),
    which has no fixed scale, so bind a plain float there instead.
    """
    if not (0 < precision <= 38):
        def _to_float(v):
            if not isinstance(v, str):
                return None
            try:
                return float(v)
            except ValueError:
                return None
        return _to_float

    quantum = Decimal(1).scaleb(-scale)      # scale 2 -> 0.01 ; scale 0 -> 1
    ctx = Context(prec=precision)            # results always fit the column
    def _to_decimal(v):
        if not isinstance(v, str):
            return None
        try:
            return Decimal(v).quantize(quantum, context=ctx)
        except (InvalidOperation, ValueError):
            return None
    return _to_decimal


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


# Types whose coercer needs no per-field parameters. double/currency/percent
# are handled separately (scale-aware) via _decimal_coercer.
_COERCER_BY_TYPE = {
    "int": _to_int,
    "date": _to_date,
    "datetime": _to_datetime,
    "time": _to_time,
}
_DECIMAL_TYPES = {"double", "currency", "percent"}


def typed_value_coercers(desc) -> dict:
    """Field name -> coercion function, for every column the typed replicate
    path needs to convert out of the CSV's plain text before to_sql. Numeric
    fields get a scale-aware coercer built from their describe precision/scale
    so the value matches its DECIMAL column exactly (see _decimal_coercer)."""
    coercers = {}
    for f in desc["fields"]:
        t = f["type"]
        if t in _DECIMAL_TYPES:
            coercers[f["name"]] = _decimal_coercer(
                int(f.get("precision") or 0), int(f.get("scale") or 0))
        elif t in _COERCER_BY_TYPE:
            coercers[f["name"]] = _COERCER_BY_TYPE[t]
    return coercers
