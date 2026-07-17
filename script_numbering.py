"""Numbering helper for sql/transformations/ and sql/source_ingestion/.

Both folders use a shared convention: scripts are numbered in gaps of 10
(010, 020, 030, ...) rather than consecutively, specifically so a script
that needs to be inserted later between two that already exist (e.g. a
forgotten intermediate step) can take an unused number in that gap
(011-019) without renumbering anything already built and committed.

Purely advisory, like batch_advisor.py/auto_mapper.py's suggestions -- this
recommends a number, it never creates, renames, or renumbers a file itself.
"""
import os
import re

_SCRIPT_RE = re.compile(r"^(\d+)_")

DEFAULT_GAP = 10


def existing_numbers(directory):
    """Sorted list of numeric prefixes already used in directory. Empty if
    the directory doesn't exist yet or has no numbered scripts."""
    if not os.path.isdir(directory):
        return []
    numbers = []
    for f in os.listdir(directory):
        m = _SCRIPT_RE.match(f)
        if m:
            numbers.append(int(m.group(1)))
    return sorted(numbers)


def next_number(directory, after=None, before=None, gap=DEFAULT_GAP):
    """The next number to use for a new script in `directory`.

    With neither after nor before: the next top-level slot -- `gap` above
    the highest existing number (or `gap` itself if nothing exists yet).

    With both after and before given: an unused number strictly between
    them, for inserting a script into an existing gap. Prefers the number
    closest to the midpoint, so repeated insertions into the same gap
    spread out evenly instead of clustering at one end.
    """
    numbers = set(existing_numbers(directory))

    if after is None and before is None:
        if not numbers:
            return gap
        return max(numbers) + gap

    if after is None or before is None:
        raise ValueError(
            "Pass both after and before to insert between two existing "
            "scripts, or neither for the next top-level number."
        )
    if after >= before:
        raise ValueError(f"after ({after}) must be less than before ({before}).")

    free = [n for n in range(after + 1, before) if n not in numbers]
    if not free:
        raise ValueError(
            f"No free number between {after} and {before} -- every value in "
            "that range is already used, so renumbering is unavoidable here."
        )
    midpoint = (after + before) / 2
    return min(free, key=lambda n: abs(n - midpoint))


def format_number(n):
    """Zero-padded to at least 3 digits, matching this project's existing
    010/020/030 convention -- widens naturally past 999 if a project ever
    genuinely needs it (:03d only sets a minimum width, never truncates)."""
    return f"{n:03d}"


def matches_token(object_name, text_value):
    """Whole-token (delimiter-bounded) match, case-insensitive -- e.g.
    "Account" matches "010_account_load.sql" but "Order" does NOT match
    "030_orderitem_load.sql" (a naive substring check did, found in
    review: an Order log row/lookup would have matched the OrderItem
    script instead, and Order/OrderItem is exactly the pairing this
    project's own batch heuristics expect kept distinct). Underscore
    counts as a delimiter (required for the filename convention to match
    at all), which leaves one disclosed residual edge: "Quote" would still
    match inside "sbqq__quote__c_load.sql" since custom-object suffixes
    are underscore-delimited too. Shared by script_filename_for() below
    and migration_run_book.py's own row-matching logic, so the fix for
    one naturally covers the other instead of drifting apart again.

    A second, still-open residual edge (found live, NPSP-to-NPC migration
    proof-of-concept, not yet fixed here): a script filename for a
    COMPOUND object name that embeds another real object's name as its
    own delimiter-bounded word collides the same way. A file named
    "110_account_contact_relation_load.sql" (for AccountContactRelation)
    still matches a bare "Account" or "Contact" lookup, and -- since
    script_filename_for() below picks the highest-numbered match -- can
    silently outrank the real, unrelated "020_contact_load.sql" once its
    own number is higher. This surfaced as a real, silent bug: it broke
    migration_run_book.py's Load-phase Object-cell resolution for three
    different bare object names in one pass (Account, Contact, Campaign),
    caught only by the existing test suite failing, not by reasoning.
    Worked around in that project by removing the internal delimiter
    ("accountcontactrelation", "campaignmember", "giftcommitmentschedule",
    "gifttransactiondesignation") so the compound name can't accidentally
    match a shorter, unrelated object as a substring -- but that's a
    naming-convention workaround, not a fix to this matcher itself. A
    real fix would need script_filename_for() to know the full set of
    object names in play (not just the one it's currently resolving) so
    it can prefer a filename that matches ONLY the requested object over
    one that also matches a different, longer compound name -- not yet
    built. See ROADMAP.md for the full write-up. If you're naming a new
    script for an object whose name contains another real object's name
    as a whole word (AccountContactRelation, CampaignMember,
    GiftCommitmentSchedule, GiftTransactionDesignation, etc.), don't put
    an underscore between the embedded segments in the filename."""
    text_value = str(text_value)
    if object_name.lower() == text_value.strip().lower():
        return True
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(object_name)}(?![A-Za-z0-9])",
        text_value, re.IGNORECASE,
    ) is not None


def script_filename_for(object_name, directory):
    """The real script for object_name in directory (sql/transformations/
    or sql/source_ingestion/) -- when more than one matches (e.g. an old
    illustrative template alongside the real numbered script), the
    highest-numbered one wins, since this project's own numbering
    convention means "most recent"/"actually used" rather than
    alphabetically first. Filenames are zero-padded to the same width, so
    ascending string sort already puts the highest number last. Returns ""
    if directory doesn't exist or nothing matches -- callers decide
    whether that's an error (a step that requires the script to already
    exist) or just "nothing to link yet"."""
    if not os.path.isdir(directory):
        return ""
    matches = sorted(
        f for f in os.listdir(directory)
        if f.lower().endswith(".sql") and matches_token(object_name, f)
    )
    return matches[-1] if matches else ""
