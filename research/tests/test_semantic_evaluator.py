import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from adapters.spreadsheet import KIND
from experiment.runner import Arm, ExperimentRunner, ModelReply, RunConfig, Task
from services.spreadsheet import SpreadsheetServices


class RoleProvider:
    def __init__(self, replies): self.replies = list(replies); self.prompts = []
    def complete(self, prompt, *, model, temperature):
        self.prompts.append(prompt)
        return ModelReply(self.replies.pop(0), 3, 2, .01, f"role-{len(self.prompts)}")


def config(arm):
    return RunConfig("semantic", arm, "same-model", "pinned-v1", 0, 100, 8, 10000, 1,
                     "sha256:x", "none", "fixed", {"transport": 0})


class IsolatedSemanticEvaluatorTest(unittest.TestCase):
    def run_arm(self, arm, replies):
        td = tempfile.TemporaryDirectory(); root = Path(td.name)
        artifact = root / "initial.xlsx"
        wb = Workbook(); ws = wb.active; ws.title = "Data"; ws["A1"] = 2; ws["B1"] = None
        wb.save(artifact); wb.close()
        context = {"answer_sheet": "Data", "answer_position": "B1", "expected_type": "number",
                   "workbook_observation": {"facts": {"cells": [
                       {"selector": "Data!A1", "value": 2, "data_type": "n"},
                       {"selector": "Data!B1", "value": None, "data_type": "n"}]},
                       "truncation": {"truncated": False}}}
        provider = RoleProvider(replies); out = root / "out"
        result = ExperimentRunner(config(arm), SpreadsheetServices(), provider, out).run(
            [Task("t", "put twice A1 in B1", artifact, KIND, context)])[0]
        return td, out, provider, result

    def value(self, out, result):
        wb = load_workbook(out / result["output"]); value = wb["Data"]["B1"].value; wb.close(); return value

    def test_c_evaluates_wrong_once_and_never_repairs(self):
        replies = [
            '{"description":"B1 equals twice A1"}',
            '{"writes":[{"selector":"Data!B1","value":3}]}',
            '{"verdict":"fail","expected_state":{"Data!B1":4},"rationale":"three is not twice two","confidence":0.99}',
        ]
        td, out, provider, result = self.run_arm(Arm.C, replies); self.addCleanup(td.cleanup)
        self.assertEqual(self.value(out, result), 3)
        self.assertFalse(result["terminal_eval"]["passed"])
        self.assertEqual(result["usage"]["model_calls"], 3)
        self.assertEqual(result["usage"]["tokens"], 15)
        traces = [json.loads(line) for line in (out / "traces" / "t.jsonl").read_text().splitlines()]
        self.assertEqual([row["purpose"] for row in traces], ["contract", "action_generation", "independent_evaluation"])
        self.assertEqual(traces[-1]["provider_request_id"], "role-3")

    def test_d_acts_first_then_repairs_from_isolated_failed_verdict(self):
        replies = [
            '{"description":"B1 equals twice A1"}',
            '{"writes":[{"selector":"Data!B1","value":3}]}',
            '{"verdict":"fail","expected_state":{"Data!B1":4},"rationale":"expected four","confidence":1}',
            '{"writes":[{"selector":"Data!B1","value":4}]}',
            '{"verdict":"pass","expected_state":{"Data!B1":4},"rationale":"four is twice two","confidence":1}',
        ]
        td, out, provider, result = self.run_arm(Arm.D, replies); self.addCleanup(td.cleanup)
        self.assertEqual(self.value(out, result), 4)
        self.assertEqual(result["status"], "fulfilled")
        self.assertEqual(result["usage"]["model_calls"], 5)
        self.assertEqual(result["usage"]["tokens"], 25)
        traces = [json.loads(line) for line in (out / "traces" / "t.jsonl").read_text().splitlines()]
        self.assertEqual([row["purpose"] for row in traces], ["contract", "action_generation",
                         "independent_evaluation", "action_generation", "independent_evaluation"])
        # The first action occurs before the first independent-evaluation call.
        events = [json.loads(line) for line in (out / "events" / "t.jsonl").read_text().splitlines()]
        self.assertTrue(any(e["event_type"] == "semantic_evaluator_verdict" for e in events))
        evaluator_prompts = [p for p in provider.prompts if "independent_semantic_evaluator" in p]
        self.assertEqual(len(evaluator_prompts), 2)
        self.assertTrue(all("writes" not in p and "golden" not in p.lower() for p in evaluator_prompts))
        repair_prompt = provider.prompts[3]
        self.assertIn("state_discrepancy", repair_prompt)
        self.assertNotIn("independent_semantic_evaluator", repair_prompt)

    def test_malformed_evaluator_response_is_uncertain_and_never_passes(self):
        replies = ['{"description":"B1 equals twice A1"}',
                   '{"writes":[{"selector":"Data!B1","value":4}]}',
                   '{"verdict":"pass"}']
        td, out, provider, result = self.run_arm(Arm.D, replies); self.addCleanup(td.cleanup)
        self.assertEqual(result["status"], "unfulfilled:evaluation_uncertain")
        self.assertFalse(result["terminal_eval"]["passed"])
        semantic = next(e for e in result["terminal_eval"]["details"]["evals"] if e["eval_id"] == "semantic")
        self.assertEqual(semantic["status"], "uncertain")
        self.assertIn("malformed", semantic["message"])

    def test_a_and_b_never_invoke_evaluation_role(self):
        cases = {
            Arm.A: ['{"writes":[{"selector":"Data!B1","value":4}]}'],
            Arm.B: ['{"description":"B1 equals twice A1"}', '{"writes":[{"selector":"Data!B1","value":4}]}'],
        }
        for arm, replies in cases.items():
            with self.subTest(arm=arm):
                td, out, provider, result = self.run_arm(arm, replies); self.addCleanup(td.cleanup)
                self.assertFalse(any("independent_semantic_evaluator" in p for p in provider.prompts))
                self.assertEqual(result["usage"]["model_calls"], 1 if arm is Arm.A else 2)


if __name__ == "__main__": unittest.main()
