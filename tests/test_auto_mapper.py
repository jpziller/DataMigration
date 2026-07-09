from auto_mapper import _match_target, _normalize


def test_normalize_lowercases():
    assert _normalize("BillingCity") == "billingcity"


def test_normalize_strips_custom_field_suffix():
    assert _normalize("Legacy_Id__c") == "legacyid"


def test_normalize_strips_non_alphanumeric():
    assert _normalize("Billing-City #1") == "billingcity1"


def test_match_target_exact_normalized_match():
    target_lookup = {"billingcity": {"name": "BillingCity"}}
    field, method, score = _match_target("Billing_City", target_lookup, {})
    assert field == {"name": "BillingCity"}
    assert method == "exact"
    assert score == 1.0


def test_match_target_thesaurus_alias():
    target_lookup = {"billingpostalcode": {"name": "BillingPostalCode"}}
    alias_to_concept = {"zip": "BillingPostalCode"}
    field, method, score = _match_target("zip", target_lookup, alias_to_concept)
    assert field == {"name": "BillingPostalCode"}
    assert method == "thesaurus"


def test_match_target_fuzzy_above_threshold():
    target_lookup = {"billingcity": {"name": "BillingCity"}}
    field, method, score = _match_target("BillngCity", target_lookup, {})
    assert field == {"name": "BillingCity"}
    assert method == "fuzzy"


def test_match_target_no_match_returns_none():
    target_lookup = {"billingcity": {"name": "BillingCity"}}
    field, method, score = _match_target("CompletelyUnrelatedField", target_lookup, {})
    assert field is None
    assert method is None
    assert score == 0.0
