"""OKF v0.1 conformance guard for this repo's shipped knowledge bundles
(ROADMAP.md #72): validators/ and okf/.

Deliberately different in kind from every other test here: it reads the
REAL committed tree, not tmp_path fixtures, because the thing under test
is shipped template content -- the same "always committed, identical
whoever clones this repo" class as reference/*.json. Without this, OKF
conformance regresses silently the first time someone adds a validator
without frontmatter; with it, the spec's own conformance rule (SPEC.md
section 9: every non-reserved .md parses with a non-empty `type`) is an
executable CI gate instead of a convention.
"""
from pathlib import Path

import pytest

import validators_lookup as vl

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_ROOTS = ("validators", "okf")
# Reused from validators_lookup.py itself, not redefined -- found in
# review: a second, independent copy here could drift silently if a
# third reserved filename is ever added to the module this test is
# supposed to be gating.
_RESERVED = vl._RESERVED


def _concept_files(bundle_root):
    return sorted(
        p for p in bundle_root.rglob("*.md") if p.name.lower() not in _RESERVED
    )


def _reserved_files(bundle_root):
    return sorted(
        p for p in bundle_root.rglob("*.md") if p.name.lower() in _RESERVED
    )


def test_validators_bundle_always_exists():
    assert (_REPO_ROOT / "validators").is_dir(), "validators/ should always exist in this repo"


@pytest.mark.parametrize("bundle_name", _BUNDLE_ROOTS)
def test_every_concept_file_has_frontmatter_with_type(bundle_name):
    bundle_root = _REPO_ROOT / bundle_name
    if not bundle_root.is_dir():
        pytest.skip(f"{bundle_name}/ bundle not built yet")
    concepts = _concept_files(bundle_root)
    assert concepts, f"{bundle_name}/ exists but holds no concept files"
    for path in concepts:
        meta, _ = vl.parse_frontmatter(path.read_text(encoding="utf-8"))
        rel = path.relative_to(_REPO_ROOT)
        assert meta, f"{rel} has no parseable YAML frontmatter"
        assert isinstance(meta.get("type"), str) and meta["type"].strip(), (
            f"{rel} frontmatter is missing a non-empty `type` (OKF's one "
            "required field)"
        )


@pytest.mark.parametrize("bundle_name", _BUNDLE_ROOTS)
def test_reserved_files_carry_no_frontmatter_except_root_okf_version(bundle_name):
    bundle_root = _REPO_ROOT / bundle_name
    if not bundle_root.is_dir():
        pytest.skip(f"{bundle_name}/ bundle not built yet")
    for path in _reserved_files(bundle_root):
        meta, _ = vl.parse_frontmatter(path.read_text(encoding="utf-8"))
        rel = path.relative_to(_REPO_ROOT)
        if path.name.lower() == "index.md" and path.parent == bundle_root:
            # The one spec-sanctioned exception: the bundle-root index.md
            # MAY declare the OKF version, and nothing else.
            assert set(meta) <= {"okf_version"}, (
                f"{rel} may only carry `okf_version` frontmatter, found: {sorted(meta)}"
            )
        else:
            assert meta == {}, (
                f"{rel} is an OKF reserved file and must not carry frontmatter"
            )


def test_no_reserved_files_inside_validators_system():
    """index.md/log.md belong at the bundle root only -- one placed in
    validators/system/ would previously have been announced as a system
    validator by list_system_validators() (now excluded defensively, but
    the file still shouldn't exist there at all)."""
    system_dir = _REPO_ROOT / "validators" / "system"
    stray = [p.name for p in system_dir.glob("*.md") if p.name.lower() in _RESERVED]
    assert stray == [], f"OKF reserved files found in validators/system/: {stray}"
