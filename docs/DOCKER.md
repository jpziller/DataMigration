# Docker local dev environment (roadmap #68)

An alternative to README.md's "One-time environment setup" steps 3–7
(Python venv, SQL Server engine, SSMS, the ODBC driver, creating the
mirror database) — not a different architecture, the same one, packaged
so `docker compose up` replaces a manual multi-installer setup. Nothing
about this changes any Hard Rule in `CLAUDE.md`: `replicate`/`bulkops`
are still the only write paths, the mirror DB is still the only thing
`replicate`/`DROP`/`CREATE` ever touch (Hard Rule 1), and a live Salesforce
write still needs explicit confirmation (Hard Rule 2) — this is a
packaging change, not a design change.

## What you get

Two services, defined in `docker-compose.yml`:

- **`sqlserver`** — SQL Server 2022, Developer Edition (free, full-featured,
  non-production use only — same edition README.md's own step 4 already
  recommends). Data persists in a named volume (`sqlserver_data`) across
  `docker compose down`/`up`; `docker compose down -v` wipes it. Its
  healthcheck only confirms the TCP listener is up, not that SQL Server
  can actually authenticate a login yet (those can genuinely differ by
  tens of seconds on a first-ever run) — deliberately dependency-free
  (see the compose file's own comment for why: unlike `app`'s image,
  whether `sqlserver`'s own image bundles `sqlcmd` was never actually
  confirmed, so the healthcheck doesn't rely on it at all).
- **`app`** — this repo's Python environment: `requirements.txt` already
  installed, plus the Microsoft ODBC Driver 18 for SQL Server, `sqlcmd`
  (`mssql-tools18`), and the Salesforce CLI (`sf`, installed via
  NodeSource's current Node LTS, not Debian's own default `nodejs`/`npm`
  packages — see the Dockerfile's own comment), all preinstalled. The
  repo itself is **bind-mounted**, not copied into the image — edits on
  your host are reflected immediately, no rebuild needed for a Python/SQL
  file change (only for a `requirements.txt` change). On startup, `app`
  runs `docker/init-db.sh` — an idempotent, retrying "create the empty
  mirror database if it doesn't exist yet" step, using this same
  container's own verified `mssql-tools18` install (deliberately not a
  separate init container reusing the `sqlserver` image, for the same
  unverified-`sqlcmd` reason above) — then stays running for `docker
  compose exec app <command>`.

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + the Compose plugin
  (Linux) — this setup uses Compose v2 syntax (`condition:
  service_healthy`), not the older standalone `docker-compose` v1.
- A `.env` file (`copy .env.example .env`, same as README.md's step 13),
  with **`MSSQL_SA_PASSWORD`** set to a strong password (8+ characters,
  upper+lower+digit+symbol — SQL Server rejects a weak one at container
  startup) and your normal `SF_*` auth values filled in.

## Quickstart

```bash
docker compose up -d          # builds the app image, starts sqlserver,
                               # waits for it to be healthy, then starts
                               # app (which creates the mirror DB itself)
docker compose exec app python cli.py list-objects
docker compose exec app python cli.py describe Account
docker compose exec app python cli.py replicate Account
```

First run takes longer than subsequent ones — pulling the SQL Server
image, then SQL Server's own first-time startup (generating its master
key, etc.) genuinely can take longer than the `sqlserver` healthcheck's
`start_period`/`retries` grace period on a slower machine. If `app` never
starts, check `docker compose logs sqlserver` for the actual startup
state, and `docker compose logs app` for `init-db.sh`'s own retry
messages (it retries the real login-and-query check for up to 120s on
its own, independent of the healthcheck) — increase the healthcheck's
`retries`/`interval` in `docker-compose.yml` if 130s of combined grace
still isn't enough.

Every command in `CLAUDE.md`'s "Canonical commands" section works the
same way — prefix it with `docker compose exec app` instead of
`.venv/Scripts/python.exe`. For an interactive shell inside the container
instead of one-off commands:

```bash
docker compose exec app bash
```

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
- **`cli` — confirmed broken inside this container, not just
  inconvenient.** This section used to document a `~/.sf` bind-mount
  workaround (reuse a host `sf org login web` session from inside the
  container). That workaround **no longer works, full stop** — confirmed
  live (2026-07-13) against a Summer '26 `sf` CLI: as part of
  Salesforce's May 27, 2026 CLI credential-security update, `sf` stopped
  storing org authorization in a plaintext file under `~/.sf` and now
  stores the actual token in the **host OS's native credential store**
  (Windows Credential Manager / macOS Keychain / `libsecret` on Linux).
  Mounting `~/.sf` into the container only ever exposes logs and cache
  (`deploy-cache.json`, `manifestCache`, `sf-*.log`) — there is no
  `orgs/` directory with auth JSON to find on either side of the mount,
  because the real secret lives in a host-OS keychain a Linux container
  has no way to reach. `sf org display --target-org <alias>` inside the
  container fails with `NamedOrgNotFoundError: No authorization
  information found for <alias>` regardless of how the mount path is
  configured — this is an architecture limitation of the current CLI,
  not a path/typo to fix. `docker-compose.yml`'s `app.volumes` keeps the
  mount line commented out for reference only.

  **`cli` mode itself is completely fine outside Docker** — a
  host-installed venv (README.md's own setup path) reaches the OS
  keychain natively, so nothing here affects that workflow. The
  limitation is specific to reusing a host login *from inside a Linux
  container*.

## Inspecting the mirror DB

Three equally valid ways, same read-only spirit as `CLAUDE.md`'s own
"read-only eyes" guidance:

- From inside the container: `docker compose exec app sqlcmd -S sqlserver
  -U sa -P "$SQL_PWD" -C -d SF_Migration -Q "SELECT COUNT(*) FROM dbo.Account;"`
  (`$SQL_PWD`, not `$MSSQL_SA_PASSWORD` — the latter is only set as a
  container-level environment variable on `sqlserver` itself, not on
  `app`; `app` only ever gets the derived `SQL_PWD`/`SQL_UID` values from
  `docker-compose.yml`'s own `environment:` block.)
- From the host, since port 1433 is published: a host-installed `sqlcmd`,
  Azure Data Studio, DBeaver, or SSMS (Windows) pointed at
  `localhost,1433` with the SQL login `sa` / your `MSSQL_SA_PASSWORD`.
- `docker compose exec app python cli.py query "SELECT ..."` for anything
  that's really a Salesforce SOQL query rather than a local SQL one.

## Why your `.env`'s own `SQL_*` values don't leak into the container

`docker-compose.yml`'s `app` service sets `SQL_SERVER=sqlserver` (and the
other `SQL_*` values matching the containerized SQL Server) directly in
its own `environment:` block. This wins over whatever's in your mounted
`.env` for two independent reasons: Compose's own documented precedence
(`environment:` beats `env_file:` when the same key appears in both), and
separately, `config.py`'s `load_dotenv()` call never overrides an
already-set OS environment variable either. Your real `.env`'s `SF_*` /
`MOCKAROO_API_KEY` / `TICKET_SYSTEM_*` values still load normally from the
mounted file — only the `SQL_*` connection settings are overridden, and
only for the containerized `app` service.

**One subtlety worth knowing**: `.env` is read by two *different*
mechanisms here, which happen to point at the same file today but are
worth telling apart if something doesn't pick up a value you expect.
Compose itself reads a file literally named `.env` in the same directory
as `docker-compose.yml` for its own `${VAR}` substitutions (that's how
`${MSSQL_SA_PASSWORD:?...}` gets its value, resolved when you run `docker
compose up`, from wherever you run that command). Separately, the `app`
service's `env_file: - .env` line loads that same file's contents into
the *container's* process environment at start time (that's how `SF_*`
etc. reach `config.py`'s own `load_dotenv()` call). If you ever rename
your env file or run `docker compose` from a different working
directory, these two can diverge in confusing ways — keep `.env` at the
repo root and run `docker compose` from there, same as every other
command in this repo already assumes.

## What this doesn't (yet) do

- No SQLite-backend container variant — `SQL_BACKEND=sqlite` needs no
  server at all (see README.md's "SQL backend" section), so there's
  nothing for Docker to add there; run it directly in a plain Python venv
  as documented, container or not.
- PostgreSQL as a second database option (roadmap #69) isn't built yet —
  once it lands, this compose file is the natural place to add a
  `postgres` service alongside (or instead of) `sqlserver`.
- No production deployment story here — `MSSQL_PID: Developer` in
  `docker-compose.yml` is explicitly the free, non-production edition,
  matching this framework's own dev/practice framing throughout
  `CLAUDE.md`.
- `app` runs as root inside its own container — a deliberate
  simplification for a local-only dev tool, not an oversight. The
  bind-mounted repo already means the container can read/write your host
  filesystem at that one path regardless of the in-container user, and
  adding a non-root user here would trade that away for the classic
  bind-mount UID/GID mismatch headache (files created in the container
  owned by an ID that doesn't match your host user) for no real
  additional isolation in this specific setup. Worth revisiting if this
  ever needs to run somewhere less trusted than a developer's own
  machine.
