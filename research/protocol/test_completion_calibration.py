try:
    from research.protocol.completion_calibration import (
        coverage_aware_three_valued,
        legacy_policy,
        strict_three_valued,
    )
except ModuleNotFoundError:  # canonical image has /app/research on PYTHONPATH
    from protocol.completion_calibration import (
        coverage_aware_three_valued,
        legacy_policy,
        strict_three_valued,
    )


def candidate(*, truncated=False, statuses=None, compiled=True, coverage=1.0,
              formula_representation_ambiguous=False):
    statuses = statuses or {
        "artifact-valid": "pass", "preservation": "pass", "nonblank": "pass",
        "type": "pass", "output-shape": "pass", "formula-errors": "pass",
        "semantic": "pass",
    }
    return {
        "contract_compiled": compiled,
        "required_eval_ids": list(statuses),
        "eval_results": {key: {"status": value} for key, value in statuses.items()},
        "eval_coverage": coverage,
        "source_observation": {"truncated": truncated},
        "formula_representation_ambiguous": formula_representation_ambiguous,
        "artifact_valid": statuses.get("artifact-valid") == "pass",
        "constraint_violation": statuses.get("preservation") == "fail",
    }


def test_legacy_reproduces_binary_all_pass_gate():
    assert legacy_policy(candidate()) == "FULFILLED"
    row = candidate()
    row["eval_results"]["type"]["status"] = "fail"
    assert legacy_policy(row) == "UNFULFILLED"


def test_three_valued_separates_missing_evidence_from_failure():
    assert strict_three_valued(candidate(compiled=False, coverage=0)) == "UNKNOWN"
    row = candidate(statuses={"artifact-valid": "pass", "semantic": "error"})
    assert strict_three_valued(row) == "UNKNOWN"


def test_coverage_aware_policy_refuses_positive_claim_on_truncation():
    assert coverage_aware_three_valued(candidate(truncated=True)) == "UNKNOWN"
    assert coverage_aware_three_valued(candidate()) == "FULFILLED"


def test_coverage_aware_policy_preserves_hard_negative():
    row = candidate()
    row["eval_results"]["artifact-valid"]["status"] = "fail"
    row["artifact_valid"] = False
    assert coverage_aware_three_valued(row) == "UNFULFILLED"


def test_formula_result_type_disagreement_is_unknown_not_accepted():
    row = candidate(formula_representation_ambiguous=True)
    row["eval_results"]["type"]["status"] = "fail"
    assert coverage_aware_three_valued(row) == "UNKNOWN"
