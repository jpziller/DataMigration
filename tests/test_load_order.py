from load_order import _group_cycle_members, compute_load_order


def test_simple_parent_child_order():
    objects = ["Account", "Contact"]
    edges = [{"child": "Contact", "parent": "Account", "field": "AccountId"}]
    result = compute_load_order(objects, edges)

    by_name = {row["object"]: row for row in result["order"]}
    assert by_name["Account"]["level"] == 0
    assert by_name["Contact"]["level"] == 1
    assert by_name["Account"]["sequence"] < by_name["Contact"]["sequence"]
    assert result["unresolved_cycles"] == []
    assert result["self_references"] == {}


def test_diamond_dependency_order():
    # Account is a shared grandparent of Opportunity via both Contact and
    # a direct edge -- Opportunity must land after both its parents.
    objects = ["Account", "Contact", "Opportunity"]
    edges = [
        {"child": "Contact", "parent": "Account", "field": "AccountId"},
        {"child": "Opportunity", "parent": "Account", "field": "AccountId"},
        {"child": "Opportunity", "parent": "Contact", "field": "ContactId"},
    ]
    result = compute_load_order(objects, edges)
    by_name = {row["object"]: row for row in result["order"]}

    assert by_name["Account"]["level"] == 0
    assert by_name["Opportunity"]["level"] > by_name["Account"]["level"]
    assert by_name["Opportunity"]["level"] > by_name["Contact"]["level"]


def test_self_reference_is_reported_not_treated_as_a_cycle():
    objects = ["Case"]
    edges = [{"child": "Case", "parent": "Case", "field": "ParentId"}]
    result = compute_load_order(objects, edges)

    assert result["self_references"] == {"Case": ["ParentId"]}
    assert result["unresolved_cycles"] == []
    assert [row["object"] for row in result["order"]] == ["Case"]


def test_unresolved_two_object_cycle():
    objects = ["A", "B"]
    edges = [
        {"child": "A", "parent": "B", "field": "BId"},
        {"child": "B", "parent": "A", "field": "AId"},
    ]
    result = compute_load_order(objects, edges)

    assert result["order"] == []
    assert result["unresolved_cycles"] == [["A", "B"]]


def test_group_cycle_members_groups_disconnected_cycles_separately():
    remaining = {"A", "B", "C", "D"}
    parents_of = {
        "A": {"B"}, "B": {"A"},   # cycle 1
        "C": {"D"}, "D": {"C"},   # cycle 2, unrelated to cycle 1
    }
    groups = _group_cycle_members(remaining, parents_of)

    assert sorted(groups) == [["A", "B"], ["C", "D"]]
