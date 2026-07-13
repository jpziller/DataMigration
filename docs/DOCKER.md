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

Three services, defined in `docker-compose.yml`:

- **`sqlserver`** — SQL Server 2022, Developer Edition (free, full-featured,
  non-production use only — same edition README.md's own step 4 already
  recommends). Data persists in a named volume (`sqlserver_data`) across
  `docker compose down`/`up`; `docker compose down -v` wipes it.
- **`sqlserver-init`** — a one-shot container that creates the empty
  `SF_Migration` database (or whatever `SQL_DATABASE` is set to) once
  `sqlserver` reports healthy, then exits. Idempotent — safe on every
  `docker compose up`. See `docker/init-db.sh`.
- **`app`** — this repo's Python environment: `requirements.txt` already
  installed, plus the Microsoft ODBC Driver 18 for SQL Server, `sqlcmd`
  (`mssql-tools18`), and the Salesforce CLI (`sf`), all preinstalled (see
  `Dockerfile`). The repo itself is **bind-mounted**, not copied into the
  image — edits on your host are reflected immediately, no rebuild needed
  for a Python/SQL file change (only for a `requirements.txt` change).

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + the Compose plugin
  (Linux) — this setup uses Compose v2 syntax (`condition:
  service_healthy` / `service_completed_successfully`), not the older
  standalone `docker-compose` v1.
- A `.env` file (`copy .env.example .env`, same as README.md's step 13),
  with **`MSSQL_SA_PASSWORD`** set to a strong password (8+ characters,
  upper+lower+digit+symbol — SQL Server rejects a weak one at container
  startup) and your normal `SF_*` auth values filled in.

## Quickstart

```bash
docker compose up -d          # builds the app image, starts sqlserver,
                               # runs sqlserver-init, then starts app
docker compose exec app python cli.py list-objects
docker compose exec app python cli.py describe Account
docker compose exec app python cli.py replicate Account
```

Every command in `CLAUDE.md`'s "Canonical commands" section works the
same way — prefix it with `docker compose exec app` instead of
`.venv/Scripts/python.exe`. For an interactive shell inside the container
instead of one-off commands:

```bash
docker compose exec app bash
```

## Choosing a Salesforce auth mode inside the container

`SF_AUTH_MODE` (from your mounted `.env`, per `sf_client.py`) works
differently here than on a host machine:

- **`jwt` (recommended for this setup)** — pure Python, no browser, no
  shelling out to the `sf` binary at all (`connect_salesforce()` calls
  `simple_salesforce`'s own JWT bearer flow directly). Works immediately
  with zero extra container config: mount (or just keep) `server.key` at
  the repo root as usual — it's already inside the container via the
  bind mount.
- **`password`** — same story: pure Python, no `sf` CLI involved, works
  immediately.
- **`cli`** — reuses an org already authed via `sf org login web`, which
  needs a real browser and doesn't work headlessly inside the container.
  The workaround: run `sf org login web --alias ...` **on your host**
  (normal browser flow, exactly like README.md's step 8), then mount your
  host's `sf` CLI config directory into the container so the *already-
  authenticated* org is reusable from inside it. Uncomment the relevant
  line in `docker-compose.yml`'s `app.volumes` and adjust for your OS:
  ```yaml
  # Windows
  - ${USERPROFILE}/.sf:/root/.sf
  # Mac/Linux
  - ${HOME}/.sf:/root/.sf
  ```
  Then `docker compose up -d` again to pick up the new mount. If `sf org
  display --target-org <alias>` fails inside the container
  (`docker compose exec app sf org display --target-org YOUR_ALIAS`),
  double-check the mounted path actually matches where your `sf` install
  stores auth data (verify on the host with `sf config get target-org`
  after a successful login, since the exact directory has changed across
  CLI versions).

## Inspecting the mirror DB

Three equally valid ways, same read-only spirit as `CLAUDE.md`'s own
"read-only eyes" guidance:

- From inside the container: `docker compose exec app sqlcmd -S sqlserver
  -U sa -P "$MSSQL_SA_PASSWORD" -C -d SF_Migration -Q "SELECT COUNT(*) FROM dbo.Account;"`
- From the host, since port 1433 is published: a host-installed `sqlcmd`,
  Azure Data Studio, DBeaver, or SSMS (Windows) pointed at
  `localhost,1433` with the SQL login `sa` / your `MSSQL_SA_PASSWORD`.
- `docker compose exec app python cli.py query "SELECT ..."` for anything
  that's really a Salesforce SOQL query rather than a local SQL one.

## Why `cli`/password/JWT env values in `.env` don't leak into the
container's SQL connection

`docker-compose.yml`'s `app` service sets `SQL_SERVER=sqlserver` (and the
other `SQL_*` values matching the containerized SQL Server) directly in
its own `environment:` block, which takes priority over whatever's in
your mounted `.env` file — `config.py`'s `load_dotenv()` call (via
`python-dotenv`) never overrides an already-set OS environment variable,
which is exactly what Compose's `environment:` block sets before the
container's Python process ever starts. Your real `.env`'s `SF_*` /
`MOCKAROO_API_KEY` / `TICKET_SYSTEM_*` values still load normally from
the mounted file — only the `SQL_*` connection settings are overridden,
and only for the containerized `app` service.

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
