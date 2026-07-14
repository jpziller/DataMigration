# Docker local dev environment (roadmap #68/#69)

An alternative to README.md's "One-time environment setup" steps 3–7
(Python venv, SQL Server/PostgreSQL engine, SSMS/psql, the driver,
creating the mirror database) — not a different architecture, the same
one, packaged so `docker compose up` replaces a manual multi-installer
setup. Nothing about this changes any Hard Rule in `CLAUDE.md`:
`replicate`/`bulkops` are still the only write paths, the mirror DB is
still the only thing `replicate`/`DROP`/`CREATE` ever touch (Hard Rule
1), and a live Salesforce write still needs explicit confirmation (Hard
Rule 2) — this is a packaging change, not a design change.

## What you get

Two backend **profiles** — `mssql` (default) and `postgres` — each with
its own pair of services in `docker-compose.yml`. Pick one via
`COMPOSE_PROFILES` in `.env` or `--profile` per command; never both at
once (Compose profiles keep them structurally exclusive, rather than
merging `depends_on` the confusing way a second override file would).
SQLite has no service here at all — see "What this doesn't do" below.

**`mssql` profile**:
- **`sqlserver`** — SQL Server 2022, Developer Edition (free,
  full-featured, non-production use only). Data persists in a named
  volume (`sqlserver_data`) across `down`/`up`; `down -v` wipes it. Its
  healthcheck only confirms the TCP listener is up, not that SQL Server
  can authenticate a login yet — deliberately dependency-free (whether
  this image bundles `sqlcmd` was never confirmed, so the healthcheck
  doesn't rely on it).
- **`app-mssql`** — see "The `app-*` image" below.

**`postgres` profile**:
- **`postgres`** — PostgreSQL 16 (matches the same version this repo's
  own CI already runs integration tests against, `.github/workflows/tests.yml`).
  Data persists in `postgres_data`; `down -v` wipes it. Healthcheck uses
  `pg_isready` — unlike `sqlcmd`'s unverified-bundling risk above, this
  one is not a guess: this repo's own CI already runs `pg_isready`
  against this exact image today, confirmed working.
- **`app-postgres`** — see "The `app-*` image" below.

**The `app-*` image** (one Dockerfile, shared by both profiles — only
the `environment:` block differs per profile): this repo's Python
environment, `requirements.txt` already installed, plus the Microsoft
ODBC Driver 18 for SQL Server + `sqlcmd` (`mssql-tools18`),
`postgresql-client` (`psql`/`pg_isready` — `psycopg2-binary` in
`requirements.txt` is Python-only and provides neither binary), and the
Salesforce CLI (`sf`, via NodeSource's current Node LTS). The repo
itself is **bind-mounted**, not copied into the image — edits on your
host are reflected immediately, no rebuild needed for a Python/SQL file
change (only for a `requirements.txt` change). On startup, `docker/init-db.sh`
runs an idempotent, retrying "create the empty mirror database if it
doesn't exist yet" step (plus, for Postgres specifically, `CREATE SCHEMA
IF NOT EXISTS "dbo"` — Postgres has no built-in `dbo` schema the way SQL
Server does, and every `cli.py` command defaults `--schema` to `"dbo"`
regardless of backend) — then stays running for `docker compose exec
app-<backend> <command>`.

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + the Compose plugin
  (Linux) — this setup uses Compose v2 syntax (`condition:
  service_healthy`, `profiles:`), not the older standalone
  `docker-compose` v1.
- A `.env` file (`copy .env.example .env`, same as README.md's step 14):
  `COMPOSE_PROFILES` picks the backend (`mssql` default, or `postgres`);
  **`MSSQL_SA_PASSWORD`** (mssql profile) or **`POSTGRES_PASSWORD`**
  (postgres profile) set to a strong password; your normal `SF_*` auth
  values filled in either way.

## Quickstart

```bash
# mssql (default) -- COMPOSE_PROFILES=mssql in .env, or:
docker compose --profile mssql up -d
docker compose exec app-mssql python cli.py list-objects
docker compose exec app-mssql python cli.py replicate Account

# postgres -- COMPOSE_PROFILES=postgres in .env, or:
docker compose --profile postgres up -d
docker compose exec app-postgres python cli.py list-objects
docker compose exec app-postgres python cli.py replicate Account
```

`docker compose up -d` with no `--profile` flag uses whatever
`COMPOSE_PROFILES` says in your `.env` (defaults to `mssql` in
`.env.example`, so a plain `docker compose up -d` behaves exactly like
before profiles existed unless you change it).

First run takes longer than subsequent ones — pulling the database
image, then its own first-time startup, genuinely can take longer than
the healthcheck's `start_period`/`retries` grace period on a slower
machine. If `app-mssql`/`app-postgres` never starts, check `docker
compose logs sqlserver`/`docker compose logs postgres` for the actual
startup state, and `docker compose logs app-mssql`/`app-postgres` for
`init-db.sh`'s own retry messages (it retries the real login-and-query
check for up to 120s on its own, independent of the healthcheck) —
increase the healthcheck's `retries`/`interval` in `docker-compose.yml`
if 130s of combined grace still isn't enough.

Every command in `CLAUDE.md`'s "Canonical commands" section works the
same way — prefix it with `docker compose exec app-mssql` or `docker
compose exec app-postgres` instead of `.venv/Scripts/python.exe`. For an
interactive shell inside the container instead of one-off commands:

```bash
docker compose exec app-mssql bash      # or app-postgres
```

**Verified (2026-07-13)** on a clean rebuild, both profiles: Node 22
inside `app-*` (the `markAsUncloneable` fix holds), a real login as
`sa`/`postgres` against the sibling database container, the mirror
database (and, for Postgres, its `dbo` schema) created by
`docker/init-db.sh`, `cli.py list-objects` returning real data over a
`jwt`-mode Salesforce connection, `replicate Account` writing real rows
through the actual compose network (not an ad hoc throwaway container),
and idempotent restart (`down` then `up` again, no `-v`) with data
intact — the whole stack end-to-end for both backends, not just the
build step. One real bug surfaced only by this live test and fixed
along the way: `replicate.py` wrote Salesforce boolean fields as Python
`0`/`1` integers, which SQL Server's `BIT`/SQLite's `INTEGER` both
tolerate but Postgres's native `BOOLEAN` column rejects outright
(`column "IsDeleted" is of type boolean but expression is of type
integer`) — fixed to write real Python `True`/`False`, which all three
backends' own drivers adapt correctly. See `ROADMAP.md` #69 for the full
account.

## Choosing a Salesforce auth mode inside the container

`SF_AUTH_MODE` (from your mounted `.env`, per `sf_client.py`) works
differently here than on a host machine — **`cli` mode does not work
inside this container at all.** Use `jwt` or `password` for anything
running in Docker.

- **`jwt` (recommended for this setup)** — pure Python, no browser, no
  shelling out to the `sf` binary at all (`connect_salesforce()` calls
  `simple_salesforce`'s own JWT bearer flow directly). Works immediately
  with zero extra container config: mount (or just keep) `server.key` at
  the repo root as usual — it's already inside the container via the
  bind mount. Needs `SF_USERNAME`/`SF_CONSUMER_KEY` for the target org's
  own Connected App / External Client App (see README.md's "Auth modes"
  section) — these are per-org, so a different target org than the one
  your Connected App was set up against needs its own Consumer Key, not
  a reused one.
- **`password`** — same story: pure Python, no `sf` CLI involved, works
  immediately.
- **`cli` does not work inside this container — use `jwt`/`password`
  instead.** `cli` mode itself is completely fine outside Docker (a
  host-installed venv reaches the OS keychain natively); the limitation
  is specific to reusing a host login *from inside a Linux container*.

  Why: as part of Salesforce's May 27, 2026 CLI credential-security
  update, `sf` stopped storing org authorization in a plaintext file
  under `~/.sf` and now stores the actual token in the **host OS's
  native credential store** (Windows Credential Manager / macOS Keychain
  / `libsecret` on Linux) — a Linux container has no way to reach a
  Windows/macOS keychain entry through any bind mount. Confirmed live
  (2026-07-13): mounting `~/.sf` into the container only ever exposes
  logs and cache (`deploy-cache.json`, `manifestCache`, `sf-*.log`),
  never an `orgs/` directory with auth JSON, and `sf org display
  --target-org <alias>` inside the container fails with
  `NamedOrgNotFoundError` regardless of the mount path. This section
  used to document a `~/.sf` bind-mount workaround for exactly this —
  it no longer works, full stop; `docker-compose.yml`'s `app.volumes`
  keeps the mount line commented out for reference only.

## Inspecting the mirror DB

Three equally valid ways, same read-only spirit as `CLAUDE.md`'s own
"read-only eyes" guidance:

- From inside the container:
  - mssql: `docker compose exec app-mssql sqlcmd -S sqlserver -U sa
    -P "$SQL_PWD" -C -d SF_Migration -Q "SELECT COUNT(*) FROM dbo.Account;"`
  - postgres: `docker compose exec app-postgres sh -c 'PGPASSWORD="$SQL_PWD"
    psql -h postgres -U postgres -d SF_Migration -c "SELECT COUNT(*)
    FROM dbo.\"Account\""'` — note `psql` takes its password via the
    `PGPASSWORD` environment variable (or an interactive prompt), not a
    `-P`-style flag the way `sqlcmd` does; without it, a non-interactive
    `docker compose exec` fails with "fe_sendauth: no password
    supplied" rather than prompting.
  - Either way: `$SQL_PWD`, not `$MSSQL_SA_PASSWORD`/`$POSTGRES_PASSWORD`
    — those are only set as container-level environment variables on
    `sqlserver`/`postgres` themselves, not on `app-*`; `app-*` only ever
    gets the derived `SQL_PWD`/`SQL_UID` values from
    `docker-compose.yml`'s own `environment:` block.
- From the host, since the ports are published: a host-installed
  `sqlcmd`/Azure Data Studio/DBeaver/SSMS pointed at `localhost,1433`
  with `sa`/your `MSSQL_SA_PASSWORD` (mssql), or `psql`/DBeaver/Azure
  Data Studio pointed at `localhost:5432` with `postgres`/your
  `POSTGRES_PASSWORD` (postgres).
- `docker compose exec app-mssql python cli.py query "SELECT ..."` (or
  `app-postgres`) for anything that's really a Salesforce SOQL query
  rather than a local SQL one.

## Why your `.env`'s own `SQL_*` values don't leak into the container

`docker-compose.yml`'s `app-mssql`/`app-postgres` services each set
`SQL_SERVER=sqlserver`/`SQL_SERVER=postgres` (and the other `SQL_*`
values matching whichever containerized database is active) directly in
their own `environment:` block. This wins over whatever's in your mounted
`.env` for two independent reasons: Compose's own documented precedence
(`environment:` beats `env_file:` when the same key appears in both), and
separately, `config.py`'s `load_dotenv()` call never overrides an
already-set OS environment variable either. Your real `.env`'s `SF_*` /
`MOCKAROO_API_KEY` / `TICKET_SYSTEM_*` values still load normally from the
mounted file — only the `SQL_*` connection settings are overridden, and
only for whichever `app-*` service is running.

**One subtlety worth knowing**: `.env` is read by two *different*
mechanisms here, which happen to point at the same file today but are
worth telling apart if something doesn't pick up a value you expect.
Compose itself reads a file literally named `.env` in the same directory
as `docker-compose.yml` for its own `${VAR}` substitutions (that's how
`${MSSQL_SA_PASSWORD:?...}`/`${POSTGRES_PASSWORD:?...}` get their values,
resolved when you run `docker compose up`, from wherever you run that
command — this includes `COMPOSE_PROFILES` itself). Separately, the
`app-*` service's `env_file: - .env` line loads that same file's
contents into the *container's* process environment at start time
(that's how `SF_*` etc. reach `config.py`'s own `load_dotenv()` call). If
you ever rename your env file or run `docker compose` from a different
working directory, these two can diverge in confusing ways — keep `.env`
at the repo root and run `docker compose` from there, same as every
other command in this repo already assumes.

## What this doesn't (yet) do

- No SQLite-backend container variant — `SQL_BACKEND=sqlite` needs no
  server at all (see README.md's "SQL backend" section), so there's
  nothing for Docker to add there; run it directly in a plain Python venv
  as documented, container or not.
- No production deployment story here — `MSSQL_PID: Developer` /
  `postgres:16` (the free, non-production-oriented default tag) in
  `docker-compose.yml` are both explicitly dev/practice framing,
  matching `CLAUDE.md`'s own framing throughout.
- `app-mssql`/`app-postgres` both run as root inside their own container
  — a deliberate simplification for a local-only dev tool, not an
  oversight. The bind-mounted repo already means the container can
  read/write your host filesystem at that one path regardless of the
  in-container user, and adding a non-root user here would trade that
  away for the classic bind-mount UID/GID mismatch headache (files
  created in the container owned by an ID that doesn't match your host
  user) for no real additional isolation in this specific setup. Worth
  revisiting if this ever needs to run somewhere less trusted than a
  developer's own machine.
- Only one backend's containers run at a time — `COMPOSE_PROFILES`
  picks `mssql` or `postgres`, never both simultaneously (see "What you
  get" above for why this is a deliberate structural choice, not a
  current limitation to lift later). Running the actual migration
  methodology (Snowfakery mock data, a real transform, `bulkops`) against
  a live org through the Postgres profile is real, separate follow-up
  work — this document only covers getting the container environment
  itself running and verified; see `ROADMAP.md` #69 for what's been
  exercised so far.
