"""Read-only retrieval for the ``okf/`` knowledge bundle (ROADMAP.md #83).

``gather-okf`` surfaces the OKF docs relevant to the objects (or subject
area / cloud) in play, so a migration consults target-platform behavior
and external recipe sources **before** building -- the same "don't
rediscover it after a mistake" role ``validators_lookup.py`` plays for
``validators/``, and what the orchestrator gathers as part of an
assessment.

Reuses ``validators_lookup.parse_frontmatter()`` (the one OKF-aware
frontmatter parser in this repo) rather than re-implementing it, and its
``_RESERVED`` set so the bundle's ``index.md``/``log.md`` are never
surfaced as knowledge docs.
"""
import os
import re

from validators_lookup import parse_frontmatter, _RESERVED


def _norm(s):
    """Lowercase and strip to alphanumerics, so "GiftCommitment" matches
    both the tag "gift-commitment" and the title "GiftCommitmentSchedule
    ...", and "Nonprofit Cloud" matches the tag "nonprofit-cloud"."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _subject_area(path, okf_dir):
    rel = os.path.relpath(path, okf_dir)
    parts = rel.split(os.sep)
    return parts[0] if len(parts) > 1 else ""


def iter_okf_docs(okf_dir="okf"):
    """Yield ``(path, meta, body)`` for every non-reserved ``.md`` file in
    the bundle (skips ``index.md``/``log.md`` at any level)."""
    if not os.path.isdir(okf_dir):
        return
    for root, _dirs, files in os.walk(okf_dir):
        for f in sorted(files):
            if f.lower().endswith(".md") and f.lower() not in _RESERVED:
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fh:
                    meta, body = parse_frontmatter(fh.read())
                yield path, meta, body


def list_subject_areas(okf_dir="okf"):
    """Sorted list of ``okf/<area>/`` subject-area folder names, or []."""
    if not os.path.isdir(okf_dir):
        return []
    return sorted(
        d for d in os.listdir(okf_dir)
        if os.path.isdir(os.path.join(okf_dir, d))
    )


def gather_okf(objects=None, subject_area=None, okf_dir="okf"):
    """Return a list of matching OKF docs, most-specific match first.

    Each result is a dict: ``{path, subject_area, meta, matched_on}``.

    - ``objects``: match any of these against a doc's title / description /
      tags (normalized substring -- see :func:`_norm`). A doc is included
      only if at least one object matches.
    - ``subject_area``: restrict to that ``okf/<area>/`` folder; with no
      ``objects`` given, lists every doc in the area.
    - neither given: returns every non-reserved doc (the full catalog).

    Body text is deliberately NOT part of the match -- title/description/
    tags are the curated, high-signal fields, and matching the body would
    surface a doc for any object it merely mentions in passing.
    """
    objects = [o for o in (objects or []) if o and str(o).strip()]
    norm_objects = [(o, _norm(o)) for o in objects]
    norm_objects = [(o, n) for o, n in norm_objects if n]
    sa = subject_area.strip().lower() if subject_area else None

    results = []
    for path, meta, _body in iter_okf_docs(okf_dir):
        area = _subject_area(path, okf_dir)
        if sa and area.lower() != sa:
            continue
        matched_on = []
        if norm_objects:
            tags = meta.get("tags") or []
            if not isinstance(tags, list):
                tags = [tags]
            hay = _norm(" ".join([
                str(meta.get("title", "")),
                str(meta.get("description", "")),
                " ".join(str(t) for t in tags),
            ]))
            for orig, no in norm_objects:
                if no in hay:
                    matched_on.append(orig)
            if not matched_on:
                continue
        elif sa:
            matched_on.append(f"subject-area:{area}")
        else:
            matched_on.append("all")
        results.append({
            "path": path.replace(os.sep, "/"),
            "subject_area": area,
            "meta": meta,
            "matched_on": matched_on,
        })

    def _specificity(r):
        real = [m for m in r["matched_on"]
                if not m.startswith("subject-area:") and m != "all"]
        return (-len(real), r["path"])

    results.sort(key=_specificity)
    return results
