#!/bin/sh
# One-shot mirror-DB creation, run at the START of the `app-*` container
# (see docker-compose.yml's `command:`) -- not by a separate init
# container. Found in review: reusing mcr.microsoft.com/mssql/server
# (the SQL Server ENGINE image) as a throwaway "sqlcmd" client container
# was never actually confirmed to have sqlcmd bundled in it at all -- an
# unverified assumption that could have silently blocked the whole stack
# from ever starting. Running this from `app-*` instead uses ONLY the
# mssql-tools18/postgresql-client this same Dockerfile already installs
# and is built from, and reuses the exact SQL_SERVER/SQL_DATABASE/
# SQL_UID/SQL_PWD values docker-compose.yml already sets on this
# container for the Python app's own connection -- no separate,
# duplicated credentials to keep in sync.
#
# Idempotent -- safe to run again on every `docker compose up`.
# Hard Rule 1 (Mirror-DB-Only Writes) applies here too: this only ever
# creates the empty mirror database (and, for Postgres, its "dbo"
# schema) named by SQL_DATABASE, never touches a source/production
# database.
set -e

case "$SQL_BACKEND" in
mssql)
    # sqlserver's own healthcheck (docker-compose.yml) only confirms the
    # TCP port is accepting connections -- not that SQL Server has
    # finished its own internal startup/recovery and can actually
    # authenticate a login, which can genuinely take longer on a
    # first-ever run (e.g. generating its master key). Retry the REAL
    # login-and-query check here, in the container that actually needs
    # it to succeed, rather than trusting the coarser healthcheck alone.
    attempt=0
    until sqlcmd -S "$SQL_SERVER" -U "$SQL_UID" -P "$SQL_PWD" -C -Q "SELECT 1" > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 60 ]; then
            echo "init-db.sh: sqlserver did not become ready to accept logins after 120s -- giving up." >&2
            exit 1
        fi
        sleep 2
    done

    sqlcmd -S "$SQL_SERVER" -U "$SQL_UID" -P "$SQL_PWD" -C \
        -Q "IF DB_ID('${SQL_DATABASE}') IS NULL CREATE DATABASE [${SQL_DATABASE}];"
    ;;

postgresql)
    export PGPASSWORD="$SQL_PWD"

    # postgres's own healthcheck (docker-compose.yml) uses pg_isready
    # too, but against the postgres SERVICE, before app-postgres even
    # starts -- this retries the real login-and-query check from THIS
    # container specifically (same defense-in-depth reasoning as the
    # mssql branch above), against the "postgres" maintenance database,
    # which always exists on any Postgres server regardless of whether
    # SQL_DATABASE has been created yet.
    attempt=0
    until psql -h "$SQL_SERVER" -p "${SQL_PORT:-5432}" -U "$SQL_UID" -d postgres -c "SELECT 1" > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge 60 ]; then
            echo "init-db.sh: postgres did not become ready to accept logins after 120s -- giving up." >&2
            exit 1
        fi
        sleep 2
    done

    # Postgres has no CREATE DATABASE IF NOT EXISTS (unlike SQL Server's
    # IF DB_ID(...) IS NULL above) -- check pg_database first, connecting
    # to the always-present "postgres" maintenance DB since SQL_DATABASE
    # itself may not exist yet on a first run (or after a SQL_DATABASE
    # rename against a volume from an earlier one).
    exists=$(psql -h "$SQL_SERVER" -p "${SQL_PORT:-5432}" -U "$SQL_UID" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '${SQL_DATABASE}'")
    if [ "$exists" != "1" ]; then
        psql -h "$SQL_SERVER" -p "${SQL_PORT:-5432}" -U "$SQL_UID" -d postgres -c \
            "CREATE DATABASE \"${SQL_DATABASE}\";"
    fi

    # Unlike SQL Server, Postgres has no built-in "dbo" schema (its own
    # default is "public") -- every cli.py command defaults --schema to
    # "dbo" regardless of backend, and nothing else creates it. Without
    # this, the first real replicate/bulkops call against a fresh
    # Postgres container fails outright with "schema dbo does not
    # exist." Postgres DOES support CREATE SCHEMA IF NOT EXISTS natively,
    # so this one needs no separate existence check.
    psql -h "$SQL_SERVER" -p "${SQL_PORT:-5432}" -U "$SQL_UID" -d "$SQL_DATABASE" -c \
        'CREATE SCHEMA IF NOT EXISTS "dbo";'
    ;;

*)
    echo "init-db.sh: unsupported SQL_BACKEND='${SQL_BACKEND}' for docker init (expected mssql or postgresql -- sqlite needs no server/init step at all)." >&2
    exit 1
    ;;
esac
