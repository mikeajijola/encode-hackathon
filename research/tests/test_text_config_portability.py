import tempfile
import unittest
from pathlib import Path

from adapters.text_config import (
    DesiredSelectorValueEvaluator, DirectoryWorkspace, EditTextCapability,
    InspectTextCapability, TextArtifactValidityEvaluator, ValidateTextCapability,
)
from fulfilment import (
    Broker, BrokerError, CapabilityRequest, Contract, ContractValidator,
    DesiredAssertion, DeterministicContractCompiler, EvalSpec, EvaluatorRegistry,
    EvidenceStore, FulfilmentAgent, Scope, Transition, TransitionKind,
)


CONFIG_ENABLED = Scope("file/config.json#/enabled")
STATUS_TEXT = Scope("file/status.txt")


def desired_contract():
    return Contract(
        "portable-text-v1", 1, "enable config and mark ready",
        (
            DesiredAssertion("enabled", "configuration is enabled", (CONFIG_ENABLED,)),
            DesiredAssertion("status", "status text is ready", (STATUS_TEXT,)),
            DesiredAssertion("valid", "text and configuration remain valid", (CONFIG_ENABLED, STATUS_TEXT)),
        ),
        ("only selected files may change",), ("all selected content remains valid",),
        (
            EvalSpec("enabled-eval", "enabled", "selector-value", parameters={"selector": CONFIG_ENABLED.resource, "expected": True}),
            EvalSpec("status-eval", "status", "selector-value", parameters={"selector": STATUS_TEXT.resource, "expected": "ready\n"}),
            EvalSpec("valid-eval", "valid", "text-validity", parameters={"selectors": [CONFIG_ENABLED.resource, STATUS_TEXT.resource]}),
        ),
        (CONFIG_ENABLED, STATUS_TEXT),
    )


class TextPlanner:
    VALUES = {"enabled-eval": True, "status-eval": "ready\n"}
    SELECTORS = {"enabled-eval": CONFIG_ENABLED, "status-eval": STATUS_TEXT}

    def plan(self, contract, observation, discrepancies, capabilities):
        actionable = next((item for item in discrepancies if item.failed_eval_id in self.VALUES), None)
        if actionable is None: return None
        scope = self.SELECTORS[actionable.failed_eval_id]
        request = CapabilityRequest(
            f"edit-{actionable.failed_eval_id}", "edit_text", "1", observation.artifact_id,
            "directory", {"selector": scope.resource, "value": self.VALUES[actionable.failed_eval_id]},
            (scope,), (actionable.id,),
        )
        return Transition(f"transition-{actionable.id}", TransitionKind.CAPABILITY, (actionable.id,),
                          "apply one bounded desired-state delta", capability_request=request)


class PortabilityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "artifact"; self.root.mkdir()
        (self.root / "config.json").write_text('{"enabled": false}\n')
        (self.root / "status.txt").write_text("pending\n")
        self.store = EvidenceStore(Path(self.temp.name) / "evidence.jsonl")
        self.workspace = DirectoryWorkspace(self.root, (CONFIG_ENABLED, STATUS_TEXT))

    def tearDown(self): self.temp.cleanup()

    def agent(self):
        broker = Broker(self.store, self.workspace)
        for capability in (InspectTextCapability(self.workspace), EditTextCapability(self.workspace),
                           ValidateTextCapability(self.workspace)):
            broker.register(capability.manifest, capability)
        evaluators = EvaluatorRegistry(self.store)
        evaluators.register("selector-value", DesiredSelectorValueEvaluator())
        evaluators.register("text-validity", TextArtifactValidityEvaluator())
        contract = desired_contract()
        return FulfilmentAgent(
            DeterministicContractCompiler({contract.intent: contract}), ContractValidator(), self.workspace,
            evaluators, TextPlanner(), broker, self.store, self.workspace, max_iterations=5,
        )

    def test_generic_loop_reconciles_two_text_config_transitions(self):
        result = self.agent().run(desired_contract().intent, self.workspace.observe())
        self.assertTrue(result.fulfilled)
        self.assertTrue(__import__("json").loads((self.root / "config.json").read_text())["enabled"])
        self.assertEqual((self.root / "status.txt").read_text(), "ready\n")
        self.assertEqual(result.iterations, 3)

        events = self.store.verify()
        self.assertEqual(events[-1].event_type, "termination_decision")
        self.assertTrue(events[-1].payload["fulfilled"])
        self.assertEqual(events[-1].payload["artifact"]["artifact_hash"], result.artifact["artifact_hash"])
        requests = [event for event in events if event.event_type == "capability_request"]
        decisions = [event for event in events if event.event_type == "transition_decision"]
        self.assertEqual(len(requests), 2)
        self.assertEqual([r.payload["discrepancy_ids"] for r in requests],
                         [d.payload["discrepancy_ids"] for d in decisions])

    def test_out_of_scope_edit_is_rejected_before_file_access(self):
        broker = Broker(self.store, self.workspace)
        capability = EditTextCapability(self.workspace); broker.register(capability.manifest, capability)
        request = CapabilityRequest("bad", "edit_text", "1", str(self.root), "directory",
                                    {"selector": "file/secret.txt", "value": "bad"},
                                    (Scope("file/secret.txt"),), ("d1",))
        with self.assertRaisesRegex(BrokerError, "contract authorization"):
            broker.invoke(desired_contract(), request)
        self.assertFalse((self.root / "secret.txt").exists())

    def test_inspect_is_bounded_and_validation_checks_utf8_and_json(self):
        broker = Broker(self.store, self.workspace)
        inspect = InspectTextCapability(self.workspace)
        validate = ValidateTextCapability(self.workspace)
        broker.register(inspect.manifest, inspect); broker.register(validate.manifest, validate)
        inspected = broker.invoke(desired_contract(), CapabilityRequest(
            "inspect", "inspect_text", "1", str(self.root), "directory",
            {"selector": CONFIG_ENABLED.resource}, (), ("knowledge-d1",),
        ))
        self.assertEqual(inspected.output["facts"][CONFIG_ENABLED.resource], False)
        (self.root / "config.json").write_bytes(b"\xff")
        checked = broker.invoke(desired_contract(), CapabilityRequest(
            "validate", "validate_text", "1", str(self.root), "directory", {}, (), ("validity-d1",),
        ))
        self.assertFalse(checked.succeeded)
        self.assertFalse(checked.output["validity"][CONFIG_ENABLED.resource])

    def test_invalid_json_refuses_without_mutation(self):
        (self.root / "config.json").write_text("{broken", encoding="utf-8")
        before = (self.root / "status.txt").read_bytes()
        result = self.agent().run(desired_contract().intent, self.workspace.observe())
        self.assertFalse(result.fulfilled)
        self.assertEqual(result.reason, "artifact_invalid")
        self.assertEqual((self.root / "status.txt").read_bytes(), before)
        self.assertFalse(any(event.event_type == "capability_request" for event in self.store.records()))


if __name__ == "__main__":
    unittest.main()
