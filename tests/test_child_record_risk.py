"""Coverage for child_record_risk.py -- detecting platform-auto-generated
child records the Tooling API can't see (the GiftCommitmentSchedule
finding, 2026-07-18). Local _StubSF pattern matching
test_sample_reference_records.py's own established convention, since the
shared stub_salesforce.py doesn't support query().
"""
import child_record_risk as ccr


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    """query_responses: {substring -> records list}. The first key found
    as a substring of the actual SOQL wins -- callers pick distinct-enough
    substrings (an object name always differs between parent and child in
    a real edge, so "FROM Parent"/"FROM Child" never collide)."""
    def __init__(self, fields_by_object, query_responses):
        self._fields_by_object = fields_by_object
        self._query_responses = query_responses
        self.queries = []

    def __getattr__(self, name):
        return _StubObjectDescribe(self._fields_by_object[name])

    def query(self, soql):
        self.queries.append(soql)
        for key, records in self._query_responses.items():
            if key in soql:
                return {"records": records}
        return {"records": []}


_WITH_MIGRATION_ID = [
    {"name": "Id", "type": "id"},
    {"name": "MigrationID__c", "type": "string"},
]
_WITHOUT_MIGRATION_ID = [{"name": "Id", "type": "id"}]

_EDGE = {"child": "GiftCommitmentSchedule", "parent": "GiftCommitment",
         "field": "GiftCommitmentId", "is_master_detail": False, "is_nillable": True}


def test_high_rate_flags_likely_auto_generated():
    parent_ids = [f"6gc{i}" for i in range(4)]
    sf = _StubSF(
        {"GiftCommitment": _WITH_MIGRATION_ID},
        {
            "FROM GiftCommitment WHERE MigrationID__c": [{"Id": pid} for pid in parent_ids],
            "FROM GiftCommitmentSchedule": [{"GiftCommitmentId": pid, "cnt": 1} for pid in parent_ids],
        },
    )
    findings = ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"], edges=[_EDGE])
    assert len(findings) == 1
    f = findings[0]
    assert f["parent"] == "GiftCommitment"
    assert f["child"] == "GiftCommitmentSchedule"
    assert f["sample_size"] == 4
    assert f["with_child_count"] == 4
    assert f["rate"] == 1.0
    assert f["likely_auto_generated"] is True
    assert f["insufficient_data"] is False
    assert f["used_migration_filter"] is True


def test_low_rate_not_flagged():
    parent_ids = [f"6gc{i}" for i in range(4)]
    sf = _StubSF(
        {"GiftCommitment": _WITH_MIGRATION_ID},
        {
            "FROM GiftCommitment WHERE MigrationID__c": [{"Id": pid} for pid in parent_ids],
            # Only the first parent has a real child.
            "FROM GiftCommitmentSchedule": [{"GiftCommitmentId": parent_ids[0], "cnt": 1}],
        },
    )
    findings = ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"], edges=[_EDGE])
    f = findings[0]
    assert f["with_child_count"] == 1
    assert f["rate"] == 0.25
    assert f["likely_auto_generated"] is False


def test_insufficient_sample_never_flagged_even_at_100_percent():
    parent_ids = ["6gc0", "6gc1"]  # below default min_sample=3
    sf = _StubSF(
        {"GiftCommitment": _WITH_MIGRATION_ID},
        {
            "FROM GiftCommitment WHERE MigrationID__c": [{"Id": pid} for pid in parent_ids],
            "FROM GiftCommitmentSchedule": [{"GiftCommitmentId": pid, "cnt": 1} for pid in parent_ids],
        },
    )
    findings = ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"], edges=[_EDGE])
    f = findings[0]
    assert f["sample_size"] == 2
    assert f["rate"] == 1.0
    assert f["insufficient_data"] is True
    assert f["likely_auto_generated"] is False


def test_missing_migration_id_field_falls_back_to_unfiltered_sample():
    parent_ids = [f"6gc{i}" for i in range(3)]
    sf = _StubSF(
        {"GiftCommitment": _WITHOUT_MIGRATION_ID},
        {
            "FROM GiftCommitment ORDER BY": [{"Id": pid} for pid in parent_ids],
            "FROM GiftCommitmentSchedule": [{"GiftCommitmentId": pid, "cnt": 1} for pid in parent_ids],
        },
    )
    findings = ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"], edges=[_EDGE])
    f = findings[0]
    assert f["used_migration_filter"] is False
    assert f["sample_size"] == 3
    # The unfiltered fallback query must NOT include a MigrationID__c filter.
    assert not any("MigrationID__c" in q for q in sf.queries)


def test_aggregate_query_shape_uses_in_clause_and_group_by():
    sf = _StubSF(
        {"GiftCommitment": _WITH_MIGRATION_ID},
        {
            "FROM GiftCommitment WHERE MigrationID__c": [{"Id": "6gc0"}, {"Id": "6gc1"}, {"Id": "6gc2"}],
            "FROM GiftCommitmentSchedule": [],
        },
    )
    ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"], edges=[_EDGE])
    child_query = next(q for q in sf.queries if "GiftCommitmentSchedule" in q)
    assert "GROUP BY GiftCommitmentId" in child_query
    assert "IN ('6gc0', '6gc1', '6gc2')" in child_query


def test_no_edges_means_no_findings():
    sf = _StubSF({"Account": _WITH_MIGRATION_ID}, {})
    findings = ccr.detect_auto_generated_children(sf, ["Account"], edges=[])
    assert findings == []


def test_edges_computed_from_object_names_when_not_given():
    """When edges=None, falls back to load_order.build_dependency_edges --
    a real reference field on the child pointing at the parent, both
    inside object_names, must be discovered without the caller precomputing it."""
    child_fields = [
        {"name": "Id", "type": "id"},
        {"name": "GiftCommitmentId", "type": "reference", "referenceTo": ["GiftCommitment"], "nillable": True},
    ]
    sf = _StubSF(
        {"GiftCommitment": _WITH_MIGRATION_ID, "GiftCommitmentSchedule": child_fields},
        {
            "FROM GiftCommitment WHERE MigrationID__c": [{"Id": "6gc0"}, {"Id": "6gc1"}, {"Id": "6gc2"}],
            "FROM GiftCommitmentSchedule": [{"GiftCommitmentId": "6gc0", "cnt": 1}],
        },
    )
    findings = ccr.detect_auto_generated_children(sf, ["GiftCommitment", "GiftCommitmentSchedule"])
    assert len(findings) == 1
    assert findings[0]["parent"] == "GiftCommitment"
    assert findings[0]["child"] == "GiftCommitmentSchedule"
