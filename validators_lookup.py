"""Lookup helper for the validators library (see validators/README.md).

Purely a retrieval convenience -- reads whatever's already on disk under
validators/, never writes anything. Writing a new validator entry is
always a deliberate manual edit (or Claude editing the file directly),
same as every other git-tracked knowledge file in this project
(reference/field_synonyms.json, reference/batch_size_heuristics.json).

The library is an Open Knowledge Format (OKF) v0.1 bundle (ROADMAP.md
#72): every non-reserved .md file carries YAML frontmatter with a `type`
field, and `index.md`/`log.md` are OKF reserved filenames (directory
listing / change history) that live at the bundle root only, never in
system/. parse_frontmatter() is the one OKF-aware piece here -- per the
spec's own conformance rules it tolerates absent or unparseable
frontmatter rather than rejecting a document.
"""
import os

import yaml

_SYSTEM_DIR = "system"

# OKF reserved filenames (SPEC.md section 3.1) -- never concept documents,
# so never listed as validators even if one strays into system/.
_RESERVED = ("index.md", "log.md")


def parse_frontmatter(text):
    """(meta, body) from a markdown string.

    meta is the dict parsed from a leading ``---``-fenced YAML frontmatter
    block, or {} when there is no block, the fence is unclosed, the YAML
    doesn't parse, or it parses to something other than a dict -- OKF
    consumers MUST tolerate all of those rather than reject the document
    (SPEC.md section 9). body is the text with the block stripped, or the
    original text unchanged whenever meta comes back {}.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", len("---\n") - 1)
    if end == -1:
        return {}, text
    try:
        meta = yaml.safe_load(text[len("---\n"):end])
    except yaml.YAMLError:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, text[end + len("\n---\n"):]


def list_system_validators(validators_dir="validators"):
    """Sorted list of system validator filenames (e.g.
    ["migration-key-integrity.md", ...]), or [] if the folder doesn't
    exist. OKF reserved filenames (index.md/log.md) are excluded -- they
    belong at the bundle root, but a stray one in system/ shouldn't get
    announced as a validator."""
    system_dir = os.path.join(validators_dir, _SYSTEM_DIR)
    if not os.path.isdir(system_dir):
        return []
    return sorted(
        f for f in os.listdir(system_dir)
        if f.lower().endswith(".md") and f.lower() not in _RESERVED
    )


def object_validator_path(object_name, validators_dir="validators"):
    """Path to validators/<object_name>.md, or None if it doesn't exist.

    object_name is expected to be a plain Salesforce object API name --
    rejected outright if it contains a path separator or ".." (found in
    review: unvalidated, this would let e.g.
    object_name="../../../etc/passwd" escape validators_dir via
    os.path.join(); low real-world severity today since every caller
    passes a CLI-argument object name, but cheap to close outright rather
    than lean on that being true forever)."""
    if not object_name or "/" in object_name or "\\" in object_name or ".." in object_name:
        raise ValueError(f"Invalid object name for validator lookup: {object_name!r}")
    path = os.path.join(validators_dir, f"{object_name}.md")
    return path if os.path.isfile(path) else None


def read_object_validator(object_name, validators_dir="validators"):
    """Contents of validators/<object_name>.md, or None if it doesn't exist."""
    path = object_validator_path(object_name, validators_dir=validators_dir)
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()
