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
    odbc = urllib.parse.quote_plus(build_odbc_string(s))
    # fast_executemany dramatically speeds up pandas.to_sql / executemany writes.
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={odbc}",
        fast_executemany=True,
    )
