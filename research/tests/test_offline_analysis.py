import json
import sys
import unittest
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from protocol.offline_report import analyze, join_results, markdown_table
from protocol.selection import manifest, select_stratified, validate_manifest, validate_no_leakage


class SelectionTests(unittest.TestCase):
    def test_stratification_reproducibility_hash_and_no_leakage(self):
        tasks = [{"id": str(i), "instruction": f"task {i}", "instruction_type": kind,
                  "spreadsheet_path": f"spreadsheet/{i}", "answer_position": "A1", "answer_sheet": "S",
                  "data_position": "A1:B2", "golden_xlsx": "must-not-copy"}
                 for i, kind in enumerate(["Cell-Level Manipulation"] * 4 + ["Sheet-Level Manipulation"] * 4)]
        counts = {"Cell-Level Manipulation": 2, "Sheet-Level Manipulation": 2}
        first, heldout = select_stratified(tasks, counts, 7)
        self.assertEqual(first, select_stratified(tasks, counts, 7)[0])
        self.assertEqual(len(first), 4); self.assertEqual(len(heldout), 4)
        value = manifest("development", first, 7, "source-hash")
        validate_manifest(value)
        self.assertNotIn("golden", json.dumps(value).lower())
        altered = {**value, "seed": 8}
        with self.assertRaises(ValueError): validate_manifest(altered)
        with self.assertRaises(ValueError): validate_no_leakage({"golden_value": 42})


def official(task_id, passed, correct=1, cells=1):
    return {"id": task_id, "status": "graded", "pass": passed, "correct": correct, "cells": cells}


def internal(task_id, fulfilled, first, actions):
    return {"id": task_id, "internal_status": "FULFILLED" if fulfilled else "UNFULFILLED",
            "artifact_valid": True, "first_mutation_pass": first,
            "usage": {"actions": actions, "tokens": actions * 10, "latency_ms": actions * 100, "cost": actions / 100}}


class OfflineAnalysisTests(unittest.TestCase):
    def test_join_is_paired_and_ffr_recovery_table_are_correct(self):
        official_rows = [official("1", True), official("2", False, 0)]
        arms = {
            "A": join_results([internal("1", False, None, 1), internal("2", False, None, 1)], official_rows),
            "B": join_results([internal("1", True, None, 1), internal("2", True, None, 1)], official_rows),
            "C": join_results([internal("1", True, None, 1), internal("2", False, None, 1)], official_rows),
            "D": join_results([internal("1", True, False, 2), internal("2", True, False, 2)], official_rows),
        }
        report = analyze(arms, samples=100, seed=3)
        self.assertEqual(report["metrics"]["B"]["false_fulfilment_rate"], .5)
        self.assertEqual(report["metrics"]["D"]["recovery_yield"], .5)
        table = markdown_table(report)
        self.assertIn("| Arm | Pass rate | Cell accuracy | FFR |", table)
        self.assertEqual(sum(line.startswith("| A ") for line in table.splitlines()), 1)

    def test_join_rejects_missing_or_duplicate_pairs(self):
        with self.assertRaises(ValueError): join_results([internal("1", False, None, 1)], [official("2", False)])
        with self.assertRaises(ValueError): join_results([internal("1", False, None, 1)] * 2, [official("1", False)])

    def test_unverified_one_shot_claims_are_in_ffr_denominator(self):
        rows = [internal("1", False, None, 1), internal("2", False, None, 1)]
        for row in rows:
            row["internal_status"] = "FULFILLED_UNVERIFIED"
        joined = join_results(rows, [official("1", True), official("2", False, 0)])
        report = analyze({arm: joined for arm in "ABCD"}, samples=10, seed=1)
        self.assertEqual(report["metrics"]["A"]["false_fulfilment_rate"], .5)
        self.assertEqual(report["metrics"]["A"]["completion_claim_precision"], .5)
        self.assertIsNone(report["metrics"]["A"]["internal_eval_precision"])

    def test_unknown_completion_label_is_rejected(self):
        row = internal("1", False, None, 1); row["internal_status"] = "LOOKS_GOOD"
        with self.assertRaisesRegex(ValueError, "unknown internal_status"):
            join_results([row], [official("1", True)])

    def test_unverified_one_shot_completion_claim_is_in_ffr_denominator(self):
        rows = join_results([
            {"id": "1", "internal_status": "FULFILLED_UNVERIFIED", "usage": {}},
            {"id": "2", "internal_status": "FULFILLED_UNVERIFIED", "usage": {}},
        ], [official("1", True), official("2", False, 0)])
        arms = {arm: rows for arm in "ABCD"}
        metrics = analyze(arms, samples=10)["metrics"]["A"]
        self.assertEqual(metrics["false_fulfilment_rate"], .5)
        self.assertEqual(metrics["completion_claim_precision"], .5)
        self.assertIsNone(metrics["internal_eval_precision"])

    def test_failure_schema_contains_exact_registered_taxonomy(self):
        schema = json.loads((RESEARCH / "protocol" / "failure_assignment.schema.json").read_text())
        labels = set(schema["properties"]["classes"]["items"]["enum"])
        self.assertEqual(len(labels), 12)
        self.assertIn("evaluation_false_positive", labels)
        self.assertIn("budget_failure", labels)

    def test_official_disagreement_adds_evaluator_error_classes_only_when_evaluated(self):
        false_positive = internal("1", True, False, 1)
        false_positive["terminal_eval"] = {"passed": True}
        false_negative = internal("2", False, False, 1)
        false_negative["terminal_eval"] = {"passed": False}
        rows = join_results([false_positive, false_negative],
                            [official("1", False, 0), official("2", True)])
        self.assertIn("evaluation_false_positive", rows[0]["failure_classes"])
        self.assertIn("evaluation_false_negative", rows[1]["failure_classes"])

    def test_preregistered_assessment_cannot_ignore_reliability_gates(self):
        rows_a = [join_results([internal(str(i), False, None, 1)], [official(str(i), False, 0)])[0]
                  for i in range(10)]
        rows_d = []
        for i in range(10):
            item = internal(str(i), True, False, 2)
            rows_d.extend(join_results([item], [official(str(i), i < 9, int(i < 9))]))
        report = analyze({"A": rows_a, "B": rows_a, "C": rows_a, "D": rows_d}, samples=100, seed=2)
        assessment = report["preregistered_assessment"]
        self.assertTrue(assessment["criteria"]["D_minus_A_at_least_8_points"])
        self.assertFalse(assessment["criteria"]["D_false_fulfilment_below_5_percent"])
        self.assertEqual(assessment["result"], "partially_supported_quantitatively")


if __name__ == "__main__": unittest.main()
