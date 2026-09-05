import json
import unittest
from pathlib import Path

from protocol.analysis import (
    arm_metrics,
    breakdown,
    failure_distribution,
    mcnemar_exact,
    paired_bootstrap_ci,
    paired_pass_difference,
    validate_ledger,
)


HERE = Path(__file__).parent


def row(task_id, official, status="FULFILLED", first=None, valid=True, **extra):
    base = {"task_id": task_id, "official_pass": official, "internal_status": status,
            "first_mutation_pass": first, "artifact_valid": valid, "total_cells": 2,
            "correct_cells": 2 if official else 1, "actions": 1, "tokens": 10,
            "latency_ms": 100, "cost_usd": .01, "task_family": extra.pop("task_family", "formula")}
    base.update(extra)
    return base


class MetricsTests(unittest.TestCase):
    def test_hand_calculable_metrics(self):
        rows = [row("1", True, first=True), row("2", True, first=False),
                row("3", False, first=False), row("4", False, status="UNFULFILLED", first=False, valid=False)]
        got = arm_metrics(rows)
        self.assertEqual(got["pass_rate"], .5)
        self.assertEqual(got["cell_accuracy"], .75)
        self.assertEqual(got["false_fulfilment_rate"], 1 / 3)
        self.assertEqual(got["internal_eval_precision"], 2 / 3)
        self.assertEqual(got["internal_eval_recall"], 1)
        self.assertEqual(got["recovery_yield"], 1 / 3)
        self.assertEqual(got["artifact_validity_rate"], .75)

    def test_paired_effect_and_exact_mcnemar(self):
        a = [row(str(i), i == 0) for i in range(4)]
        d = [row(str(i), i < 3) for i in range(4)]
        self.assertEqual(paired_pass_difference(a, d), .5)
        test = mcnemar_exact(a, d)
        self.assertEqual((test["control_only"], test["treatment_only"]), (0, 2))
        self.assertEqual(test["p_value"], .5)

    def test_bootstrap_is_paired_and_reproducible(self):
        a = [row(str(i), False) for i in range(5)]
        d = [row(str(i), True) for i in range(5)]
        first = paired_bootstrap_ci(a, d, samples=100, seed=7)
        self.assertEqual(first, paired_bootstrap_ci(a, d, samples=100, seed=7))
        self.assertEqual((first["estimate"], first["lower"], first["upper"]), (1, 1, 1))

    def test_pair_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            paired_pass_difference([row("1", True)], [row("2", True)])

    def test_breakdowns_and_failure_taxonomy(self):
        rows = [row("1", True, task_family="formula", failure_classes=[]),
                row("2", False, task_family="value", failure_classes=["execution_failure", "budget_failure"])]
        self.assertEqual(set(breakdown(rows, "task_family")), {"formula", "value"})
        self.assertEqual(failure_distribution(rows), {"budget_failure": 1, "execution_failure": 1})


class SchemaTests(unittest.TestCase):
    def test_template_validates_and_schema_has_trace_fields(self):
        template = json.loads((HERE / "ledger.template.json").read_text())
        schema = json.loads((HERE / "ledger.schema.json").read_text())
        self.assertEqual(validate_ledger(template), [])
        self.assertEqual(schema["additionalProperties"], False)
        required_provenance = schema["properties"]["provenance"]["required"]
        self.assertEqual(set(required_provenance), {"git_commit", "run_manifest_sha256", "evidence_root_sha256", "scorer_commit", "created_at"})

    def test_invalid_ledger_is_rejected(self):
        self.assertIn("invalid:decision", validate_ledger({"decision": "success"}))

    def test_preregistration_contains_four_distinct_arms_and_fixed_budgets(self):
        protocol = json.loads((HERE / "preregistered_experiment.json").read_text())
        self.assertEqual(set(protocol["arms"]), {"A", "B", "C", "D"})
        self.assertEqual(protocol["fixed_conditions"]["action_budget"], 12)
        self.assertEqual(protocol["success_criteria"]["D_minus_A_pass_rate_points_min"], 8)
        self.assertEqual(protocol["multimodal_protocol_eval"]["status"], "not_applicable")


if __name__ == "__main__":
    unittest.main()
