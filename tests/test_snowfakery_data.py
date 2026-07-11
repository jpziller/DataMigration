"""Coverage for snowfakery_data.py -- focused on _fix_snowfakery_datetime_strings(),
a real bug fix (see ROADMAP.md #28): Snowfakery's own JSON output
serializes a datetime value via Python's default str(datetime)
representation (space-separated, tz-aware), which is a genuine XSD
dateTime parse failure against Salesforce's Bulk API, not just
non-canonical -- and it's baked in before pandas/sql_dialect.py's own
dtype-based datetime handling ever sees a real datetime64 column.
"""
import pandas as pd
import yaml

from snowfakery_data import _fix_snowfakery_datetime_strings, build_recipe

_DATETIME_FIELD = {"name": "EmailBouncedDate", "type": "datetime"}
_STRING_FIELD = {"name": "LastName", "type": "string"}


def test_fixes_space_separated_tz_aware_string_to_isoformat_t():
    df = pd.DataFrame({
        "EmailBouncedDate": ["2024-07-29 22:38:35+00:00", "2026-06-17 01:13:23+00:00"],
        "LastName": ["Smith", "Jones"],
    })
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD, _STRING_FIELD])
    assert list(out["EmailBouncedDate"]) == ["2024-07-29T22:38:35+00:00", "2026-06-17T01:13:23+00:00"]
    assert " " not in out["EmailBouncedDate"].iloc[0]
    # non-datetime fields untouched, even though they're plain strings too
    assert list(out["LastName"]) == ["Smith", "Jones"]


def test_leaves_null_and_empty_values_alone():
    df = pd.DataFrame({"EmailBouncedDate": [None, "", "2024-07-29 22:38:35+00:00"]})
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD])
    assert pd.isna(out["EmailBouncedDate"].iloc[0])
    assert out["EmailBouncedDate"].iloc[1] == ""
    assert out["EmailBouncedDate"].iloc[2] == "2024-07-29T22:38:35+00:00"


def test_no_op_when_column_not_present():
    df = pd.DataFrame({"LastName": ["Smith"]})
    out = _fix_snowfakery_datetime_strings(df, [_DATETIME_FIELD, _STRING_FIELD])
    assert list(out.columns) == ["LastName"]


class _StubDescribe:
    def __init__(self, fields):
        self._fields = fields

    def describe(self):
        return {"fields": self._fields}


class _StubSF:
    def __init__(self, describes):
        for name, fields in describes.items():
            setattr(self, name, _StubDescribe(fields))


def _field(name, ftype="string", reference_to=None, nillable=True):
    f = {"name": name, "type": ftype, "createable": True, "nillable": nillable}
    if reference_to is not None:
        f["referenceTo"] = reference_to
    return f


def test_build_recipe_splits_polymorphic_child_into_one_cohort_per_target(tmp_path):
    sf = _StubSF({
        "Account": [_field("Name")],
        "Opportunity": [_field("Name")],
        "Task": [_field("Subject"), _field("WhatId", "reference", ["Account", "Opportunity"])],
    })
    counts = {"Account": 2, "Opportunity": 2, "Task": 1}

    (recipe_path, skipped, primary_parent, secondary_exact,
     secondary_random, fields_by_object, polymorphic_children) = build_recipe(
        sf, ["Account", "Opportunity", "Task"], counts, stage_dir=str(tmp_path)
    )

    assert "Task" not in primary_parent
    assert "Task" not in secondary_exact
    assert "Task" not in secondary_random
    assert polymorphic_children == {
        "Task": {"field": "WhatId", "targets": ["Account", "Opportunity"], "extra_refs": []}
    }

    with open(recipe_path, encoding="utf-8") as fh:
        recipe = yaml.safe_load(fh)
    by_object = {node["object"]: node for node in recipe if isinstance(node, dict) and "object" in node}

    account_task = by_object["Account"]["fields"]["_children_Task"][0]
    assert account_task["fields"]["_ParentType"] == "Account"
    assert account_task["fields"]["_ParentMockRef"] == {"reference": "Account"}

    opportunity_task = by_object["Opportunity"]["fields"]["_children_Task"][0]
    assert opportunity_task["fields"]["_ParentType"] == "Opportunity"
    assert opportunity_task["fields"]["_ParentMockRef"] == {"reference": "Opportunity"}


def test_build_recipe_polymorphic_cohort_carries_extra_refs_exact_vs_random(tmp_path):
    # Opportunity nests under Contact (its deepest in-scope parent) and also
    # exactly references Account (an ancestor of Contact) -- existing,
    # unaffected behavior. Task.WhatId is polymorphic (Account/Opportunity);
    # Task.WhoId is a normal single-target field to Contact. Contact IS an
    # ancestor of Opportunity (via Opportunity->Contact nesting), but is NOT
    # an ancestor of Account -- so each polymorphic cohort should classify
    # the same "extra ref" (Contact) differently.
    sf = _StubSF({
        "Account": [_field("Name")],
        "Contact": [_field("LastName"), _field("AccountId", "reference", ["Account"])],
        "Opportunity": [
            _field("Name"),
            _field("ContactId", "reference", ["Contact"]),
            _field("AccountId", "reference", ["Account"]),
        ],
        "Task": [
            _field("Subject"),
            _field("WhatId", "reference", ["Account", "Opportunity"]),
            _field("WhoId", "reference", ["Contact"]),
        ],
    })
    counts = {"Account": 2, "Contact": 1, "Opportunity": 1, "Task": 1}

    (recipe_path, skipped, primary_parent, secondary_exact,
     secondary_random, fields_by_object, polymorphic_children) = build_recipe(
        sf, ["Account", "Contact", "Opportunity", "Task"], counts, stage_dir=str(tmp_path)
    )

    assert polymorphic_children["Task"]["extra_refs"] == ["Contact"]

    with open(recipe_path, encoding="utf-8") as fh:
        recipe = yaml.safe_load(fh)
    by_object = {node["object"]: node for node in recipe if isinstance(node, dict) and "object" in node}

    account_task = by_object["Account"]["fields"]["_children_Task"][0]
    assert account_task["fields"]["_SecondaryParentRef_Contact"] == {"random_reference": "Contact"}

    # Opportunity nests under Contact -- find the Task cohort under it.
    contact_node = by_object["Account"]["fields"]["_children_Contact"][0]
    opportunity_node = contact_node["fields"]["_children_Opportunity"][0]
    opportunity_task = opportunity_node["fields"]["_children_Task"][0]
    assert opportunity_task["fields"]["_SecondaryParentRef_Contact"] == {"reference": "Contact"}


def test_build_recipe_polymorphic_cohort_skips_redundant_self_ref(tmp_path):
    # Task has its OWN separate AccountId field (real, distinct from the
    # polymorphic WhatId that also targets Account) -- confirmed live
    # against a real org. For the Account-nested cohort, that would be a
    # redundant _SecondaryParentRef_Account pointing at the exact same row
    # _ParentMockRef already references -- should be skipped there, but
    # still appear on the Opportunity-nested cohort (a genuinely different,
    # useful reference there).
    sf = _StubSF({
        "Account": [_field("Name")],
        "Opportunity": [_field("Name"), _field("AccountId", "reference", ["Account"])],
        "Task": [
            _field("Subject"),
            _field("WhatId", "reference", ["Account", "Opportunity"]),
            _field("AccountId", "reference", ["Account"]),
        ],
    })
    counts = {"Account": 2, "Opportunity": 1, "Task": 1}

    (recipe_path, skipped, primary_parent, secondary_exact,
     secondary_random, fields_by_object, polymorphic_children) = build_recipe(
        sf, ["Account", "Opportunity", "Task"], counts, stage_dir=str(tmp_path)
    )

    with open(recipe_path, encoding="utf-8") as fh:
        recipe = yaml.safe_load(fh)
    by_object = {node["object"]: node for node in recipe if isinstance(node, dict) and "object" in node}

    account_task = by_object["Account"]["fields"]["_children_Task"][0]
    assert "_SecondaryParentRef_Account" not in account_task["fields"]

    opportunity_task = by_object["Account"]["fields"]["_children_Opportunity"][0]["fields"]["_children_Task"][0]
    assert opportunity_task["fields"]["_SecondaryParentRef_Account"] == {"reference": "Account"}


def test_build_recipe_raises_on_two_polymorphic_fields_for_same_child(tmp_path):
    sf = _StubSF({
        "Account": [_field("Name")],
        "Opportunity": [_field("Name")],
        "Contact": [_field("LastName")],
        "Task": [
            _field("Subject"),
            _field("WhatId", "reference", ["Account", "Opportunity"]),
            _field("SecondPolyId", "reference", ["Account", "Contact"]),
        ],
    })
    counts = {"Account": 1, "Opportunity": 1, "Contact": 1, "Task": 1}

    import pytest
    with pytest.raises(ValueError, match="more than one polymorphic reference field"):
        build_recipe(sf, ["Account", "Opportunity", "Contact", "Task"], counts, stage_dir=str(tmp_path))
