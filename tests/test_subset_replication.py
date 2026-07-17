import subset_replication as subrep


def test_in_clause_single_chunk():
    clause = subrep._in_clause("AccountId", {"001A", "001B"})
    assert clause == "(AccountId IN ('001A', '001B'))"


def test_in_clause_chunks_over_200_ids():
    ids = {f"001{i:015d}" for i in range(450)}
    clause = subrep._in_clause("AccountId", ids)
    assert clause.count(" OR ") == 2  # 450 ids -> 3 chunks of <=200
    assert clause.startswith("(") and clause.endswith(")")


def test_in_clause_escapes_quotes_and_backslashes():
    clause = subrep._in_clause("Name", {"O'Brien", "back\\slash"})
    assert "O\\'Brien" in clause
    assert "back\\\\slash" in clause


def test_build_child_where_single_field_single_parent():
    edges = [{"child": "Contact", "parent": "Account", "field": "AccountId",
              "is_master_detail": False, "is_nillable": True}]
    replicated_ids = {"Account": {"001A", "001B"}}
    where = subrep._build_child_where("Contact", edges, replicated_ids)
    assert where == "(AccountId IN ('001A', '001B'))"


def test_build_child_where_polymorphic_field_unions_targets():
    """A polymorphic field (same field, multiple parents) should union
    every already-replicated parent's Ids under that one field -- OR
    semantics with no separate detection step."""
    edges = [
        {"child": "Task", "parent": "Account", "field": "WhatId", "is_master_detail": False, "is_nillable": True},
        {"child": "Task", "parent": "Opportunity", "field": "WhatId", "is_master_detail": False, "is_nillable": True},
    ]
    replicated_ids = {"Account": {"001A"}, "Opportunity": {"006B"}}
    where = subrep._build_child_where("Task", edges, replicated_ids)
    assert where == "(WhatId IN ('001A', '006B'))"


def test_build_child_where_distinct_fields_combine_with_and():
    edges = [
        {"child": "Contact", "parent": "Account", "field": "AccountId", "is_master_detail": False, "is_nillable": True},
        {"child": "Contact", "parent": "User", "field": "OwnerId", "is_master_detail": False, "is_nillable": True},
    ]
    replicated_ids = {"Account": {"001A"}, "User": {"005X"}}
    where = subrep._build_child_where("Contact", edges, replicated_ids)
    assert where == "(AccountId IN ('001A')) AND (OwnerId IN ('005X'))"


def test_build_child_where_self_reference_is_not_a_gate():
    edges = [{"child": "Account", "parent": "Account", "field": "ParentId", "is_master_detail": False, "is_nillable": True}]
    where = subrep._build_child_where("Account", edges, replicated_ids={})
    assert where is None


def test_build_child_where_none_when_no_in_scope_parent_replicated():
    edges = [{"child": "Contact", "parent": "Account", "field": "AccountId", "is_master_detail": False, "is_nillable": True}]
    where = subrep._build_child_where("Contact", edges, replicated_ids={})
    assert where is None


def test_build_child_where_empty_sentinel_when_parent_subset_empty():
    edges = [{"child": "Contact", "parent": "Account", "field": "AccountId", "is_master_detail": False, "is_nillable": True}]
    replicated_ids = {"Account": set()}
    where = subrep._build_child_where("Contact", edges, replicated_ids)
    assert where == ""


def test_build_child_where_ignores_edges_for_other_children():
    edges = [
        {"child": "Contact", "parent": "Account", "field": "AccountId", "is_master_detail": False, "is_nillable": True},
        {"child": "Opportunity", "parent": "Account", "field": "AccountId", "is_master_detail": False, "is_nillable": True},
    ]
    replicated_ids = {"Account": {"001A"}}
    where = subrep._build_child_where("Contact", edges, replicated_ids)
    assert where == "(AccountId IN ('001A'))"
