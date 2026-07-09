from batch_advisor import _ladder_index, _load_heuristics, _seed_lookup, _step

LADDER = [50, 100, 200, 500, 1000, 2000, 5000, 10000]


def test_ladder_index_exact_rung():
    assert _ladder_index(LADDER, 500) == 3


def test_ladder_index_nearest_rung():
    # 600 is closer to 500 (100 away) than 1000 (400 away)
    assert _ladder_index(LADDER, 600) == 3


def test_step_up_one_rung():
    assert _step(LADDER, 500, 1) == 1000


def test_step_down_one_rung():
    assert _step(LADDER, 500, -1) == 200


def test_step_clamps_at_top_of_ladder():
    assert _step(LADDER, 10000, 3) == 10000


def test_step_clamps_at_bottom_of_ladder():
    assert _step(LADDER, 50, -3) == 50


def test_seed_lookup_exact_object_seed():
    heuristics = _load_heuristics()
    start, why = _seed_lookup(heuristics, "Opportunity")
    assert start == 200
    assert "Opportunity" in why


def test_seed_lookup_prefix_seed():
    heuristics = _load_heuristics()
    start, why = _seed_lookup(heuristics, "SBQQ__Quote__c")
    assert start == 50
    assert "SBQQ__" in why


def test_seed_lookup_falls_back_to_default():
    heuristics = _load_heuristics()
    start, why = _seed_lookup(heuristics, "SomeCustomObject__c")
    assert start == heuristics["default_batch_size"]
    assert "No seed knowledge" in why
