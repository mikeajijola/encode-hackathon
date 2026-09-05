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

    def test_failure_schema_contains_exact_registered_taxonomy(self):
        schema = json.loads((RESEARCH / "protocol" / "failure_assignment.schema.json").read_text())
        labels = set(schema["properties"]["classes"]["items"]["enum"])
        self.assertEqual(len(labels), 12)
        self.assertIn("evaluation_false_positive", labels)
        self.assertIn("budget_failure", labels)


if __name__ == "__main__": unittest.main()
