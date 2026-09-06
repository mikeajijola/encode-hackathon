import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from experiment.runner import Arm, BudgetExceeded, ModelReply, RunConfig, TaskRuntime
from protocol.mechanism_validation import revise_d_manifest


class Provider:
    def complete(self, prompt, *, model, temperature):
        return ModelReply("ok", 10, 10)


class MechanismValidationTest(unittest.TestCase):
    def config(self, **changes):
        values = dict(experiment_id="x", arm=Arm.D, model="m", model_version="v",
                      temperature=0, max_tokens=16, max_actions=12,
                      max_wall_time_ms=300_000, max_cost=100,
                      environment_image_digest="sha256:" + "a" * 64,
                      recalculation_engine="lo", scorer_commit="b" * 40,
                      retry_policy={})
        values.update(changes)
        return RunConfig(**values)

    def test_measured_cost_ignores_research_limit_but_enforces_emergency_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = TaskRuntime(self.config(token_policy="measured_cost",
                operational_emergency_token_ceiling=30), Provider(), root / "trace", root / "events")
            runtime.complete("one", purpose="test")
            with self.assertRaisesRegex(BudgetExceeded, "operational_emergency"):
                runtime.complete("two", purpose="test")

    def test_fixed_policy_still_enforces_legacy_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = TaskRuntime(self.config(), Provider(), root / "trace", root / "events")
            with self.assertRaisesRegex(BudgetExceeded, "token_budget"):
                runtime.complete("one", purpose="test")

    def test_revision_preserves_frozen_development_base(self):
        base = {"run_config": {"arm": "D", "max_tokens": 16000, "deviations": []},
                "task_selection": {"name": "development", "tasks": [{}] * 20},
                "reproducibility": {"deviations": []}}
        revised = revise_d_manifest(base, "d-mechanism-v1")
        self.assertEqual(base["run_config"]["max_tokens"], 16000)
        self.assertEqual(revised["run_config"]["token_policy"], "measured_cost")
        self.assertIsNone(revised["experiment_revision"]["research_token_budget_per_task"])
        self.assertEqual(revised["experiment_revision"]["preserves_prior_result"],
                         "fixed-budget development experiment — 16,000 tokens/task")


if __name__ == "__main__":
    unittest.main()
