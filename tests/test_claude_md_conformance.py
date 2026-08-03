"""CLAUDE.md conformance -- enforces the invariants in
docs/CONTEXT_DOC_STANDARDS.md *continuously in CI*, so a future edit that drops
a command, loses/renumbers a hard rule, removes a safety rule, or lets the
file balloon is caught here rather than only when someone remembers to run
/optimize-claude-md. This is the automated safety net behind the standard's
five invariants (the same "get ahead of drift" move as the leak-vector
catch-all test, applied to the operating manual)."""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CLAUDE_MD = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
_CLI_PY = (_ROOT / "cli.py").read_text(encoding="utf-8")

# Commands deliberately not required in CLAUDE.md go here, each with a reason.
# Empty today -- every cli.py command is currently documented.
_ALLOWLIST: dict[str, str] = {}

# Word ceiling: a CI forcing function so the file can't creep back to its
# pre-trim ~15.5k words. Generous headroom over the current ~9.3k; when a real
# addition pushes past it, run /optimize-claude-md rather than raising this.
_WORD_CEILING = 12000

# The safety-critical rules (standard invariant #2): a trim may compress but
# never remove these by name.
_SAFETY_RULES = [
    "Mirror-DB-Only",
    "Live-Org Write Confirmation",
    "Credential Non-Disclosure",
    "Email Deliverability Attestation",
    "Live Migration Key Validation",
]


def _cli_commands():
    return sorted(set(re.findall(r'@cli\.command\("([a-z0-9-]+)"\)', _CLI_PY)))


def test_every_cli_command_is_documented_in_claude_md():
    """Invariant #3 (automated): every CLI command appears in CLAUDE.md.
    Catches both drift directions -- a new command added without docs, and a
    trim that silently drops one."""
    missing = [c for c in _cli_commands()
               if c not in _ALLOWLIST and c not in _CLAUDE_MD]
    assert not missing, (
        f"{len(missing)} cli.py command(s) not mentioned in CLAUDE.md: {missing}. "
        "Document them in CLAUDE.md, or add to _ALLOWLIST with a reason.")


def test_all_fifteen_hard_rules_present_and_numbered():
    """Invariant #1: every hard rule keeps its number. The Hard rules section
    must contain a numbered entry 1..15."""
    section = _CLAUDE_MD.split("## Hard rules", 1)[1].split("## Validators library", 1)[0]
    for n in range(1, 16):
        assert re.search(rf'(?m)^{n}\. \*\*', section), f"Hard rule {n} missing or renumbered"


def test_safety_critical_rules_stay_explicit():
    """Invariant #2: the safety-critical rules must remain present by name."""
    for name in _SAFETY_RULES:
        assert name in _CLAUDE_MD, f"safety-critical rule missing from CLAUDE.md: {name!r}"


def test_claude_md_stays_within_word_budget():
    """The standard's 'keep it lean' as a CI forcing function."""
    words = len(_CLAUDE_MD.split())
    assert words <= _WORD_CEILING, (
        f"CLAUDE.md is {words} words (ceiling {_WORD_CEILING}). Run "
        "/optimize-claude-md per docs/CONTEXT_DOC_STANDARDS.md, or raise the "
        "ceiling deliberately if the growth is genuinely load-bearing.")
