import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from adapters.spreadsheet import KIND
from experiment.runner import Arm, ExperimentRunner, ModelReply, RunConfig, Task
from services.spreadsheet import SpreadsheetServices
from tests.contract_fixtures import capability_records, contract_reply, transition_reply


class CaptureRuntime:
    def __init__(self, reply): self.reply, self.prompts = reply, []
    def complete(self, prompt, *, purpose):
        self.prompts.append((purpose, prompt)); return ModelReply(self.reply, 1, 1)


class QueueProvider:
    def __init__(self, replies): self.replies, self.prompts = list(replies), []
    def complete(self, prompt, *, model, temperature):
        self.prompts.append(prompt); return ModelReply(self.replies.pop(0), 1, 1)


class ContractCompilerV2Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.artifact = self.root / "initial.xlsx"
        wb = Workbook(); wb.active.title = "Data"; wb.active["A1"] = 2; wb.save(self.artifact); wb.close()
        self.context = {"answer_sheet": "Data", "answer_position": "B1", "expected_type": "number"}

    def tearDown(self): self.temp.cleanup()

    def task(self, intent="compute twice A1", manifests=None):
        return Task("t", intent, self.artifact, KIND, self.context,
                    capability_records() if manifests is None else manifests)

    def compile(self, reply, task=None):
        runtime = CaptureRuntime(reply)
        value = SpreadsheetServices().compile_contract(task or self.task(), runtime)
        return value, runtime

    def test_different_intents_produce_different_immutable_state_specs(self):
        computed, _ = self.compile(contract_reply("B1 equals twice A1", property="computed_value"))
        formula, _ = self.compile(contract_reply("B1 contains a reusable formula", property="formula_result",
                                                  output_type="any", uncertainty_allowed=True),
                                  self.task("place a reusable formula"))
        self.assertNotEqual(computed["desired_state"], formula["desired_state"])
        self.assertEqual(computed["desired_state"]["assertions"][0]["selectors"], ("workbook/Data/B1",))
        with self.assertRaises(TypeError): computed["intent"] = "changed"
        with self.assertRaises(TypeError): computed["desired_state"]["assertions"][0]["output"]["type"] = "text"

    def test_procedural_unknown_malformed_and_empty_proposals_are_rejected(self):
        empty_description = json.loads(contract_reply())
        empty_description["desired_state"]["assertions"][0]["description"] = ""
        cases = [
            contract_reply("First write a formula into B1"),
            contract_reply(extra={"steps": ["write B1"]}),
            json.dumps(empty_description),
            "{}",
            "not JSON",
            "prefix " + contract_reply(),
        ]
        for reply in cases:
            with self.subTest(reply=reply[:30]), self.assertRaises(ValueError): self.compile(reply)

    def test_missing_required_capability_or_evaluator_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "capability unavailable"):
            self.compile(contract_reply(), self.task(manifests=()))
        with self.assertRaisesRegex(ValueError, "required evaluator"):
            self.compile(contract_reply(evaluator="type"))

    def test_model_output_type_changes_internal_eval_contract(self):
        context = {"answer_sheet": "Data", "answer_position": "B1", "independent_expected": 4}
        task = Task("typed", "put twice A1 in B1", self.artifact, KIND, context, capability_records())
        provider = QueueProvider([
            contract_reply("B1 is textual", output_type="text"),
            transition_reply(),
        ])
        config = RunConfig("v2", Arm.C, "m", "v", 0, 100, 5, 10000, 1,
                           "sha256:x", "none", "fixed", {"transport": 0})
        result = ExperimentRunner(config, SpreadsheetServices(), provider, self.root / "typed-out").run([task])[0]
        self.assertFalse(result["terminal_eval"]["passed"])
        type_eval = next(item for item in result["terminal_eval"]["details"]["evals"] if item["eval_id"] == "type")
        self.assertEqual(type_eval["details"]["expected"], "text")
        self.assertEqual(type_eval["status"], "fail")

    def test_compiler_receives_exact_versioned_task_manifests(self):
        task = self.task()
        _, runtime = self.compile(contract_reply(), task)
        prompt = json.loads(runtime.prompts[0][1])
        self.assertEqual(prompt["capability_manifests"], json.loads(json.dumps(task.capability_manifests, default=str)))
        self.assertTrue(all("name" in item and "version" in item for item in prompt["capability_manifests"]))

    def test_action_and_eval_use_accepted_state_not_raw_compiler_response(self):
        raw = contract_reply("B1 is a numeric doubled result", property="computed_value")
        provider = QueueProvider([raw, transition_reply()])
        config = RunConfig("v2", Arm.B, "m", "v", 0, 100, 5, 10000, 1,
                           "sha256:x", "none", "fixed", {"transport": 0})
        result = ExperimentRunner(config, SpreadsheetServices(), provider, self.root / "out").run([self.task()])[0]
        self.assertEqual(result["status"], "ok")
        action = json.loads(provider.prompts[1])
        accepted = action["accepted_contract"]
        self.assertNotIn("schema_version", accepted)
        self.assertEqual(accepted["version"], 2)
        self.assertEqual(accepted["desired_state"]["assertions"][0]["property"], "computed_value")
        semantic = next(item for item in accepted["evals"] if item["id"] == "semantic")
        self.assertEqual(semantic["parameters"]["purpose"], "independently verify the requested result")


if __name__ == "__main__":
    unittest.main()
