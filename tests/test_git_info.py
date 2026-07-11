import git_info as gi


def test_github_url_normalizes_https_form():
    assert gi.github_url("https://github.com/jpziller/DataMigration") == "https://github.com/jpziller/DataMigration"


def test_github_url_normalizes_https_form_with_dot_git_suffix():
    assert gi.github_url("https://github.com/jpziller/DataMigration.git") == "https://github.com/jpziller/DataMigration"


def test_github_url_normalizes_ssh_form():
    assert gi.github_url("git@github.com:jpziller/DataMigration.git") == "https://github.com/jpziller/DataMigration"


def test_github_url_returns_none_for_non_github_remote():
    assert gi.github_url("https://gitlab.com/jpziller/DataMigration") is None


def test_github_url_returns_none_for_empty_remote():
    assert gi.github_url("") is None
    assert gi.github_url(None) is None


def test_get_git_info_returns_expected_keys_against_real_repo():
    info = gi.get_git_info()
    # This test suite runs inside a real git repo with an origin remote --
    # confirms the happy path end-to-end rather than only the pure regex
    # logic above.
    assert info is not None
    assert set(info.keys()) == {"remote_url", "commit_sha", "branch"}
    assert info["commit_sha"]
