import tempfile
import unittest
from pathlib import Path

from fulfilment import (
    Broker, Budget, CapabilityEffect, CapabilityManifest, CapabilityRequest, CapabilityResult,
    Contract, ContractValidator, DesiredAssertion, DeterministicContractCompiler,
    DiscrepancyKind, EvalResult, EvalSpec, EvalStatus, EvaluatorRegistry, EvidenceStore,
    FulfilmentAgent, Observation, Scope, Transition, TransitionKind,
)


TARGET = Scope("artifact/target")


def fixture_contract(description="target equals two"):
    return Contract(
        "contract-1", 1, "reach two",
        (DesiredAssertion("target", description, (TARGET,)),),
        ("preserve other state",), ("artifact remains valid",),
        (EvalSpec("target-eval", "target", "target-value"),), (TARGET,),
    )


class StateFixture:
    """Tiny second-domain-like fixture: generic integer state, not an artifact adapter."""
    def __init__(self, value=0, visible=True):
        self.value, self.visible, self.observations = value, visible, 0
        self.rollbacks = []

    def observe(self, scopes=()):
        if scopes: self.visible = True
        self.observations += 1
        return Observation(
            f"obs-{self.observations}", "fixture", "counter", str(self.value),
            {"target": self.value} if self.visible else {}, {},
            (TARGET,) if self.visible else (), () if self.visible else (TARGET,),
        )

    def before_mutation(self, request): return f"before-{self.value}"
    def after_mutation(self, request): return f"after-{self.value}"
    def rollback(self, reason): self.rollbacks.append(reason)
    def select_result(self, observation, status):
        return {"artifact_id": observation.artifact_id, "hash": observation.artifact_hash, "status": status}
    def invoke(self, request):
        self.value = request.inputs["value"]
        return CapabilityResult(request.id, True, {"value": self.value}, (TARGET,), {"actor": "fixture"})


class ValueEvaluator:
    def evaluate(self, spec, observation, contract):
        if "target" not in observation.facts:
            return EvalResult(spec.id, observation.id, EvalStatus.FAIL, "target unobserved",
                              details={"knowledge_gap": True, "expected": 2})
        value = observation.facts["target"]
        return EvalResult(spec.id, observation.id,
                          EvalStatus.PASS if value == 2 else EvalStatus.FAIL,
                          "equal" if value == 2 else "not equal",
                          details={"expected": 2, "observed": value})


class IncrementPlanner:
    def plan(self, contract, observation, discrepancies, capabilities):
        ids = tuple(item.id for item in discrepancies)
        if any(item.kind is DiscrepancyKind.KNOWLEDGE for item in discrepancies):
            return Transition("inspect", TransitionKind.OBSERVE, ids, "close knowledge gap", (TARGET,))
        value = observation.facts.get("target", 0)
        request = CapabilityRequest(f"set-{value + 1}", "set", "1", "fixture", "counter",
                                    {"value": value + 1}, (TARGET,), ids)
        return Transition(f"increment-{value}", TransitionKind.CAPABILITY, ids,
                          "smallest transition toward target", capability_request=request)


class NonePlanner:
    def plan(self, *args): return None


class RepeatedObservePlanner:
    def plan(self, contract, observation, discrepancies, capabilities):
        return Transition("same", TransitionKind.OBSERVE, tuple(d.id for d in discrepancies),
                          "repeat", (TARGET,))


class UnknownCapabilityPlanner:
    def plan(self, contract, observation, discrepancies, capabilities):
        request = CapabilityRequest("missing", "absent", "1", "fixture", "counter", {}, (TARGET,),
                                    tuple(d.id for d in discrepancies))
        return Transition("missing", TransitionKind.CAPABILITY, request.discrepancy_ids, "try missing",
                          capability_request=request)


class ErrorEvaluator:
    def evaluate(self, spec, observation, contract): raise RuntimeError("evaluation broke")


class InvalidEvaluator:
    def evaluate(self, spec, observation, contract):
        return EvalResult(spec.id, observation.id, EvalStatus.FAIL, "invalid",
                          details={"kind": "artifact_invalid"})


class ControlLoopTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.evidence = EvidenceStore(Path(self.temp.name) / "evidence.jsonl")

    def tearDown(self): self.temp.cleanup()

    def build(self, state, planner, evaluator=None, *, budget=None, contract=None, register=True):
        broker = Broker(self.evidence, state, budget)
        if register:
            broker.register(CapabilityManifest(
                "set", "1", ("counter",),
                {"type": "object", "properties": {"value": {"type": "integer"}},
                 "required": ["value"], "additionalProperties": False},
                CapabilityEffect.MUTATE, (TARGET,), provenance_requirements=("actor",),
            ), state)
        registry = EvaluatorRegistry(self.evidence)
        registry.register("target-value", evaluator or ValueEvaluator())
        chosen = contract or fixture_contract()
        return FulfilmentAgent(
            DeterministicContractCompiler({"reach two": chosen}), ContractValidator(), state,
            registry, planner, broker, self.evidence, state, max_iterations=6,
        )

    def test_multistep_reconciliation_converges_with_causal_trace(self):
        state = StateFixture(0, visible=False)
        result = self.build(state, IncrementPlanner()).run("reach two", state.observe())
        self.assertTrue(result.fulfilled)
        self.assertEqual(state.value, 2)
        self.assertGreaterEqual(result.iterations, 4)  # inspect, set 1, set 2, verify
        events = self.evidence.records()
        kinds = [event.event_type for event in events]
        for required in ("accepted_contract", "observation", "eval_result", "discrepancy",
                         "transition_decision", "capability_request", "capability_result",
                         "termination_decision"):
            self.assertIn(required, kinds)
        request = next(event for event in events if event.event_type == "capability_request")
        transition = [event for event in events if event.event_type == "transition_decision" and
                      event.payload["kind"] == "capability"][0]
        self.assertEqual(request.payload["discrepancy_ids"], transition.payload["discrepancy_ids"])
        self.assertEqual(events[-1].payload["fulfilled"], True)

    def test_impossible_state_refuses_no_safe_transition(self):
        state = StateFixture()
        result = self.build(state, NonePlanner()).run("reach two", state.observe())
        self.assertEqual(result.reason, "no_safe_transition")
        self.assertFalse(result.fulfilled)

    def test_ambiguous_and_procedural_contracts_refuse(self):
        state = StateFixture()
        missing = self.build(state, NonePlanner()).run("unknown intent", state.observe())
        self.assertEqual(missing.reason, "contract_ambiguous")
        procedural = fixture_contract("First click the target")
        result = self.build(state, NonePlanner(), contract=procedural).run("reach two", state.observe())
        self.assertEqual(result.reason, "contract_ambiguous")
        uncovered = Contract("c", 1, "reach two", (DesiredAssertion("a", "state holds", (TARGET,)),),
                             (), (), (), (TARGET,))
        result = self.build(state, NonePlanner(), contract=uncovered).run("reach two", state.observe())
        self.assertEqual(result.reason, "contract_ambiguous")

    def test_knowledge_gap_cannot_authorize_mutation(self):
        state = StateFixture(0, visible=False)
        # This planner ignores the knowledge type and attempts a mutation.
        class UnsafePlanner:
            def plan(inner_self, contract, observation, discrepancies, capabilities):
                ids = tuple(d.id for d in discrepancies)
                request = CapabilityRequest("unsafe", "set", "1", "fixture", "counter",
                                            {"value": 2}, (TARGET,), ids)
                return Transition("unsafe", TransitionKind.CAPABILITY, ids, "guess",
                                  capability_request=request)
        result = self.build(state, UnsafePlanner()).run("reach two", state.observe())
        self.assertEqual(result.reason, "no_safe_transition")
        self.assertEqual(state.value, 0)

    def test_missing_capability_and_budget_paths_are_typed(self):
        state = StateFixture()
        missing = self.build(state, UnknownCapabilityPlanner(), register=False).run("reach two", state.observe())
        self.assertEqual(missing.reason, "capability_missing")

        # A fresh evidence store avoids mixing independent experimental runs.
        self.evidence = EvidenceStore(Path(self.temp.name) / "budget.jsonl")
        state = StateFixture()
        exhausted = self.build(state, IncrementPlanner(), budget=Budget(0, 100, 1000, 1)).run(
            "reach two", state.observe())
        self.assertEqual(exhausted.reason, "budget_exhausted")

    def test_repeated_transition_is_no_progress(self):
        state = StateFixture(0)
        result = self.build(state, RepeatedObservePlanner()).run("reach two", state.observe())
        self.assertEqual(result.reason, "no_progress")
        decisions = [e for e in self.evidence.records() if e.event_type == "transition_decision"]
        self.assertEqual(len(decisions), 1)  # repetition is rejected before execution

    def test_evaluator_error_is_uncertain_and_never_fulfilled(self):
        state = StateFixture(2)
        result = self.build(state, NonePlanner(), ErrorEvaluator()).run("reach two", state.observe())
        self.assertEqual(result.reason, "evaluation_uncertain")
        eval_event = next(e for e in self.evidence.records() if e.event_type == "eval_result")
        self.assertEqual(eval_event.payload["status"], "error")

    def test_invalid_artifact_stops_without_mutation(self):
        state = StateFixture()
        result = self.build(state, IncrementPlanner(), InvalidEvaluator()).run("reach two", state.observe())
        self.assertEqual(result.reason, "artifact_invalid")
        self.assertFalse(any(e.event_type == "capability_request" for e in self.evidence.records()))


if __name__ == "__main__":
    unittest.main()
