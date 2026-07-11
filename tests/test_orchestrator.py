"""Coverage for orchestrator.py's assess_tier() -- the trust-critical,
deterministic logic docs/ORCHESTRATOR_DESIGN.md section 1 insists must
never be model judgment. Every tier boundary is covered explicitly and
independently, so a change to one trigger can't silently break another.
"""
from orchestrator import assess_tier, TIER_NAMES

_CLEAN = {
    "operation": "insert", "submitted": 100, "succeeded": 100, "failed": 0,
    "ambiguous": 0, "external_id_not_found": 0, "lock_errors": 0,
    "failure_error_counts": {},
}

_SOME_HISTORY = [{
    "operation": "insert", "submitted": 100, "succeeded": 98, "failed": 2,
    "ambiguous": 0, "external_id_not_found": 0, "lock_errors": 0,
    "failure_error_counts": {"DUPLICATE_VALUE:x:Jigsaw": 2},
    "duration_seconds": 50.0,
}]


def test_tier1_clean_run_with_history():
    result = assess_tier(_CLEAN, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 1
    assert result["coarse_approval_eligible"] is True


def test_tier1_cold_start_not_coarse_approval_eligible():
    result = assess_tier(_CLEAN, [], has_automation_risk_data=True)
    assert result["tier"] == 1
    assert result["coarse_approval_eligible"] is False


def test_tier2_known_signature_within_ceiling():
    current = {**_CLEAN, "submitted": 100, "failed": 2, "succeeded": 98,
               "failure_error_counts": {"DUPLICATE_VALUE:x:Jigsaw": 2}}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 2


def test_tier2_first_lock_error_no_prior_lock_error():
    current = {**_CLEAN, "lock_errors": 3}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 2


def test_tier3_band_between_tier2_and_tier3_ceiling_with_known_signature():
    # 5% failure, above the 2% tier-2 ceiling but within the 10% tier-3
    # ceiling, split across two already-known signatures (each well under
    # the repeated-identical-error tier-4 threshold on its own) -- must
    # still land in tier 3, not silently fall through to tier 1, and not
    # get bumped to tier 4 by the separate repeated-error trigger.
    history = [{**_SOME_HISTORY[0], "failure_error_counts": {"KNOWN_A": 1, "KNOWN_B": 1}}]
    current = {**_CLEAN, "submitted": 100, "failed": 5, "succeeded": 95,
               "failure_error_counts": {"KNOWN_A": 3, "KNOWN_B": 2}}
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 3


def test_tier3_novel_error_regardless_of_volume():
    current = {**_CLEAN, "submitted": 1000, "failed": 1, "succeeded": 999,
               "failure_error_counts": {"SOME_NEW_ERROR": 1}}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 3
    assert any("Novel" in r for r in result["reasons"])


def test_tier3_ambiguous_any_count():
    current = {**_CLEAN, "ambiguous": 1}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 3


def test_tier3_external_id_not_found_growth():
    history = [{**_SOME_HISTORY[0], "external_id_not_found": 2}]
    current = {**_CLEAN, "external_id_not_found": 3}
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 3


def test_tier3_external_id_not_found_within_baseline_is_fine():
    history = [{**_SOME_HISTORY[0], "external_id_not_found": 5}]
    current = {**_CLEAN, "external_id_not_found": 3}
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 1


def test_tier3_second_consecutive_lock_error():
    history = [{**_SOME_HISTORY[0], "lock_errors": 2}]
    current = {**_CLEAN, "lock_errors": 1}
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 3


def test_tier3_no_automation_risk_data():
    result = assess_tier(_CLEAN, _SOME_HISTORY, has_automation_risk_data=False)
    assert result["tier"] == 3


def test_tier4_failure_rate_over_ceiling():
    current = {**_CLEAN, "submitted": 100, "failed": 15, "succeeded": 85,
               "failure_error_counts": {"SOME_ERROR": 15}}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 4


def test_tier4_delete_is_always_tier4_even_when_clean():
    current = {**_CLEAN, "operation": "delete", "failed": 0}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True)
    assert result["tier"] == 4
    assert "unconditionally" in result["reasons"][0]


def test_tier4_delete_never_downgraded_by_clean_signals_or_history():
    # Even with a long clean history and zero failures, a delete op is
    # still tier 4 -- the one rule this design says never graduates.
    current = {**_CLEAN, "operation": "delete (dry run)"}
    result = assess_tier(current, _SOME_HISTORY * 10, has_automation_risk_data=True)
    assert result["tier"] == 4


def test_tier4_repeated_identical_error_over_row_threshold():
    # 15 identical, already-known failures out of 1000 (1.5% -- comfortably
    # within the plain failure-rate tier-2 ceiling on its own) still trips
    # tier 4 via the *separate* repeated-identical-error trigger (>= 1% of
    # 1000 = 10 rows), confirming the two triggers are independent.
    history = [{**_SOME_HISTORY[0], "failure_error_counts": {"DUPLICATE_VALUE:x:Jigsaw": 1}}]
    current = {**_CLEAN, "submitted": 1000, "failed": 15, "succeeded": 985,
               "failure_error_counts": {"DUPLICATE_VALUE:x:Jigsaw": 15}}
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 4


def test_tier4_elapsed_time_over_multiplier():
    history = [{**_SOME_HISTORY[0], "duration_seconds": 10.0, "submitted": 100}]
    current = {**_CLEAN, "duration_seconds": 1000.0}  # 10s/row vs history's 0.1s/row
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 4


def test_elapsed_time_check_skipped_gracefully_without_duration_data():
    history = [{**_SOME_HISTORY[0], "duration_seconds": None}]
    current = {**_CLEAN}  # no duration_seconds key at all
    result = assess_tier(current, history, has_automation_risk_data=True)
    assert result["tier"] == 1


def test_tier4_takes_priority_over_tier3_reasons_in_output():
    # Both a tier-3 trigger (no automation data) and a tier-4 trigger
    # (over the failure ceiling) fire together -- tier must be 4, and
    # both reasons should still be visible in the output.
    current = {**_CLEAN, "submitted": 100, "failed": 50, "succeeded": 50,
               "failure_error_counts": {"SOME_ERROR": 50}}
    result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=False)
    assert result["tier"] == 4
    assert len(result["reasons"]) >= 2


def test_prod_thresholds_are_tighter_than_uat():
    current = {**_CLEAN, "submitted": 100, "failed": 3, "succeeded": 97,
               "failure_error_counts": {"DUPLICATE_VALUE:x:Jigsaw": 3}}
    uat_result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True, environment="uat")
    prod_result = assess_tier(current, _SOME_HISTORY, has_automation_risk_data=True, environment="prod")
    # 3% failure: within uat's 2%..10% band (tier 3 via the explicit band
    # check), but over prod's tighter 5% tier-3 ceiling (tier 4).
    assert uat_result["tier"] == 3
    assert prod_result["tier"] == 4


def test_every_tier_result_includes_its_name_not_just_the_bare_number():
    # "Tier 3" means nothing out of context, same reason CLAUDE.md's Hard
    # Rules were given names -- every result must carry tier_name too.
    for current, history, has_data in [
        (_CLEAN, _SOME_HISTORY, True),
        ({**_CLEAN, "operation": "delete"}, _SOME_HISTORY, True),
        ({**_CLEAN, "ambiguous": 1}, _SOME_HISTORY, True),
        ({**_CLEAN, "submitted": 100, "failed": 50, "succeeded": 50,
          "failure_error_counts": {"X": 50}}, _SOME_HISTORY, True),
    ]:
        result = assess_tier(current, history, has_automation_risk_data=has_data)
        assert result["tier_name"] == TIER_NAMES[result["tier"]]


def test_tier_names_are_the_four_expected_ones():
    assert TIER_NAMES == {
        1: "Continue Silently",
        2: "Continue with Warning",
        3: "Pause and Ask",
        4: "Full Stop",
    }
