"""Coverage for config.py's two-org role overlay (resolve_org_settings) --
built to remove the friction of hand-editing .env's single SF_ORG_ALIAS on
every flip between a migration's source and target org. Settings() itself
resolves its defaults once at class-definition time (module import), so
these tests build Settings instances directly via explicit kwargs rather
than relying on env at import time -- only resolve_org_settings()'s own
role-suffixed lookups are read live, via monkeypatch.
"""
import pytest

from config import Settings, resolve_org_settings, partial_override_warnings


def _base_settings(**overrides):
    fields = dict(
        sf_auth_mode="cli", sf_api_version="67.0", sf_org_alias="BASE_ALIAS",
        sf_username="base_user", sf_consumer_key="", sf_private_key_file="",
        sf_domain="login", sf_password="", sf_security_token="",
    )
    fields.update(overrides)
    return Settings(**fields)


def test_resolve_org_settings_falls_back_to_base_when_no_role_suffix_set(monkeypatch):
    monkeypatch.delenv("SF_ORG_ALIAS_SOURCE", raising=False)
    s = _base_settings()
    resolved = resolve_org_settings(s, "source")
    assert resolved.sf_org_alias == "BASE_ALIAS"
    assert resolved.sf_auth_mode == "cli"


def test_resolve_org_settings_overrides_only_role_suffixed_fields(monkeypatch):
    monkeypatch.setenv("SF_ORG_ALIAS_TARGET", "NPC_TARGET_v2")
    s = _base_settings()
    resolved = resolve_org_settings(s, "target")
    assert resolved.sf_org_alias == "NPC_TARGET_v2"
    # untouched fields fall back to the base value unchanged
    assert resolved.sf_username == "base_user"
    assert resolved.sf_auth_mode == "cli"


def test_resolve_org_settings_source_and_target_are_independent(monkeypatch):
    monkeypatch.setenv("SF_ORG_ALIAS_SOURCE", "NPSP_SOURCE")
    monkeypatch.setenv("SF_ORG_ALIAS_TARGET", "NPC_TARGET_v2")
    s = _base_settings()
    source = resolve_org_settings(s, "source")
    target = resolve_org_settings(s, "target")
    assert source.sf_org_alias == "NPSP_SOURCE"
    assert target.sf_org_alias == "NPC_TARGET_v2"
    # the original Settings instance is never mutated
    assert s.sf_org_alias == "BASE_ALIAS"


def test_resolve_org_settings_can_override_auth_mode_and_credentials(monkeypatch):
    """Two orgs can use entirely different auth modes -- e.g. an
    interactively-authed cli-mode source alongside a jwt-mode target
    running headless for CI."""
    monkeypatch.setenv("SF_AUTH_MODE_TARGET", "jwt")
    monkeypatch.setenv("SF_USERNAME_TARGET", "target_user@example.com")
    monkeypatch.setenv("SF_CONSUMER_KEY_TARGET", "3MVG9...")
    s = _base_settings()
    resolved = resolve_org_settings(s, "target")
    assert resolved.sf_auth_mode == "jwt"
    assert resolved.sf_username == "target_user@example.com"
    assert resolved.sf_consumer_key == "3MVG9..."


def test_resolve_org_settings_rejects_unknown_role():
    s = _base_settings()
    with pytest.raises(ValueError, match="Unknown org role"):
        resolve_org_settings(s, "staging")


def test_partial_override_warnings_empty_when_cli_alias_fully_overridden(monkeypatch):
    monkeypatch.setenv("SF_ORG_ALIAS_TARGET", "NPC_TARGET_v2")
    s = _base_settings()
    resolved = resolve_org_settings(s, "target")
    assert partial_override_warnings(resolved, "target") == []


def test_partial_override_warnings_flags_incomplete_jwt_override(monkeypatch):
    """Found in review: this is the exact real scenario
    test_resolve_org_settings_can_override_auth_mode_and_credentials above
    already exercises -- SF_AUTH_MODE_TARGET=jwt plus username/consumer
    key, but no SF_PRIVATE_KEY_FILE_TARGET/SF_DOMAIN_TARGET -- silently
    falling back to the base (likely source-org) private key file and
    domain."""
    monkeypatch.setenv("SF_AUTH_MODE_TARGET", "jwt")
    monkeypatch.setenv("SF_USERNAME_TARGET", "target_user@example.com")
    monkeypatch.setenv("SF_CONSUMER_KEY_TARGET", "3MVG9...")
    s = _base_settings()
    resolved = resolve_org_settings(s, "target")
    assert partial_override_warnings(resolved, "target") == ["sf_private_key_file", "sf_domain"]


def test_partial_override_warnings_empty_when_jwt_fully_overridden(monkeypatch):
    monkeypatch.setenv("SF_AUTH_MODE_TARGET", "jwt")
    monkeypatch.setenv("SF_USERNAME_TARGET", "target_user@example.com")
    monkeypatch.setenv("SF_CONSUMER_KEY_TARGET", "3MVG9...")
    monkeypatch.setenv("SF_PRIVATE_KEY_FILE_TARGET", "./target-server.key")
    monkeypatch.setenv("SF_DOMAIN_TARGET", "login")
    s = _base_settings()
    resolved = resolve_org_settings(s, "target")
    assert partial_override_warnings(resolved, "target") == []


def test_partial_override_warnings_unrecognized_auth_mode_returns_empty(monkeypatch):
    s = _base_settings(sf_auth_mode="sso")
    resolved = resolve_org_settings(s, "target")
    assert partial_override_warnings(resolved, "target") == []
