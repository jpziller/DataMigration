"""Detect child records a migration didn't create but the platform did
(roadmap follow-up to the NPSP-to-NPC GiftCommitmentSchedule finding).

analyze-org-risk (risk_analyzer.py) only sees automation the Tooling API
can introspect -- ValidationRule/ApexTrigger/Flow/WorkflowRule/
ApprovalProcess. It has a real, structural blind spot: managed-package-
internal automation. Confirmed live, 2026-07-18: Nonprofit Cloud
auto-creates a GiftCommitmentSchedule the moment a GiftCommitment is
inserted with ScheduleType = 'Recurring' -- no Flow/trigger visible via
the Tooling API explains this; it's baked into the package. A migration's
own explicit insert for that same child then collides with it.

Since the automation itself can't be introspected, this module infers it
empirically instead: for every parent -> child dependency edge among the
objects a migration is analyzing, sample real, human-created/pre-existing
parent records and check what fraction of them already have a real child
record. A consistently high rate -- especially when the migration's own
plan has no explicit reason to expect one -- is a signal worth verifying
before assuming an explicit child-object insert is safe or necessary.

This is advisory, not proof. A genuinely normal 1:1 business relationship
(not platform auto-creation) can also show a high rate -- e.g. every real
Opportunity might have exactly one OpportunityLineItem because that's how
the business actually operates, not because the platform silently created
it. Verify the real reason before deciding whether to skip an explicit
insert, the same way batch_advisor.py's/auto_mapper.py's own
recommendations are a starting point for human judgment, not a verdict.
"""
from load_order import build_dependency_edges

DEFAULT_MIN_SAMPLE = 3
# Calibrated against real data, not a guess: live-tested in NPC_TARGET_v2
# against the exact known-true GiftCommitment -> GiftCommitmentSchedule
# auto-creation pattern (see gift-commitment-schedule-auto-creation.md).
# A naive, unsegmented sample of real GiftCommitment records (mixing
# Recurring and Custom ScheduleType together) showed a 60% population
# rate for that real relationship -- 0.8 was too strict and missed it
# entirely; 0.5 catches it. Real-world population rates for a genuine
# platform-automation relationship can be diluted well below 100% when
# the parent object mixes record shapes that only sometimes trigger the
# automation (here, only Recurring-type commitments do) -- this default
# is deliberately permissive rather than conservative, since a false
# positive only costs a human a "verify this" glance, while a false
# negative (the original, too-strict 0.8) silently misses the exact bug
# this module was built to catch.
DEFAULT_THRESHOLD = 0.5
DEFAULT_SAMPLE_LIMIT = 10


def _escape_soql_literal(value):
    """Manual SOQL string-literal escaping -- simple_salesforce has no bind-
    parameter API, same convention as bulkops.py/reference_record.py/
    sample_reference_records.py."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _has_field(sf, object_name, field_name):
    desc = getattr(sf, object_name).describe()
    return any(f["name"] == field_name for f in desc["fields"])


def _sample_parent_ids(sf, parent, sample_limit):
    """Real, non-migrated parent Ids if MigrationID__c exists on this
    object (the same "real reference data" signal sample_reference_records.py
    already established); otherwise every real parent Id, with the caller
    told the filter wasn't available via used_migration_filter=False."""
    used_migration_filter = _has_field(sf, parent, "MigrationID__c")
    if used_migration_filter:
        soql = (
            f"SELECT Id FROM {parent} WHERE MigrationID__c = null "
            f"ORDER BY CreatedDate DESC LIMIT {sample_limit}"
        )
    else:
        soql = f"SELECT Id FROM {parent} ORDER BY CreatedDate DESC LIMIT {sample_limit}"
    records = sf.query(soql).get("records", [])
    return [r["Id"] for r in records], used_migration_filter


def _count_children_per_parent(sf, child, field, parent_ids):
    """One aggregate query for every sampled parent Id at once -- not one
    query per record. Returns {parent_id: count}."""
    if not parent_ids:
        return {}
    ids_clause = ", ".join(f"'{_escape_soql_literal(i)}'" for i in parent_ids)
    soql = f"SELECT {field}, COUNT(Id) cnt FROM {child} WHERE {field} IN ({ids_clause}) GROUP BY {field}"
    records = sf.query(soql).get("records", [])
    return {r[field]: r["cnt"] for r in records}


def detect_auto_generated_children(sf, object_names, edges=None,
                                    min_sample=DEFAULT_MIN_SAMPLE,
                                    threshold=DEFAULT_THRESHOLD,
                                    sample_limit=DEFAULT_SAMPLE_LIMIT):
    """For every parent -> child dependency edge among object_names, sample
    real parent records and report what fraction already have a real child.

    edges: reuse an already-computed load_order.build_dependency_edges()
    result if the caller has one (e.g. risk_analyzer.py's own
    analyze_migration_risk(), which needs the same edges for nothing else
    here but would otherwise describe() every object twice). Computed
    fresh via build_dependency_edges(sf, object_names) if not given --
    this only considers edges within object_names, the same scoping
    build_dependency_edges itself already documents; there is no org-wide
    reverse-dependency scan here by design (analyze-org-risk is always
    invoked with the full object set a migration project is analyzing).

    Returns a list of dicts, one per edge:
    {"parent", "child", "field", "sample_size", "with_child_count", "rate",
     "insufficient_data", "likely_auto_generated", "used_migration_filter"}
    """
    if edges is None:
        edges = build_dependency_edges(sf, object_names)

    findings = []
    for edge in edges:
        parent, child, field = edge["parent"], edge["child"], edge["field"]
        parent_ids, used_migration_filter = _sample_parent_ids(sf, parent, sample_limit)
        sample_size = len(parent_ids)
        insufficient_data = sample_size < min_sample

        counts = _count_children_per_parent(sf, child, field, parent_ids)
        with_child_count = sum(1 for pid in parent_ids if counts.get(pid, 0) > 0)
        rate = (with_child_count / sample_size) if sample_size else 0.0

        findings.append({
            "parent": parent,
            "child": child,
            "field": field,
            "sample_size": sample_size,
            "with_child_count": with_child_count,
            "rate": rate,
            "insufficient_data": insufficient_data,
            "likely_auto_generated": (not insufficient_data) and rate >= threshold,
            "used_migration_filter": used_migration_filter,
        })
    return findings
