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
    """Path to validators/<object_name>.md, or None if it doesn't exist."""
    path = os.path.join(validators_dir, f"{object_name}.md")
    return path if os.path.isfile(path) else None


def read_object_validator(object_name, validators_dir="validators"):
    """Contents of validators/<object_name>.md, or None if it doesn't exist."""
    path = object_validator_path(object_name, validators_dir=validators_dir)
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()
