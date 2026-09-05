import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from fulfilment import (
    Broker,
    BrokerError,
    Budget,
    CapabilityEffect,
    CapabilityManifest,
    CapabilityRequest,
    CapabilityResult,
    Contract,
    DesiredAssertion,
    Discrepancy,
    DiscrepancyKind,
    DiscrepancyStatus,
    EvalResult,
    EvalSpec,
    EvalStatus,
    EvidenceIntegrityError,
    EvidenceStore,
    Observation,
    Scope,
    decide_completion,
    resolve_discrepancy,
)


def contract() -> Contract:
    return Contract(
        id="c1", version=1, intent="make the artifact correct",
        assertions=(DesiredAssertion("a1", "target property holds", (Scope("document/target"),)),),
        constraints=("preserve everything else",), invariants=("artifact remains valid",),
        evals=(EvalSpec("e1", "a1", "independent-check"),),
        authorized_mutation_scopes=(Scope("document/target"),),
    )


class RecordsTest(unittest.TestCase):
    def test_contract_is_versioned_validated_and_frozen(self):
        value = contract()
        self.assertEqual(value.version, 1)
        with self.assertRaises(FrozenInstanceError):
            value.version = 2
        with self.assertRaises(ValueError):
            Contract("bad", 0, "intent", (), (), (), (), ())

    def test_observation_separates_facts_interpretations_and_scope(self):
        observation = Observation(
            "o1", "artifact", "text", "abc", {"raw": "x"}, {"meaning": "y"},
            (Scope("document/target"),), (Scope("document/other"),),
        )
        self.assertNotEqual(observation.facts, observation.interpretations)
        self.assertTrue(observation.omitted_scope)
        with self.assertRaises(TypeError):
            observation.facts["raw"] = "changed"

    def test_evaluator_error_never_passes(self):
        result = EvalResult("e1", "o1", EvalStatus.ERROR, "crashed")
        self.assertFalse(result.passed)

    def test_only_matching_passing_eval_resolves_discrepancy(self):
        discrepancy = Discrepancy(
            "d1", DiscrepancyKind.STATE, "yes", "no", "e1", (), .9,
            (Scope("document/target"),),
        )
        for status in (EvalStatus.FAIL, EvalStatus.ERROR, EvalStatus.UNCERTAIN):
            with self.assertRaises(ValueError):
                resolve_discrepancy(discrepancy, EvalResult("e1", "o2", status, "not pass"))
        with self.assertRaises(ValueError):
            resolve_discrepancy(discrepancy, EvalResult("other", "o2", EvalStatus.PASS, "pass"))
        resolved = resolve_discrepancy(discrepancy, EvalResult("e1", "o2", EvalStatus.PASS, "pass"))
        self.assertEqual(resolved.status, DiscrepancyStatus.RESOLVED)


class EvidenceAndCompletionTest(unittest.TestCase):
    def test_append_only_order_and_hash_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = EvidenceStore(path)
            first = store.append("accepted_contract", {"id": "c1"})
            second = store.append("observation", {"id": "o1"})
            self.assertEqual((first.sequence, second.sequence), (0, 1))
            self.assertEqual(second.previous_hash, first.hash)
            self.assertEqual(len(store.verify()), 2)
            rows = path.read_text().splitlines()
            row = json.loads(rows[0]); row["payload"]["id"] = "tampered"
            rows[0] = json.dumps(row)
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaises(EvidenceIntegrityError):
                store.verify()

    def test_completion_requires_passes_validity_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EvidenceStore(Path(directory) / "events.jsonl")
            passed = [EvalResult("e1", "o1", EvalStatus.PASS, "ok")]
            decision = decide_completion(
                contract(), passed, store.records(), desired_state_satisfied=True,
                constraints_preserved=True, invariants_hold=True, artifact_valid=True,
            )
            self.assertFalse(decision.fulfilled)
            for kind in ("accepted_contract", "observation", "eval_result"):
                store.append(kind, {})
            decision = decide_completion(
                contract(), passed, store.records(), desired_state_satisfied=True,
                constraints_preserved=True, invariants_hold=True, artifact_valid=True,
            )
            self.assertTrue(decision.fulfilled)
            error = [EvalResult("e1", "o1", EvalStatus.ERROR, "boom")]
            self.assertFalse(decide_completion(
                contract(), error, store.records(), desired_state_satisfied=True,
                constraints_preserved=True, invariants_hold=True, artifact_valid=True,
            ).fulfilled)


class FakeSnapshots:
    def __init__(self): self.calls = []
    def before_mutation(self, request): self.calls.append("before"); return "hash-before"
    def after_mutation(self, request): self.calls.append("after"); return "hash-after"


class FakeHandler:
    def __init__(self, actual=(Scope("document/target"),)): self.actual = actual
    def invoke(self, request):
        return CapabilityResult(request.id, True, {"changed": True}, self.actual, {"actor": "test"})


class BrokerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.snapshots = FakeSnapshots()
        self.store = EvidenceStore(Path(self.temp.name) / "events.jsonl")
        self.broker = Broker(self.store, self.snapshots)
        self.manifest = CapabilityManifest(
            "edit", "1", ("text",),
            {"type": "object", "properties": {"value": {"type": "string"}},
             "required": ["value"], "additionalProperties": False},
            CapabilityEffect.MUTATE, (Scope("document/*"),),
        )

    def tearDown(self): self.temp.cleanup()

    def request(self, scope="document/target"):
        return CapabilityRequest("r1", "edit", "1", "artifact", "text", {"value": "new"},
                                 (Scope(scope),), ("d1",))

    def test_schema_and_mutation_scope_are_enforced_before_action(self):
        handler = FakeHandler(); self.broker.register(self.manifest, handler)
        with self.assertRaises(BrokerError):
            self.broker.invoke(contract(), self.request("document/other"))
        invalid = CapabilityRequest("r2", "edit", "1", "artifact", "text", {},
                                    (Scope("document/target"),), ("d1",))
        with self.assertRaises(BrokerError): self.broker.invoke(contract(), invalid)
        self.assertEqual(self.snapshots.calls, [])

    def test_mutation_is_snapshotted_and_traced(self):
        self.broker.register(self.manifest, FakeHandler())
        self.broker.invoke(contract(), self.request())
        self.assertEqual(self.snapshots.calls, ["before", "after"])
        events = self.store.records()
        self.assertEqual([e.event_type for e in events], ["capability_request", "capability_result"])
        self.assertEqual(events[1].payload["before_hash"], "hash-before")

    def test_actual_effect_outside_requested_scope_is_rejected(self):
        self.broker.register(self.manifest, FakeHandler((Scope("document/other"),)))
        with self.assertRaises(BrokerError): self.broker.invoke(contract(), self.request())
        self.assertEqual(self.store.records()[-1].event_type, "capability_result")
        self.assertIn("outside requested scope", self.store.records()[-1].payload["error"])

    def test_budget_is_enforced_and_usage_is_traced(self):
        broker = Broker(self.store, self.snapshots, Budget(0, 100, 1000, 1))
        broker.register(self.manifest, FakeHandler())
        with self.assertRaisesRegex(BrokerError, "budget"):
            broker.invoke(contract(), self.request())
        self.assertEqual(self.store.records(), ())

    def test_render_effect_is_represented_and_traced_without_snapshot(self):
        render = CapabilityManifest("render", "1", ("text",), {"type": "object"}, CapabilityEffect.RENDER)
        self.broker.register(render, FakeHandler(actual=()))
        request = CapabilityRequest("render-1", "render", "1", "artifact", "text", {}, (), ("d1",))
        self.broker.invoke(contract(), request)
        self.assertEqual(self.snapshots.calls, [])
        self.assertEqual(self.store.records()[0].payload["effect"], "render")

    def test_required_provenance_is_enforced(self):
        manifest = CapabilityManifest(
            "strict-edit", "1", ("text",), {"type": "object"}, CapabilityEffect.MUTATE,
            (Scope("document/*"),), provenance_requirements=("actor", "tool_version"),
        )
        self.broker.register(manifest, FakeHandler())
        request = CapabilityRequest("strict-1", "strict-edit", "1", "artifact", "text", {},
                                    (Scope("document/target"),), ("d1",))
        with self.assertRaisesRegex(BrokerError, "provenance"):
            self.broker.invoke(contract(), request)

    def test_frozen_json_array_satisfies_array_schema(self):
        manifest = CapabilityManifest(
            "inspect", "1", ("text",),
            {"type": "object", "properties": {"selectors": {"type": "array"}},
             "required": ["selectors"], "additionalProperties": False},
            CapabilityEffect.OBSERVE,
        )
        self.broker.register(manifest, FakeHandler(actual=()))
        request = CapabilityRequest(
            "inspect-1", "inspect", "1", "artifact", "text",
            {"selectors": ["document/target"]}, (), ("d1",),
        )
        self.broker.invoke(contract(), request)


if __name__ == "__main__":
    unittest.main()
