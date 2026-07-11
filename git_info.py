"""Shared git-repo introspection: current commit/branch, and (if a GitHub
remote exists) the base URL for building blob/tree links. Used by both
migration_run_book.py and mapping_doc.py so every "jump to this file at
this commit" breadcrumb hyperlink across the project is built the same
way, from one place.
"""
import os
import re
import subprocess

_REPO_ROOT = os.path.dirname(__file__)

_GITHUB_HTTPS_RE = re.compile(r"^https?://github\.com/([^/]+)/(.+?)(\.git)?/?$")
_GITHUB_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/(.+?)(\.git)?$")


def get_git_info():
    """Best-effort {"remote_url", "commit_sha", "branch"} for this repo, or
    None on any failure (no git on PATH, not a repo, no "origin" remote) --
    callers just leave a breadcrumb blank rather than erroring out over it."""
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return None
    if not remote or not sha:
        return None
    return {"remote_url": remote, "commit_sha": sha, "branch": branch}


def github_url(remote_url):
    """Normalize a GitHub remote (https or SSH form) to
    https://github.com/owner/repo, or None for any other host -- a v1
    limitation, documented in ROADMAP.md, not silently wrong."""
    if not remote_url:
        return None
    for pattern in (_GITHUB_HTTPS_RE, _GITHUB_SSH_RE):
        m = pattern.match(remote_url)
        if m:
            return f"https://github.com/{m.group(1)}/{m.group(2)}"
    return None
