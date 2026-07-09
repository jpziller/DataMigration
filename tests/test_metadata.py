from metadata import validate_external_id_field


class _StubObject:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, object_name, fields):
        setattr(self, object_name, _StubObject(fields))


def test_validate_external_id_field_ok_when_both_flags_set():
    sf = _StubSF("Account", [
        {"name": "Legacy_Id__c", "externalId": True, "unique": True},
    ])
    result = validate_external_id_field(sf, "Account", "Legacy_Id__c")
    assert result == {"ok": True, "problems": []}


def test_validate_external_id_field_missing_field():
    sf = _StubSF("Account", [{"name": "Name", "externalId": False, "unique": False}])
    result = validate_external_id_field(sf, "Account", "Legacy_Id__c")
    assert result["ok"] is False
    assert "is not a field on Account" in result["problems"][0]


def test_validate_external_id_field_not_external_id():
    sf = _StubSF("Account", [
        {"name": "Legacy_Id__c", "externalId": False, "unique": True},
    ])
    result = validate_external_id_field(sf, "Account", "Legacy_Id__c")
    assert result["ok"] is False
    assert any("External ID" in p for p in result["problems"])


def test_validate_external_id_field_not_unique():
    sf = _StubSF("Account", [
        {"name": "Legacy_Id__c", "externalId": True, "unique": False},
    ])
    result = validate_external_id_field(sf, "Account", "Legacy_Id__c")
    assert result["ok"] is False
    assert any("Unique" in p for p in result["problems"])


def test_validate_external_id_field_reports_both_problems_together():
    sf = _StubSF("Account", [
        {"name": "Legacy_Id__c", "externalId": False, "unique": False},
    ])
    result = validate_external_id_field(sf, "Account", "Legacy_Id__c")
    assert result["ok"] is False
    assert len(result["problems"]) == 2
