"""Lookup helper for the validators library (see validators/README.md).

Purely a retrieval convenience -- reads whatever's already on disk under
validators/, never writes anything. Writing a new validator entry is
always a deliberate manual edit (or Claude editing the file directly),
same as every other git-tracked knowledge file in this project
(reference/field_synonyms.json, reference/batch_size_heuristics.json).
"""
import os

_SYSTEM_DIR = "system"


def list_system_validators(validators_dir="validators"):
    """Sorted list of system validator filenames (e.g.
    ["migration-key-integrity.md", ...]), or [] if the folder doesn't
    exist."""
    system_dir = os.path.join(validators_dir, _SYSTEM_DIR)
    if not os.path.isdir(system_dir):
        return []
    return sorted(f for f in os.listdir(system_dir) if f.lower().endswith(".md"))


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
