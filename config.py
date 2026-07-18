"""Central config, loaded from environment (.env)."""
import os
from dataclasses import dataclass, replace
from dotenv import load_dotenv

load_dotenv()


def _get(key, default=None):
    v = os.getenv(key, default)
    return v.strip() if isinstance(v, str) else v


@dataclass
class Settings:
    # Salesforce
    sf_auth_mode: str = _get("SF_AUTH_MODE", "cli")
    sf_api_version: str = _get("SF_API_VERSION", "67.0")
    sf_org_alias: str = _get("SF_ORG_ALIAS", "")
    sf_username: str = _get("SF_USERNAME", "")
    sf_consumer_key: str = _get("SF_CONSUMER_KEY", "")
    sf_private_key_file: str = _get("SF_PRIVATE_KEY_FILE", "")
    sf_domain: str = _get("SF_DOMAIN", "login")
    sf_password: str = _get("SF_PASSWORD", "")
    sf_security_token: str = _get("SF_SECURITY_TOKEN", "")

    # SQL backend -- "mssql" (default), "sqlite", or "postgresql" (roadmap
    # #69). See sql_client.py/sql_dialect.py for what changes per backend.
    sql_backend: str = _get("SQL_BACKEND", "mssql")

    # SQL Server (sql_backend == "mssql")
    sql_server: str = _get("SQL_SERVER", "localhost")
    sql_database: str = _get("SQL_DATABASE", "SF_Migration")
    sql_driver: str = _get("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    sql_trusted: str = _get("SQL_TRUSTED_CONNECTION", "yes")
    sql_uid: str = _get("SQL_UID", "")
    sql_pwd: str = _get("SQL_PWD", "")
    sql_encrypt: str = _get("SQL_ENCRYPT", "yes")
    sql_trust_cert: str = _get("SQL_TRUST_SERVER_CERT", "yes")

    # PostgreSQL (sql_backend == "postgresql", roadmap #69) -- reuses
    # sql_server/sql_database/sql_uid/sql_pwd above (already
    # backend-generic names, not literally SQL-Server-specific); these two
    # are the only genuinely Postgres-specific settings.
    sql_port: str = _get("SQL_PORT", "5432")
    sql_postgres_sslmode: str = _get("SQL_POSTGRES_SSLMODE", "prefer")

    # SQLite (sql_backend == "sqlite"): sql_sqlite_dir holds one <schema>.db
    # file per schema in sql_sqlite_schemas, each ATTACHed under its own
    # schema name on every new connection -- see sql_client.make_engine().
    sql_sqlite_dir: str = _get("SQL_SQLITE_DIR", "./_sqlite")
    sql_sqlite_schemas: str = _get("SQL_SQLITE_SCHEMAS", "dbo")

    stage_dir: str = _get("STAGE_DIR", "./_stage")

    # Mockaroo (mock/demo data generation)
    mockaroo_api_key: str = _get("MOCKAROO_API_KEY", "")

    # Migration Run Book (roadmap #16) -- ticket-system project link shown in the
    # header block. Not a credential (no token, just a base URL/label) --
    # a per-project generate-migration-run-book/add-migration-run-book-pass CLI flag overrides
    # either of these.
    ticket_system_label: str = _get("TICKET_SYSTEM_LABEL", "JIRA")
    ticket_system_url: str = _get("TICKET_SYSTEM_URL", "")


def get_settings() -> Settings:
    s = Settings()
    os.makedirs(s.stage_dir, exist_ok=True)
    return s


# A real migration is a two-org problem (source org -> SQL -> target org),
# but SF_* settings above are a single flat set -- switching orgs meant
# hand-editing SF_ORG_ALIAS (and, for jwt/password mode, every credential
# field) in .env on every flip between source and target. resolve_org_settings()
# is the fix: define both orgs once in .env via a role suffix on any SF_*
# key (e.g. SF_ORG_ALIAS_SOURCE / SF_ORG_ALIAS_TARGET), then swap between
# them per-command with `--org source`/`--org target` (see cli.py's _ctx())
# instead of ever touching .env again. A role-suffixed key is optional per
# field -- only set the ones that actually differ between orgs (e.g. cli
# mode only ever needs to override SF_ORG_ALIAS_*; jwt/password mode can
# override SF_USERNAME_*/SF_CONSUMER_KEY_*/etc. too, since those orgs may
# use different connected apps entirely). Anything left unset falls back to
# the plain, unsuffixed value -- fully backward compatible with a
# single-org .env that predates this.
_SF_FIELD_ENV_KEYS = {
    "sf_auth_mode": "SF_AUTH_MODE",
    "sf_org_alias": "SF_ORG_ALIAS",
    "sf_username": "SF_USERNAME",
    "sf_consumer_key": "SF_CONSUMER_KEY",
    "sf_private_key_file": "SF_PRIVATE_KEY_FILE",
    "sf_domain": "SF_DOMAIN",
    "sf_password": "SF_PASSWORD",
    "sf_security_token": "SF_SECURITY_TOKEN",
}

ORG_ROLES = ("source", "target")


def resolve_org_settings(s: Settings, role: str) -> Settings:
    """Return a copy of s with sf_* fields overridden by any role-suffixed
    SF_<FIELD>_<ROLE> env var that's set, falling back to the base
    SF_<FIELD> value for any field left unsuffixed. role must be "source"
    or "target". Read live from os.environ (not from s's already-resolved
    fields), since role isn't known until a command actually runs."""
    if role not in ORG_ROLES:
        raise ValueError(f"Unknown org role: {role!r} (expected one of {ORG_ROLES})")
    role_suffix = role.upper()
    overrides = {}
    for field, env_key in _SF_FIELD_ENV_KEYS.items():
        role_value = _get(f"{env_key}_{role_suffix}")
        if role_value:
            overrides[field] = role_value
    return replace(s, **overrides)


# Which sf_* fields actually matter for each auth mode -- used only by
# partial_override_warnings() below, never by resolve_org_settings()
# itself (connect_salesforce() in sf_client.py is the real source of
# truth for which fields each mode reads; this is a lighter-weight,
# advisory-only mirror of that, not a duplicate enforcement point).
_AUTH_MODE_RELEVANT_FIELDS = {
    "cli": ["sf_org_alias"],
    "jwt": ["sf_username", "sf_consumer_key", "sf_private_key_file", "sf_domain"],
    "password": ["sf_username", "sf_password", "sf_security_token", "sf_domain"],
}


def partial_override_warnings(resolved: Settings, role: str) -> list:
    """Field names relevant to resolved's own (possibly role-overridden)
    sf_auth_mode that this role left falling back to the base,
    unsuffixed value instead of a role-specific SF_<FIELD>_<ROLE>
    override -- found in review: resolve_org_settings()'s per-field
    fallback means a partially-configured role override (e.g.
    SF_ORG_ALIAS_TARGET and SF_AUTH_MODE_TARGET=jwt set, but
    SF_CONSUMER_KEY_TARGET/SF_PRIVATE_KEY_FILE_TARGET left unset) can
    silently produce an internally-inconsistent credential hybrid --
    still pointed at source's own connected app -- with no error and
    nothing in cli.py's own `[org: ...]` echo to reveal it.

    Deliberately advisory, not a hard gate, and deliberately not folded
    into resolve_org_settings() itself (whose own return type and every
    existing caller/test stays exactly as it was) -- call this
    separately, after resolving, only where a human-facing warning
    actually helps (see cli.py's _ctx()). A field showing up here isn't
    necessarily wrong -- e.g. two orgs might deliberately share one
    connected app -- so word any surfaced warning as "confirm this is
    intentional," not "this is broken." Returns [] when every field
    relevant to the resolved auth mode has its own role-specific
    override, or when the resolved auth mode isn't one of "cli"/"jwt"/
    "password" (an unrecognized mode is connect_salesforce()'s own error
    to raise, not this function's job to flag)."""
    role_suffix = role.upper()
    relevant = _AUTH_MODE_RELEVANT_FIELDS.get(resolved.sf_auth_mode, [])
    return [
        field for field in relevant
        if not _get(f"{_SF_FIELD_ENV_KEYS[field]}_{role_suffix}")
    ]
