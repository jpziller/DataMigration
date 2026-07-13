# Local dev environment (roadmap #68) -- packages the exact same
# architecture documented in README.md's "One-time environment setup"
# (Python + pyodbc + ODBC Driver 18 + sqlcmd + the Salesforce CLI), not a
# different one. See docker-compose.yml and docs/DOCKER.md for how this
# is actually run; this file only builds the `app` image.
FROM python:3.12-slim-bookworm

# Microsoft ODBC Driver 18 for SQL Server + mssql-tools18 (sqlcmd) --
# pyodbc (every mssql-backend command in this repo) needs the driver at
# runtime; sqlcmd lets CLAUDE.md's own "look at SQL Server directly"
# read-only workflow work inside this container too, not just on a host
# Windows machine with SSMS. unixodbc-dev provides both the ODBC driver
# manager pyodbc links against and its headers (a source build fallback
# if no prebuilt pyodbc wheel matches this exact image).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg2 unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -sSL https://packages.microsoft.com/config/debian/12/prod.list \
        | sed 's#deb #deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] #' \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 mssql-tools18 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="$PATH:/opt/mssql-tools18/bin"

# Salesforce CLI -- only needed for SF_AUTH_MODE=cli (reusing an org
# already authed on the HOST via `sf org login web`; see docs/DOCKER.md
# for the ~/.sf volume mount that requires). jwt/password mode
# (sf_client.py's connect_salesforce()) never shells out to this binary
# at all, so it's fine to skip auth setup for this binary entirely on
# those two modes.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
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
