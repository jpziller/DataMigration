# Local dev environment (roadmap #68) -- packages the exact same
# architecture documented in README.md's "One-time environment setup"
# (Python + pyodbc + ODBC Driver 18 + sqlcmd + the Salesforce CLI), not a
# different one. See docker-compose.yml and docs/DOCKER.md for how this
# is actually run; this file only builds the `app` image.
FROM python:3.12-slim-bookworm

# Prevents apt-get from ever blocking on an unexpected interactive prompt
# during an automated build (e.g. a transitive dependency pulling in
# tzdata's own debconf prompt) -- a real risk otherwise, not a
# hypothetical one, since ACCEPT_EULA below only covers the two packages
# that specifically check for it.
ENV DEBIAN_FRONTEND=noninteractive

# Microsoft ODBC Driver 18 for SQL Server + mssql-tools18 (sqlcmd) --
# pyodbc (every mssql-backend command in this repo) needs the driver at
# runtime; sqlcmd lets CLAUDE.md's own "look at SQL Server directly"
# read-only workflow work inside this container too, not just on a host
# Windows machine with SSMS. unixodbc-dev provides both the ODBC driver
# manager pyodbc links against and its headers (a source build fallback
# if no prebuilt pyodbc wheel matches this exact image). `gnupg` (not
# `gnupg2` -- Debian merged the two packages long ago, and the
# transitional `gnupg2` package name is not reliably present across every
# Debian release) provides `gpg` for the apt keyring step below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 mssql-tools18 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="$PATH:/opt/mssql-tools18/bin"

# Salesforce CLI -- installed so it's available for ad hoc use (e.g. `sf
# project deploy start` for Hard Rule 8's field-security-bundled deploys)
# via its own fresh `sf org login jwt`/`sf org login web` inside the
# container. This framework's OWN SF_AUTH_MODE=jwt/password
# (sf_client.py's connect_salesforce()) never shells out to this binary
# at all -- only SF_AUTH_MODE=cli does, and that mode does NOT work here:
# confirmed live, current `sf` CLI versions store org auth in the host
# OS's own keychain (Windows Credential Manager / macOS Keychain /
# libsecret), not a plaintext file under ~/.sf, so there's nothing a
# Linux container can reach by reusing a HOST-authenticated session no
# matter how that directory is mounted. See docs/DOCKER.md's auth-mode
# section for the full finding.
#
# Deliberately uses NodeSource's own setup script for a current Node LTS,
# NOT Debian's default `nodejs`/`npm` apt packages -- found in review:
# distro-packaged Node lags behind current releases, and Salesforce's own
# CLI install docs specifically warn against relying on it for exactly
# this reason (a future `sf` CLI bump past whatever Node version bookworm
# ships would otherwise silently break `cli` auth mode). Pin the major
# version here deliberately rather than always tracking "current" --
# bump it the same deliberate way any other pinned dependency in this
# repo would be. Node 20 was correct when this pin was first written, but
# is stale now: a current `sf` CLI's bundled undici calls
# worker_threads.markAsUncloneable(), only added in Node v22.10.0, so
# Node 20 crashes on startup with "TypeError: webidl.util.
# markAsUncloneable is not a function" -- confirmed against Node's own
# release docs and Salesforce's 2026 guidance, which recommends Node 22
# (Maintenance LTS through ~April 2027) or 24 (current).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install --global @salesforce/cli \
    && rm -rf /var/lib/apt/lists/* /root/.npm

WORKDIR /app

# Only requirements.txt is copied at build time, for Docker layer caching
# -- the rest of the repo is bind-mounted at compose-up time (see
# docker-compose.yml), not baked into the image. This is a live local dev
# environment: edits on the host are reflected immediately, no rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["sleep", "infinity"]
