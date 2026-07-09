"""SQL Server connectivity via SQLAlchemy + pyodbc (ODBC Driver 18)."""
import urllib.parse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import Settings


def build_odbc_string(s: Settings) -> str:
    parts = [
        f"DRIVER={{{s.sql_driver}}}",
        f"SERVER={s.sql_server}",
        f"DATABASE={s.sql_database}",
        f"Encrypt={s.sql_encrypt}",
        f"TrustServerCertificate={s.sql_trust_cert}",
    ]
    if s.sql_trusted.lower() == "yes":
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={s.sql_uid}")
        parts.append(f"PWD={s.sql_pwd}")
    return ";".join(parts)


def make_engine(s: Settings) -> Engine:
    # NOTE: the SQL password (if any -- Windows/trusted auth needs none) ends
    # up inside the odbc_connect blob, not the URL's native user:pass@host
    # form -- so SQLAlchemy's own hide_password=True redaction (its default
    # logging/repr behavior) can't find and mask it. Nothing here sets
    # echo=True or prints/logs the engine or its .url today, and it must
    # stay that way -- do not add echo=True or debug-print this engine's URL
    # without first redacting PWD=... out of it, or the SQL Server password
    # will end up in cleartext in logs/console output.
    odbc = urllib.parse.quote_plus(build_odbc_string(s))
    # fast_executemany dramatically speeds up pandas.to_sql / executemany writes.
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={odbc}",
        fast_executemany=True,
    )
