"""Coverage for cli.py's own pure helper functions -- this project has
never unit-tested cli.py directly before (every command is dogfooded
live instead), but _parse_object_value_pairs() is a pure, reusable
utility with no Salesforce/SQL dependency, so it's worth testing in
isolation rather than only through a live command invocation.
"""
import pytest
from click.testing import CliRunner

import cli as cli_module
from cli import _parse_object_value_pairs, cli


def test_parse_object_value_pairs_basic():
    result = _parse_object_value_pairs(["Account=Account_Load", "Contact=Contact_Load"], "--load-table")
    assert result == {"Account": "Account_Load", "Contact": "Contact_Load"}


def test_parse_object_value_pairs_empty():
    assert _parse_object_value_pairs([], "--load-table") == {}


def test_parse_object_value_pairs_rejects_malformed_entry():
    with pytest.raises(Exception, match="--load-table must be Object=Value"):
        _parse_object_value_pairs(["AccountAccount_Load"], "--load-table")


def test_parse_object_value_pairs_rejects_duplicate_object():
    """Found in review: this exact silent-overwrite-on-duplicate-key bug
    was already fixed once for --scenario; --load-table/--migration-key
    had the identical gap at 4 separate call sites before being
    consolidated into this shared helper."""
    with pytest.raises(Exception, match="'Account' was given more than once"):
        _parse_object_value_pairs(["Account=Account_Load", "Account=Account_LoadV2"], "--load-table")


def test_parse_object_value_pairs_uses_option_name_in_error():
    with pytest.raises(Exception, match="--migration-key must be Object=Value"):
        _parse_object_value_pairs(["BadEntry"], "--migration-key")


def _stub_connect_and_engine(monkeypatch, captured):
    """Replaces the two live-connection calls _ctx() makes with stubs that
    record the Settings actually passed, and stubs list-objects' own
    metadata.list_objects() call so the command runs end-to-end under
    CliRunner without a real Salesforce/SQL connection."""
    def fake_connect_salesforce(s):
        captured["settings"] = s
        return object()

    monkeypatch.setattr(cli_module, "connect_salesforce", fake_connect_salesforce)
    monkeypatch.setattr(cli_module, "make_engine", lambda s: object())
    monkeypatch.setattr(cli_module.md, "list_objects", lambda sf, queryable_only=True: [])


def test_global_org_flag_resolves_source_role(monkeypatch):
    """--org source threads through _ctx() into resolve_org_settings(),
    picking up SF_ORG_ALIAS_SOURCE instead of the plain .env SF_ORG_ALIAS --
    the actual fix for the two-org (source -> target) config friction."""
    monkeypatch.setenv("SF_ORG_ALIAS_SOURCE", "NPSP_SOURCE")
    captured = {}
    _stub_connect_and_engine(monkeypatch, captured)

    result = CliRunner().invoke(cli, ["--org", "source", "list-objects"])

    assert result.exit_code == 0, result.output
    assert captured["settings"].sf_org_alias == "NPSP_SOURCE"


def test_global_org_alias_flag_overrides_everything(monkeypatch):
    """--org-alias is a raw one-off override -- beats both --org and .env,
    for a quick check against a third org without touching config at all."""
    monkeypatch.setenv("SF_ORG_ALIAS_SOURCE", "NPSP_SOURCE")
    captured = {}
    _stub_connect_and_engine(monkeypatch, captured)

    result = CliRunner().invoke(
        cli, ["--org", "source", "--org-alias", "SCRATCH_ORG", "list-objects"]
    )

    assert result.exit_code == 0, result.output
    assert captured["settings"].sf_org_alias == "SCRATCH_ORG"


def test_global_org_flag_warns_on_partial_jwt_override(monkeypatch):
    """Found in review: a role-suffixed auth-mode override without its
    own full credential set silently falls back to the base org's
    credentials -- _ctx() now surfaces this instead of staying silent."""
    monkeypatch.setenv("SF_AUTH_MODE_TARGET", "jwt")
    monkeypatch.setenv("SF_USERNAME_TARGET", "target_user@example.com")
    monkeypatch.setenv("SF_CONSUMER_KEY_TARGET", "3MVG9...")
    captured = {}
    _stub_connect_and_engine(monkeypatch, captured)

    result = CliRunner().invoke(cli, ["--org", "target", "list-objects"])

    assert result.exit_code == 0, result.output
    assert "sf_private_key_file" in result.output
    assert "not set for this role" in result.output


def test_global_org_flag_no_warning_when_fully_overridden(monkeypatch):
    monkeypatch.setenv("SF_ORG_ALIAS_TARGET", "NPC_TARGET_v2")
    captured = {}
    _stub_connect_and_engine(monkeypatch, captured)

    result = CliRunner().invoke(cli, ["--org", "target", "list-objects"])

    assert result.exit_code == 0, result.output
    assert "not set for this role" not in result.output


def test_no_org_flag_leaves_settings_unchanged(monkeypatch):
    """Omitting --org/--org-alias entirely must behave exactly as before
    this feature existed -- plain .env settings, no role resolution."""
    monkeypatch.delenv("SF_ORG_ALIAS_SOURCE", raising=False)
    monkeypatch.delenv("SF_ORG_ALIAS_TARGET", raising=False)
    captured = {}
    _stub_connect_and_engine(monkeypatch, captured)

    result = CliRunner().invoke(cli, ["list-objects"])

    assert result.exit_code == 0, result.output
    from config import get_settings
    assert captured["settings"].sf_org_alias == get_settings().sf_org_alias
