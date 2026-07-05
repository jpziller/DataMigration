"""Salesforce connection.

Three auth modes (set SF_AUTH_MODE):
  cli      - reuse an org already authed via `sf org login web`. Instance URL
             comes from `sf org display --json`; the access token comes from
             `sf org auth show-access-token` because the May 27, 2026 CLI
             security update REDACTS the token from `sf org display`.
  jwt      - connected-app JWT bearer flow (no browser, good for CI).
  password - username + password + security token.
"""
import json
import subprocess
import os

from simple_salesforce import Salesforce

from config import Settings


def _run_sf(args):
    proc = subprocess.run(
        ["sf", *args, "--json"],
        capture_output=True, text=True, check=True,
        shell=(os.name == "nt"),
    )
    return json.loads(proc.stdout)


def _cli_credentials(alias):
    # instanceUrl is not a secret and is still returned in full.
    disp = _run_sf(["org", "display", "--target-org", alias])
    instance_url = disp["result"]["instanceUrl"]

    # Token is redacted from `org display` since the 2026 security update.
    # `--no-prompts` makes it non-interactive. NOTE: confirm the result shape
    # for your installed CLI version (some builds return the token as the raw
    # `result` value, others under result.accessToken).
    tok = _run_sf(["org", "auth", "show-access-token",
                   "--target-org", alias, "--no-prompt"])
    result = tok["result"]
    if isinstance(result, str):
        access_token = result
    else:
        access_token = result.get("accessToken") or result.get("access_token")
    if not access_token:
        raise RuntimeError(
            "Could not parse access token from `sf org auth show-access-token`. "
            f"Raw result: {result!r}"
        )
    return instance_url, access_token


def connect_salesforce(s: Settings) -> Salesforce:
    mode = s.sf_auth_mode.lower()
    if mode == "cli":
        instance_url, token = _cli_credentials(s.sf_org_alias)
        return Salesforce(instance_url=instance_url, session_id=token,
                          version=s.sf_api_version)
    if mode == "jwt":
        return Salesforce(username=s.sf_username,
                          consumer_key=s.sf_consumer_key,
                          privatekey_file=s.sf_private_key_file,
                          domain=s.sf_domain, version=s.sf_api_version)
    if mode == "password":
        return Salesforce(username=s.sf_username, password=s.sf_password,
                          security_token=s.sf_security_token,
                          domain=s.sf_domain, version=s.sf_api_version)
    raise ValueError(f"Unknown SF_AUTH_MODE: {s.sf_auth_mode}")
