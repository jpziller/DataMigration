#!/bin/sh
# One-shot mirror-DB creation, run at the START of the `app` container
# (see docker-compose.yml's `command:`) -- not by a separate init
# container. Found in review: reusing mcr.microsoft.com/mssql/server
# (the SQL Server ENGINE image) as a throwaway "sqlcmd" client container
# was never actually confirmed to have sqlcmd bundled in it at all -- an
# unverified assumption that could have silently blocked the whole stack
# from ever starting. Running this from `app` instead uses ONLY
# mssql-tools18 this same Dockerfile already installs and verifies via
# its own apt-get install step, and reuses the exact SQL_SERVER/
# SQL_DATABASE/SQL_UID/SQL_PWD values docker-compose.yml already sets on
# this container for the Python app's own connection -- no separate,
# duplicated credentials to keep in sync.
#
# Idempotent -- safe to run again on every `docker compose up`.
# Hard Rule 1 (Mirror-DB-Only Writes) applies here too: this only ever
# creates the empty mirror database named by SQL_DATABASE, never touches
# a source/production database.
set -e

# sqlserver's own healthcheck (docker-compose.yml) only confirms the TCP
# port is accepting connections -- not that SQL Server has finished its
# own internal startup/recovery and can actually authenticate a login,
# which can genuinely take longer on a first-ever run (e.g. generating
# its master key). Retry the REAL login-and-query check here, in the
# container that actually needs it to succeed, rather than trusting the
# coarser healthcheck alone.
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
