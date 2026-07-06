"""Auto-mapping: draft source -> target field suggestions for a human to
review and correct, not a final answer (roadmap: auto-mapping).

Hard prerequisite: the source table must already be profiled
(profiling.py's profile-sql-table) -- this tool reads dbo.FieldProfile/
FieldProfileValues as its data-quality signal and refuses to guess without
it, since a name match with no data-quality context is exactly the kind of
unreviewable noise that gets a tool abandoned.

Matching pipeline, cheapest/most-confident first:
  1. Exact match on normalized name (strip __c, underscores, case).
  2. Thesaurus match against reference/field_synonyms.json -- a versioned,
     human-editable concept dictionary (git is the source of truth; this
     tool reads the file directly, no SQL Server round-trip for it). Every
     human correction during a real mapping session is a candidate new
     alias to add there.
  3. Fuzzy fallback (difflib) for near-misses the thesaurus doesn't cover
     yet.

A match is then run through a data-quality gate using the source field's
actual profile: low population or a single distinct value (e.g. 100%
populated but every row says the same thing) downgrades "migrate" to
"No"/"Review" with a written reason -- a name match never silently
overrides a bad data-quality signal.

Results land in dbo.AutoMapSuggestions (this run's suggestions) and
dbo.SourceRegistry (which source/target pairs have been auto-mapped and
when) -- both in the mirror DB, both regenerated per run, same
"replace this object's prior rows" pattern as profiling.py.
"""
import difflib
import json
import os
import re
from datetime import datetime, timezone

from sqlalchemy import text

from type_map import is_compound

_THESAURUS_PATH = os.path.join(os.path.dirname(__file__), "reference", "field_synonyms.json")

# Tunable thresholds -- art-and-science defaults, expected to shift as this
# gets used on real projects.
FUZZY_THRESHOLD = 0.82
LOW_POPULATION_PCT = 5.0
REVIEW_POPULATION_PCT = 20.0

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")


def _normalize(name):
    name = name.lower()
    if name.endswith("__c"):
        name = name[:-3]
    return _NON_ALNUM_RE.sub("", name)


def load_thesaurus(path=None):
    with open(path or _THESAURUS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    alias_to_concept = {}
    for concept, info in data.items():
        if concept.startswith("_"):
            continue
        alias_to_concept[_normalize(concept)] = concept
        for alias in info.get("aliases", []):
            alias_to_concept[_normalize(alias)] = concept
    return alias_to_concept


def _ensure_tables(engine, schema="dbo"):
    with engine.begin() as cx:
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.SourceRegistry', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[SourceRegistry] ("
            "SourceTable NVARCHAR(255) NOT NULL, "
            "TargetObject NVARCHAR(255) NOT NULL, "
            "SchemaName NVARCHAR(128) NOT NULL, "
            "AutoMappedDate DATETIME2 NULL, "
            "CONSTRAINT PK_SourceRegistry PRIMARY KEY (SourceTable, TargetObject));"
        ))
        cx.execute(text(
            f"IF OBJECT_ID('{schema}.AutoMapSuggestions', 'U') IS NULL "
            f"CREATE TABLE [{schema}].[AutoMapSuggestions] ("
            "SourceTable NVARCHAR(255) NOT NULL, "
            "TargetObject NVARCHAR(255) NOT NULL, "
            "SourceField NVARCHAR(255) NOT NULL, "
            "SuggestedTargetField NVARCHAR(255) NULL, "
            "MatchMethod NVARCHAR(20) NULL, "
            "MatchScore DECIMAL(4,3) NULL, "
            "MigrateRecommended NVARCHAR(10) NULL, "
            "Rationale NVARCHAR(1000) NULL, "
            "AnalyzedDate DATETIME2 NOT NULL);"
        ))


def ensure_source_profiled(engine, source_table, schema="dbo"):
    with engine.connect() as cx:
        count = cx.execute(
            text(
                f"SELECT COUNT(*) FROM [{schema}].[FieldProfile] "
                "WHERE ObjectOrTable = :t AND SourceType = 'sql_table'"
            ),
            {"t": source_table},
        ).scalar()
    if not count:
        raise ValueError(
            f"'{source_table}' hasn't been profiled yet -- run "
            f"`profile-sql-table {source_table}` first. Auto-mapping without "
            "profiling data has no basis for judging whether a matched field "
            "is actually worth migrating."
        )


def _get_source_columns(engine, source_table, schema):
    with engine.connect() as cx:
        return cx.execute(
            text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table "
                "ORDER BY ORDINAL_POSITION"
            ),
            {"schema": schema, "table": source_table},
        ).mappings().all()


def _get_field_profile(engine, source_table, schema):
    with engine.connect() as cx:
        rows = cx.execute(
            text(
                f"SELECT FieldName, PopulatedPct, DistinctCount FROM [{schema}].[FieldProfile] "
                "WHERE ObjectOrTable = :t AND SourceType = 'sql_table'"
            ),
            {"t": source_table},
        ).mappings().all()
    return {r["FieldName"]: r for r in rows}


def _get_sample_value(engine, source_table, field_name, schema):
    # Exclude NULL explicitly -- FieldProfileValues stores NULL as its own
    # group (SQL Server's GROUP BY semantics), and a sparsely-populated
    # field's NULL group usually has far more occurrences than its one real
    # value. Without this filter, "the most common value" would report NULL
    # (rendered as the misleading literal string "None") instead of the
    # actual repeated value we're trying to surface.
    with engine.connect() as cx:
        return cx.execute(
            text(
                f"SELECT TOP 1 Value FROM [{schema}].[FieldProfileValues] "
                "WHERE ObjectOrTable = :t AND SourceType = 'sql_table' AND FieldName = :f "
                "AND Value IS NOT NULL "
                "ORDER BY Occurrences DESC"
            ),
            {"t": source_table, "f": field_name},
        ).scalar()


def _quality_gate(engine, source_table, field_name, profile_row, schema):
    if profile_row is None:
        return "Review", "No profiling data found for this column -- re-run profile-sql-table."

    populated_pct = profile_row["PopulatedPct"]
    distinct_count = profile_row["DistinctCount"]

    if populated_pct is None or populated_pct < LOW_POPULATION_PCT:
        pct = populated_pct or 0
        return "No", f"Only {pct:.1f}% populated -- likely not worth migrating."

    if distinct_count == 1:
        sample = _get_sample_value(engine, source_table, field_name, schema)
        return "No", (
            f"Only {populated_pct:.1f}% populated, and every populated row has the same "
            f"value (\"{sample}\") -- no differentiating information, likely not worth migrating."
        )

    if populated_pct < REVIEW_POPULATION_PCT:
        return "Review", f"Only {populated_pct:.1f}% populated -- worth a human look before deciding."

    return "Yes", None


def _match_target(source_field_name, target_lookup, alias_to_concept):
    norm = _normalize(source_field_name)

    if norm in target_lookup:
        return target_lookup[norm], "exact", 1.0

    concept = alias_to_concept.get(norm)
    if concept:
        concept_norm = _normalize(concept)
        if concept_norm in target_lookup:
            return target_lookup[concept_norm], "thesaurus", 0.9

    best_field, best_ratio = None, 0.0
    for t_norm, t_field in target_lookup.items():
        ratio = difflib.SequenceMatcher(None, norm, t_norm).ratio()
        if ratio > best_ratio:
            best_field, best_ratio = t_field, ratio
    if best_ratio >= FUZZY_THRESHOLD:
        return best_field, "fuzzy", best_ratio

    return None, None, 0.0


def suggest_mappings(sf, engine, target_object, source_table, schema="dbo"):
    """Draft source -> target field suggestions for target_object from
    source_table's real columns. Returns the list of suggestion dicts (also
    written to dbo.AutoMapSuggestions / dbo.SourceRegistry)."""
    ensure_source_profiled(engine, source_table, schema=schema)
    _ensure_tables(engine, schema=schema)

    alias_to_concept = load_thesaurus()

    target_desc = getattr(sf, target_object).describe()
    target_lookup = {}
    for f in target_desc["fields"]:
        if is_compound(f) or not f.get("createable"):
            continue
        target_lookup.setdefault(_normalize(f["name"]), f)
        if f.get("label"):
            target_lookup.setdefault(_normalize(f["label"]), f)

    source_cols = _get_source_columns(engine, source_table, schema)
    profile_by_field = _get_field_profile(engine, source_table, schema)

    suggestions = []
    for col in source_cols:
        name = col["COLUMN_NAME"]
        target_field, method, score = _match_target(name, target_lookup, alias_to_concept)

        if target_field is None:
            # Still worth knowing if the data is degenerate even with no
            # target match -- "unmatched AND junk data" is a much stronger
            # signal to just drop the field than "unmatched" alone.
            migrate_flag, quality_note = _quality_gate(
                engine, source_table, name, profile_by_field.get(name), schema
            )
            rationale = "No confident match found -- needs manual review."
            if quality_note is not None:
                rationale += f" Also: {quality_note}"
            suggestions.append({
                "source_field": name,
                "target_field": None,
                "target_label": None,
                "target_type": None,
                "match_method": None,
                "match_score": None,
                "migrate_recommended": "Review" if migrate_flag == "Yes" else migrate_flag,
                "rationale": rationale,
            })
            continue

        migrate_flag, quality_note = _quality_gate(
            engine, source_table, name, profile_by_field.get(name), schema
        )
        match_note = {
            "exact": "Exact name match (normalized).",
            "thesaurus": f"Thesaurus match: known alias for \"{target_field['name']}\".",
            "fuzzy": f"Fuzzy name match ({score:.0%} similarity).",
        }[method]
        rationale = match_note if quality_note is None else f"{match_note} {quality_note}"
        # A data-quality "No"/"Review" always wins over a clean name match --
        # a match is informative, but doesn't override bad underlying data.
        if quality_note is not None and migrate_flag == "Yes":
            migrate_flag = "Review"

        suggestions.append({
            "source_field": name,
            "target_field": target_field["name"],
            "target_label": target_field.get("label"),
            "target_type": target_field.get("type"),
            "match_method": method,
            "match_score": round(score, 3),
            "migrate_recommended": migrate_flag,
            "rationale": rationale,
        })

    _write_suggestions(engine, target_object, source_table, suggestions, schema=schema)
    return suggestions


def _write_suggestions(engine, target_object, source_table, suggestions, schema="dbo"):
    analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as cx:
        cx.execute(
            text(
                f"DELETE FROM [{schema}].[AutoMapSuggestions] "
                "WHERE SourceTable = :s AND TargetObject = :t"
            ),
            {"s": source_table, "t": target_object},
        )
        if suggestions:
            cx.execute(
                text(
                    f"INSERT INTO [{schema}].[AutoMapSuggestions] "
                    "(SourceTable, TargetObject, SourceField, SuggestedTargetField, MatchMethod, "
                    "MatchScore, MigrateRecommended, Rationale, AnalyzedDate) "
                    "VALUES (:source_table, :target_object, :source_field, :target_field, "
                    ":match_method, :match_score, :migrate_recommended, :rationale, :analyzed_at)"
                ),
                [{
                    "source_table": source_table, "target_object": target_object,
                    "source_field": s["source_field"], "target_field": s["target_field"],
                    "match_method": s["match_method"], "match_score": s["match_score"],
                    "migrate_recommended": s["migrate_recommended"], "rationale": s["rationale"],
                    "analyzed_at": analyzed_at,
                } for s in suggestions],
            )

        cx.execute(
            text(
                f"IF EXISTS (SELECT 1 FROM [{schema}].[SourceRegistry] WHERE SourceTable = :s AND TargetObject = :t) "
                f"UPDATE [{schema}].[SourceRegistry] SET AutoMappedDate = :analyzed_at "
                "WHERE SourceTable = :s AND TargetObject = :t "
                f"ELSE INSERT INTO [{schema}].[SourceRegistry] (SourceTable, TargetObject, SchemaName, AutoMappedDate) "
                "VALUES (:s, :t, :schema_name, :analyzed_at);"
            ),
            {"s": source_table, "t": target_object, "schema_name": schema, "analyzed_at": analyzed_at},
        )
