"""Central config, loaded from environment (.env)."""
import os
from dataclasses import dataclass
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

    # SQL Server
    sql_server: str = _get("SQL_SERVER", "localhost")
    sql_database: str = _get("SQL_DATABASE", "SF_Migration")
    sql_driver: str = _get("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    sql_trusted: str = _get("SQL_TRUSTED_CONNECTION", "yes")
    sql_uid: str = _get("SQL_UID", "")
    sql_pwd: str = _get("SQL_PWD", "")
    sql_encrypt: str = _get("SQL_ENCRYPT", "yes")
    sql_trust_cert: str = _get("SQL_TRUST_SERVER_CERT", "yes")

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
