#!/bin/sh
# One-shot mirror-DB creation, run by the sqlserver-init service in
# docker-compose.yml after the sqlserver service reports healthy.
# Idempotent -- safe to run again on every `docker compose up`.
#
# Hard Rule 1 (Mirror-DB-Only Writes) applies here too: this only ever
# creates the empty mirror database named by SQL_DATABASE, never touches
# a source/production database.
set -e

/opt/mssql-tools18/bin/sqlcmd -S sqlserver -U sa -P "$MSSQL_SA_PASSWORD" -C \
    -Q "IF DB_ID('${SQL_DATABASE}') IS NULL CREATE DATABASE [${SQL_DATABASE}];"
