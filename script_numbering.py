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

_KNOWN_SHORTCUTS = {
    "transformations": os.path.join("sql", "transformations"),
    "source_ingestion": os.path.join("sql", "source_ingestion"),
}


def resolve_dir(target_dir):
    """Resolve a --dir value to a real directory path. The two known
    shortcut keywords ("transformations", "source_ingestion") map to this
    project's own sql/ subfolders, exactly as every existing caller
    already expects. Anything else is treated as a literal path (relative
    to cwd, or absolute) -- e.g. "attempts/2026-07-21-npc-dogfood-v2/sql",
    a per-attempt workspace kept separate from the shared library (see
    CLAUDE.md's "Library vs. attempts workspace" section). Purely string
    logic -- doesn't check the path exists; callers already handle a
    missing/empty directory the same way they always have."""
    return _KNOWN_SHORTCUTS.get(target_dir, target_dir)


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

    A second, related residual edge (found live, NPSP-to-NPC migration
    proof-of-concept): a script filename for a COMPOUND object name that
    embeds another real object's name as its own delimiter-bounded word
    collides the same way. A file named "110_account_contact_relation_load.sql"
    (for AccountContactRelation) still matches a bare "Account" or
    "Contact" lookup, and -- since script_filename_for() below picks the
    highest-numbered match -- can silently outrank the real, unrelated
    "020_contact_load.sql" once its own number is higher. This surfaced as
    a real, silent bug: it broke migration_run_book.py's Load-phase
    Object-cell resolution for three different bare object names in one
    pass (Account, Contact, Campaign), caught only by the existing test
    suite failing, not by reasoning. Two independent mitigations now
    exist: (1) name a new compound-object script without an underscore
    between the embedded segments ("accountcontactrelation",
    "campaignmember", "giftcommitmentschedule",
    "gifttransactiondesignation") so it can't match the shorter object as
    a substring at all -- still the safest choice when naming a new
    script; and (2) script_filename_for()'s own optional `known_objects`
    parameter (see its docstring below), for callers that already know
    the full set of real object names in play and want the matcher itself
    to defend against this even if a script wasn't named defensively. See
    ROADMAP.md #76 for the full write-up of both."""
    text_value = str(text_value)
    if object_name.lower() == text_value.strip().lower():
        return True
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(object_name)}(?![A-Za-z0-9])",
        text_value, re.IGNORECASE,
    ) is not None


def _disqualifying_match(other_object_name, text_value):
    """Looser than matches_token(), used only by script_filename_for()'s
    known_objects disqualification check below. A real compound object
    name (e.g. "AccountContactRelation") has no internal delimiters of
    its own -- CamelCase, no separators -- but the filename representing
    it is conventionally snake_case ("account_contact_relation_load.sql"),
    so matches_token()'s own literal-substring requirement never matches
    the compound name against its own delimited filename (only the
    merged, no-delimiter naming convention matches_token()'s docstring
    recommends). This strips every non-alphanumeric character from
    BOTH sides before comparing, so "AccountContactRelation" correctly
    matches either filename style. Deliberately looser than
    matches_token() -- safe here because this is only ever used to decide
    whether to EXCLUDE a candidate; failing toward "don't disqualify" is
    the unsafe direction, not this one.

    Found in review: an earlier version only stripped text_value, not
    other_object_name, so any object name containing an underscore --
    trivially true for a real custom-object API name ending in "__c" --
    could never disqualify anything, since an underscore-containing
    string can never be a substring of one with every underscore already
    stripped. Confirmed live: `_disqualifying_match("Payment_Method",
    "090_payment_method_load.sql")` returned False before this fix. One
    residual edge remains even now, matching matches_token()'s own
    already-disclosed limitation for the identical reason: a real custom
    object's "__c" suffix has no counterpart in a conventionally-named
    filename (nobody names a script "..._method_c_load.sql"), so
    "Payment_Method__c" still won't disqualify a file named
    "090_payment_method_load.sql" -- normalizing strips the suffix's
    underscores but leaves a trailing "c" with nothing in the filename to
    match against. Not fixed here; a caller with a custom object in
    known_objects should pass its name without the "__c" suffix if this
    matters for a specific case."""
    normalized_text = re.sub(r"[^A-Za-z0-9]", "", text_value).lower()
    normalized_other = re.sub(r"[^A-Za-z0-9]", "", other_object_name).lower()
    return normalized_other in normalized_text


def script_filename_for(object_name, directory, known_objects=None):
    """The real script for object_name in directory (sql/transformations/
    or sql/source_ingestion/) -- when more than one matches (e.g. an old
    illustrative template alongside the real numbered script), the
    highest-numbered one wins, since this project's own numbering
    convention means "most recent"/"actually used" rather than
    alphabetically first. Filenames are zero-padded to the same width, so
    ascending string sort already puts the highest number last. Returns ""
    if directory doesn't exist or nothing matches -- callers decide
    whether that's an error (a step that requires the script to already
    exist) or just "nothing to link yet".

    known_objects: optional -- the full set of real object names in play
    for this caller (e.g. every object in dbo.ObjectLoadOrder, or every
    sheet already in a mapping workbook). When given, a filename that
    matches object_name AND some other, different, LONGER name in
    known_objects (via _disqualifying_match(), not matches_token() --
    see that helper's own docstring for why) is disqualified for
    object_name -- it more specifically belongs to that longer compound
    name instead (see matches_token()'s own docstring for the real
    collision this defends against, e.g.
    "account_contact_relation_load.sql" also matching a bare "Account").
    Omitted (the default): original behavior, unchanged -- every
    existing caller that doesn't pass this is not affected. This is a
    real but partial fix: it only helps when the caller actually knows
    about the longer, disqualifying name; a caller with an incomplete
    known_objects set (or none at all) can still hit the original
    ambiguity. The naming-convention workaround in matches_token()'s own
    docstring (no delimiter between a compound name's embedded segments)
    remains the safest choice regardless.

    Only ever returns the single highest-numbered survivor -- silent when
    more than one genuinely different, real script both legitimately
    implement object_name (e.g. this project's own GiftCommitment, built
    from two different source routing branches as
    160_npc_giftcommitment_from_rd_load.sql and
    180_npc_giftcommitment_from_opportunity_load.sql). known_objects
    can't disambiguate that case at all -- it only ever excludes a
    candidate that belongs to a different, longer object name, not one
    that belongs to the SAME object name as a second, equally-valid
    script. A caller where picking the wrong one of several real
    candidates is actively harmful (not just "no link shown") should call
    script_candidates_for() directly and decide how to handle more than
    one survivor, rather than silently trust this function's own
    highest-number-wins tiebreak -- see mapping_doc.py's
    set_transform_script() for the pattern."""
    candidates = script_candidates_for(object_name, directory, known_objects=known_objects)
    return candidates[-1] if candidates else ""


def script_filename_for_source_table(candidates, directory, source_table):
    """Disambiguate among more than one real script_candidates_for()
    result using a known SourceTable value (e.g. a BulkOpsLog row's own
    SourceTable column) -- the one real, unambiguous signal available
    when two genuinely different scripts both implement the same object
    name from different source-routing branches (this project's own
    GiftTransaction: 200_npc_gifttransaction_from_opportunity_load.sql
    building GiftTransactionFromOpp_Load, and
    210_npc_gifttransaction_from_payment_load.sql building
    GiftTransactionFromPayment_Load -- script_filename_for()'s own
    highest-number-wins tiebreak always picks 210, silently wrong for a
    log row that actually ran 200). Matches by finding which candidate's
    own `INTO [dbo].[SourceTable]` clause (or bare `INTO dbo.SourceTable`,
    brackets optional, case-insensitive) names source_table exactly --
    real, not guessed, since every transformation script's own SELECT
    INTO target is exactly what a real bulk_op() call records as
    SourceTable.

    Returns "" if source_table is falsy, no candidate's file can be read,
    or none match -- callers should fall back to their own
    highest-number-wins default in that case, same as
    script_filename_for() already does when disambiguation isn't
    possible."""
    if not source_table:
        return ""
    pattern = re.compile(
        rf"INTO\s+\[?dbo\]?\.\[?{re.escape(source_table)}\]?(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
    for f in candidates:
        try:
            with open(os.path.join(directory, f), "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        if pattern.search(content):
            return f
    return ""


def script_candidates_for(object_name, directory, known_objects=None):
    """Every real script filename matching object_name in directory,
    sorted ascending (so the highest-numbered -- "most recent"/"actually
    used" -- is last), after known_objects disqualification (see
    script_filename_for()'s own docstring for exactly what that does and
    its real limits). Empty list if directory doesn't exist or nothing
    matches. script_filename_for() is a thin convenience wrapper around
    this that just returns the last candidate (or "") -- call this
    directly instead when a caller needs to know whether MORE THAN ONE
    real, distinct script matched, since script_filename_for()'s own
    highest-number tiebreak can silently pick the wrong one of two
    equally-valid scripts for the same object name (a real gap found in
    review -- known_objects only ever disqualifies a DIFFERENT, longer
    object name's file, never a second file for the SAME object name)."""
    if not os.path.isdir(directory):
        return []
    candidates = sorted(
        f for f in os.listdir(directory)
        if f.lower().endswith(".sql") and matches_token(object_name, f)
    )
    if known_objects:
        others = [o for o in known_objects if o != object_name]
        candidates = [
            f for f in candidates
            if not any(len(o) > len(object_name) and _disqualifying_match(o, f) for o in others)
        ]
    return candidates
