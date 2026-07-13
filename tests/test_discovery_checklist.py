"""Coverage for discovery_checklist.py (roadmap #60) -- a stub covering
analyze_object_risk()'s real Salesforce calls (describe()/toolingexecute/
query), since no existing test in this project already stubs that path
(test_risk_analyzer.py only covers write_to_sql(), never
analyze_object_risk() itself).
"""
import urllib.parse

import discovery_checklist as dc


class _StubObjectDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, fields_by_object, tooling_by_type=None, query_by_type=None):
        self._fields_by_object = fields_by_object
        self._tooling_by_type = tooling_by_type or {}
        self._query_by_type = query_by_type or {}

    def __getattr__(self, name):
        return _StubObjectDescribe(self._fields_by_object.get(name, []))

    def toolingexecute(self, path):
        soql = urllib.parse.unquote(path.split("query/?q=", 1)[1])
        for entity, records in self._tooling_by_type.items():
            if f"FROM {entity} " in soql or soql.endswith(f"FROM {entity}"):
                return {"records": records}
        return {"records": []}

    def query(self, soql):
        for entity, records in self._query_by_type.items():
            if f"FROM {entity} " in soql or soql.endswith(f"FROM {entity}"):
                return {"records": records}
        return {"records": []}


_BASE_FIELDS = [{"name": "Id", "type": "id"}, {"name": "Name", "type": "string"}]


def test_no_signals_yields_empty_questions_and_zero_summary():
    sf = _StubSF({"Account": _BASE_FIELDS})
    result = dc.generate_discovery_checklist(sf, ["Account"])
    assert result[0]["questions"] == []
    assert result[0]["risk_summary"] == {
        "active_validation_rules": 0, "apex_triggers": 0, "workflow_rules": 0,
        "active_flows": 0, "approval_processes": 0,
    }


def test_active_validation_rule_generates_a_question():
    sf = _StubSF(
        {"Account": _BASE_FIELDS},
        tooling_by_type={"ValidationRule": [
            {"Id": "1", "ValidationName": "No_Blank_City", "Active": True,
             "ErrorDisplayField": "BillingCity", "ErrorMessage": "City is required"},
        ]},
    )
    result = dc.generate_discovery_checklist(sf, ["Account"])
    questions = result[0]["questions"]
    assert any("1 active validation rule(s)" in q for q in questions)
    assert any("No_Blank_City" in q and "BillingCity" in q and "City is required" in q for q in questions)
    assert result[0]["risk_summary"]["active_validation_rules"] == 1


def test_inactive_validation_rule_is_not_a_question():
    sf = _StubSF(
        {"Account": _BASE_FIELDS},
        tooling_by_type={"ValidationRule": [
            {"Id": "1", "ValidationName": "Old_Rule", "Active": False, "ErrorDisplayField": "Name"},
        ]},
    )
    result = dc.generate_discovery_checklist(sf, ["Account"])
    assert result[0]["questions"] == []
    assert result[0]["risk_summary"]["active_validation_rules"] == 0


def test_record_type_id_field_generates_a_question():
    fields = _BASE_FIELDS + [{"name": "RecordTypeId", "type": "reference"}]
    sf = _StubSF({"Account": fields})
    result = dc.generate_discovery_checklist(sf, ["Account"])
    assert any("Record Types" in q and "DeveloperName" in q for q in result[0]["questions"])


def test_no_record_type_id_field_no_question():
    sf = _StubSF({"Account": _BASE_FIELDS})
    result = dc.generate_discovery_checklist(sf, ["Account"])
    assert not any("Record Types" in q for q in result[0]["questions"])


def test_out_of_scope_reference_generates_a_dependency_question():
    fields = _BASE_FIELDS + [
        {"name": "AccountId", "type": "reference", "referenceTo": ["Account"]},
    ]
    sf = _StubSF({"Contact": fields, "Account": _BASE_FIELDS})
    result = dc.generate_discovery_checklist(sf, ["Contact"])  # Account NOT in scope
    assert any("Contact depends on Account" in q for q in result[0]["questions"])


def test_in_scope_reference_generates_no_dependency_question():
    fields = _BASE_FIELDS + [
        {"name": "AccountId", "type": "reference", "referenceTo": ["Account"]},
    ]
    sf = _StubSF({"Contact": fields, "Account": _BASE_FIELDS})
    result = dc.generate_discovery_checklist(sf, ["Contact", "Account"])
    assert not any("depends on" in q for q in result[0]["questions"])


def test_self_reference_generates_no_dependency_question():
    fields = _BASE_FIELDS + [
        {"name": "ParentId", "type": "reference", "referenceTo": ["Account"]},
    ]
    sf = _StubSF({"Account": fields})
    result = dc.generate_discovery_checklist(sf, ["Account"])
    assert not any("depends on" in q for q in result[0]["questions"])


def test_format_discovery_checklist_markdown_structure():
    fields = _BASE_FIELDS + [{"name": "RecordTypeId", "type": "reference"}]
    sf = _StubSF({"Account": fields})
    checklist = dc.generate_discovery_checklist(sf, ["Account"])
    md = dc.format_discovery_checklist_markdown(checklist)
    assert "# Discovery Checklist" in md
    assert "## Account" in md
    assert "Record Types" in md


def test_format_discovery_checklist_markdown_no_questions_message():
    sf = _StubSF({"Account": _BASE_FIELDS})
    checklist = dc.generate_discovery_checklist(sf, ["Account"])
    md = dc.format_discovery_checklist_markdown(checklist)
    assert "No specific questions surfaced" in md
