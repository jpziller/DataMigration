"""Sample a small, human-identified set of real target-object records to
learn their true field-level shape -- what's actually populated, not just
what describe() or a page layout shows.

Real finding this tool exists to shorten: three Nonprofit Cloud objects
(GiftCommitment, GiftTransaction, PartyRelationshipGroup) each needed a
Name value with no natural source field, discovered only by trial-and-
error against three separate live bulkops inserts. A single sample
against one real record of each object would have shown Name populated
immediately. This generalizes that instinct into a standing, reusable
tool -- and mirrors a pattern familiar from complex managed-package work
(CPQ, and by extension Nonprofit Cloud): describe() and page layouts
don't show the full picture of what a *working* record actually looks
like, especially for fields the package's own automation needs but never
surfaces in the UI. The only reliable way to learn that shape is to look
at real records -- ideally ones a human created through the platform's
own guided flow, so its automation has already shaped them correctly.

Deliberately NOT a pre-build-only gate. Migration work happens in
sprints, and the true shape of a target object is often not fully
understood until UAT surfaces it -- this is meant to be reached for at
any point (before building, mid-sprint, after a UAT finding), the same
way query/describe themselves are, not a one-time Standard Workflow step.

Complements compare-reference-record (roadmap #51, reference_record.py)
rather than replacing it: that tool needs a *_Load table to already
exist and can only diff fields a transform already populates -- it's a
late-stage, targeted diffing aid. This tool needs neither, and exists
specifically to surface a field nobody thought to include yet.

Automation context is reported at the OBJECT level only (active
validation-rule/trigger/flow counts from dbo.ObjectAutomationRisk, if
analyze-org-risk has already been run) -- deliberately not a per-field
cross-reference. dbo.ObjectAutomationRisk's own Detail column is free
validation-rule error-message text, not a structured field reference;
regex-guessing a field name out of it would be exactly the kind of
invented, unconfirmed text-matching failure_triage.py's own docstring
already warns against (it only ever extracts a field name from one
specific, confirmed-reliable error message shape -- REQUIRED_FIELD_MISSING's
bracketed list -- and gives guidance text only for every other case).
"""
from sqlalchemy import text

import sql_dialect
from type_map import is_compound

_MAX_SAMPLE_VALUES = 3
DEFAULT_LIMIT = 5


def _escape_soql_literal(value):
    # Same manual-escaping convention bulkops.py's
    # _resolve_external_ids_to_sf_id() and reference_record.py's
    # compare_reference_record() already use -- simple_salesforce has no
    # bind-parameter API for SOQL.
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _queryable_field_names(desc):
    # Compound fields (address, location) can't be selected directly via
    # SOQL -- their real sub-fields (BillingStreet, BillingLatitude, ...)
    # already appear as their own separate describe() fields. Same
    # exclusion replicate.py already applies for the identical reason.
    return [f["name"] for f in desc["fields"] if not is_compound(f)]


def _automation_summary(engine, schema, object_name):
    """{"active_validation_rules", "active_apex_triggers",
    "active_flows", "active_workflow_rules", "active_approval_processes"}
    counts from dbo.ObjectAutomationRisk (analyze-org-risk's own output),
    or None if that table doesn't exist yet for this schema -- callers
    report "not checked" rather than a silently misleading zero."""
    d = sql_dialect.for_engine(engine)
    if not d.table_exists(engine, schema, "ObjectAutomationRisk"):
        return None
    with engine.connect() as cx:
        rows = cx.execute(
            text(
                f"SELECT CheckType, IsActive FROM {d.qualify(schema, 'ObjectAutomationRisk')} "
                f"WHERE ObjectName = :obj"
            ),
            {"obj": object_name},
        ).mappings().all()
    rows = [sql_dialect.lower_keys(r) for r in rows]
    counts = {}
    for r in rows:
        if not r.get("isactive"):
            continue
        counts[r["checktype"]] = counts.get(r["checktype"], 0) + 1
    return counts


def sample_reference_records(sf, object_name, record_ids=None, where=None,
                              limit=DEFAULT_LIMIT, engine=None, schema="dbo",
                              show_all=False):
    """Query a small sample of real object_name records and report every
    field's real shape across them.

    record_ids: explicit, human-provided Ids -- the recommended input,
    since only a human knows which records are genuinely good examples
    (especially for a package object with no real data yet, needing one
    hand-created through the UI first). Takes priority over where.
    where: a SOQL WHERE clause (no leading "WHERE"), for when a human
    knows a filtering criterion but not specific Ids.
    Neither given: falls back to the `limit` most-recently-created
    records -- a permissive default, not the recommended path.

    engine/schema: optional -- enables the object-level automation
    summary via dbo.ObjectAutomationRisk if analyze-org-risk has already
    been run for this schema. Omitted: automation is reported as None
    ("not checked"), never silently assumed clean.

    Returns {"object", "sample_size", "record_ids", "automation" | None,
    "fields": [{"field", "label", "type", "createable", "nillable",
    "defaulted_on_create", "populated_count", "sample_values"}, ...]}.
    fields is sorted by populated_count descending, then field name --
    the most broadly-populated (and so most likely genuinely meaningful)
    fields surface first. Only fields populated in at least one sample
    are included unless show_all=True.
    """
    desc = getattr(sf, object_name).describe()
    fields_by_name = {f["name"]: f for f in desc["fields"]}
    select_fields = _queryable_field_names(desc)
    select_clause = ", ".join(select_fields)

    if record_ids:
        ids_clause = ", ".join(f"'{_escape_soql_literal(i)}'" for i in record_ids)
        soql = f"SELECT {select_clause} FROM {object_name} WHERE Id IN ({ids_clause})"
    elif where:
        soql = f"SELECT {select_clause} FROM {object_name} WHERE {where} LIMIT {limit}"
    else:
        soql = f"SELECT {select_clause} FROM {object_name} ORDER BY CreatedDate DESC LIMIT {limit}"

    records = sf.query(soql)["records"]
    sample_size = len(records)

    field_reports = []
    for name in select_fields:
        f = fields_by_name[name]
        values = [r.get(name) for r in records if r.get(name) not in (None, "")]
        populated_count = len(values)
        if populated_count == 0 and not show_all:
            continue
        sample_values = list(dict.fromkeys(str(v) for v in values))[:_MAX_SAMPLE_VALUES]
        field_reports.append({
            "field": name,
            "label": f.get("label"),
            "type": f.get("type"),
            "createable": f.get("createable"),
            "nillable": f.get("nillable"),
            "defaulted_on_create": f.get("defaultedOnCreate"),
            "populated_count": populated_count,
            "sample_values": sample_values,
        })

    field_reports.sort(key=lambda r: (-r["populated_count"], r["field"]))

    automation = _automation_summary(engine, schema, object_name) if engine is not None else None

    return {
        "object": object_name,
        "sample_size": sample_size,
        "record_ids": [r.get("Id") for r in records],
        "automation": automation,
        "fields": field_reports,
    }
