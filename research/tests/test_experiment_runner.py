import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from experiment.runner import Arm, EvaluationResult, ExecutionResult, ExperimentRunner, ModelReply, RunConfig, Task


class FakeProvider:
    def __init__(self): self.calls = []
    def complete(self, prompt, *, model, temperature):
        self.calls.append((prompt, model, temperature))
        return ModelReply("ok", 2, 1, 0.01, f"fake-{len(self.calls)}")


class FlakyProvider(FakeProvider):
    def complete(self, prompt, *, model, temperature):
        self.calls.append((prompt, model, temperature))
        if len(self.calls) == 1:
            raise ConnectionError("synthetic transport failure")
        return ModelReply("ok", 2, 1, 0.01, "recovered")


class FakeServices:
    def __init__(self): self.calls = []
    def compile_contract(self, task, runtime):
        self.calls.append("compile")
        runtime.complete("compile", purpose="contract")
        return {"id": task.id, "assertions": ["desired"]}
    def execute_once(self, task, contract, destination, runtime):
        self.calls.append("direct" if contract is None else "execute")
        runtime.complete("direct" if contract is None else "fulfil", purpose="action_generation")
        runtime.action("write_fixture")
        destination.write_text("changed")
        return ExecutionResult(destination, "ok", {})
    def evaluate_once(self, task, contract, artifact, runtime):
        self.calls.append("evaluate")
        return EvaluationResult(False, "fail", {"discrepancy": "fixture"})
    def reconcile(self, task, contract, destination, runtime):
        self.calls.append("reconcile")
        runtime.action("transition-1")
        runtime.event("observation", {"iteration": 1})
        runtime.event("discrepancy", {"iteration": 1})
        runtime.action("transition-2")
        destination.write_text("reconciled")
        result = ExecutionResult(destination, "fulfilled", {"iterations": 2})
        evaluation = EvaluationResult(True, "pass", {})
        runtime.event("terminal_evaluation", {"passed": True})
        return result, evaluation


def config(arm):
    return RunConfig("fixture-exp", arm, "fake-model", "fake-v1", 0, 20, 3, 10_000, 1.0,
                     "sha256:fixture", "fixture-recalc", "fixture-scorer", {"transport": 0})


class FourArmTests(unittest.TestCase):
    def run_arm(self, arm):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        artifact = root / "initial.txt"; artifact.write_text("initial")
        provider, services = FakeProvider(), FakeServices()
        out = root / "out"
        result = ExperimentRunner(config(arm), services, provider, out).run(
            [Task("t1", "make desired", artifact, "text", {"bounded": True})]
        )[0]
        return td, out, provider, services, result

    def test_treatment_boundaries_and_outputs(self):
        expected = {
            Arm.A: (["direct"], 1, None),
            Arm.B: (["compile", "execute"], 2, None),
            Arm.C: (["compile", "execute", "evaluate"], 2, False),
            Arm.D: (["compile", "reconcile"], 1, True),
        }
        for arm, (calls, model_calls, eval_passed) in expected.items():
            with self.subTest(arm=arm):
                td, out, provider, services, result = self.run_arm(arm)
                self.addCleanup(td.cleanup)
                self.assertEqual(services.calls, calls)
                self.assertEqual(len(provider.calls), model_calls)
                self.assertTrue((out / result["output"]).exists())
                self.assertEqual(len(result["output_artifact_hash"]), 64)
                self.assertTrue((out / "run_manifest.json").exists())
                self.assertTrue((out / "traces" / "t1.jsonl").exists())
                self.assertTrue((out / "events" / "t1.jsonl").exists())
                prediction = json.loads((out / "predictions.jsonl").read_text())
                self.assertEqual(prediction["id"], "t1")
                self.assertEqual(result["rendered_eval"], "delegated_to_adapter")
                if eval_passed is None:
                    self.assertIsNone(result["terminal_eval"])
                    self.assertEqual(result["internal_status"], "FULFILLED_UNVERIFIED")
                    self.assertEqual(result["termination_reason"], "one_shot_completed_unverified")
                else:
                    self.assertEqual(result["terminal_eval"]["passed"], eval_passed)
                    self.assertEqual(result["internal_status"], "FULFILLED" if eval_passed else "UNFULFILLED")

    def test_budget_failure_projects_original_and_is_traced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "initial.txt"; artifact.write_text("original")
            cfg = RunConfig(**{**config(Arm.A).__dict__, "max_actions": 0})
            out = root / "out"
            result = ExperimentRunner(cfg, FakeServices(), FakeProvider(), out).run(
                [Task("t1", "intent", artifact, "text", {})])[0]
            self.assertTrue(result["status"].startswith("error: BudgetExceeded"))
            self.assertEqual((out / result["output"]).read_text(), "original")
            events = [json.loads(line)["event_type"] for line in (out / "events" / "t1.jsonl").read_text().splitlines()]
            self.assertIn("task_error", events)
            self.assertIn("fallback_projection", events)
            self.assertEqual(result["internal_status"], "UNFULFILLED")
            self.assertEqual(result["termination_reason"], "execution_error")
            self.assertEqual(result["failure_classes"], ["budget_failure", "execution_failure"])

    def test_transport_retry_is_uniformly_enforced_and_each_attempt_traced(self):
        for arm in Arm:
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as td:
                root = Path(td); artifact = root / "initial.txt"; artifact.write_text("initial")
                cfg = RunConfig(**{**config(arm).__dict__, "retry_policy": {"model_transport_retries": 1,
                                                                            "action_retries": 0}})
                provider = FlakyProvider(); out = root / "out"
                result = ExperimentRunner(cfg, FakeServices(), provider, out).run(
                    [Task("t1", "intent", artifact, "text", {})])[0]
                traces = [json.loads(line) for line in (out / "traces" / "t1.jsonl").read_text().splitlines()]
                self.assertEqual((traces[0]["attempt"], traces[0]["error"]),
                                 (1, "ConnectionError: synthetic transport failure"))
                self.assertEqual(traces[1]["attempt"], 2)
                self.assertIsNone(traces[1]["error"])
                self.assertEqual(result["usage"]["model_calls"], len(provider.calls))
                self.assertEqual(result["usage"]["successful_model_calls"], result["usage"]["model_calls"] - 1)
                events = (out / "events" / "t1.jsonl").read_text()
                self.assertIn('"event_type": "model_transport_retry"', events)

    def test_nonempty_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "a"; artifact.write_text("a")
            out = root / "out"; out.mkdir(); (out / "existing").write_text("do not overwrite")
            with self.assertRaises(FileExistsError):
                ExperimentRunner(config(Arm.A), FakeServices(), FakeProvider(), out).run(
                    [Task("t", "i", artifact, "text", {})])


if __name__ == "__main__":
    unittest.main()
