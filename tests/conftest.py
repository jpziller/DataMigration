"""Shared pytest fixtures across the test suite.

postgres_engine: a real (not mocked) PostgreSQL engine for integration
tests, mirroring the existing test_*_sqlite_integration.py convention now
that PostgresDialect is a real, live-verified backend (roadmap #69).
Connection details come from TEST_POSTGRES_* env vars (set by
.github/workflows/tests.yml's postgres service in CI); skipped
gracefully everywhere else (a contributor's own machine, a PR from a
fork with no service configured) rather than failing the whole suite
when no Postgres server is reachable -- SQLite's own equivalent fixture
never needed this because SQLite needs no server at all.
"""
import os

import pytest
from sqlalchemy import text

import sql_client
from config import Settings

_TEST_SCHEMA = "test_dbo"


@pytest.fixture
def postgres_engine():
    password = os.environ.get("TEST_POSTGRES_PASSWORD")
    if not password:
        pytest.skip("TEST_POSTGRES_PASSWORD not set -- no local/CI Postgres to test against")

    s = Settings(
        sql_backend="postgresql",
        sql_server=os.environ.get("TEST_POSTGRES_HOST", "localhost"),
        sql_port=os.environ.get("TEST_POSTGRES_PORT", "5432"),
        sql_uid=os.environ.get("TEST_POSTGRES_USER", "postgres"),
        sql_pwd=password,
        sql_database=os.environ.get("TEST_POSTGRES_DATABASE", "postgres"),
        sql_postgres_sslmode="disable",
    )
    engine = sql_client.make_engine(s)
    try:
        with engine.connect() as cx:
            cx.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Postgres not reachable ({s.sql_server}:{s.sql_port}) -- {e}")

    with engine.begin() as cx:
        cx.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
        cx.execute(text(f'CREATE SCHEMA "{_TEST_SCHEMA}"'))
    yield engine, s, _TEST_SCHEMA
    with engine.begin() as cx:
        cx.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
