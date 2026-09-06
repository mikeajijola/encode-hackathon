"""Artifact-neutral contract compilation, evaluation and reconciliation control flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol, Sequence
from uuid import uuid4

from .broker import Broker, BrokerError
from .completion import CompletionStatus, decide_completion
from .evidence import EvidenceStore
from .models import (
    CapabilityManifest,
    CapabilityRequest,
    Contract,
    Discrepancy,
    DiscrepancyKind,
    EvalResult,
    EvalSpec,
    EvalStatus,
    Observation,
    Scope,
    resolve_discrepancy,
)


class ContractAmbiguous(ValueError):
    pass


class ContractCompiler(Protocol):
    def compile(
        self, intent: str, context: Observation, capabilities: Sequence[CapabilityManifest]
    ) -> Contract: ...


class Observer(Protocol):
    def observe(self, scopes: tuple[Scope, ...]) -> Observation: ...


class Evaluator(Protocol):
    def evaluate(self, spec: EvalSpec, observation: Observation, contract: Contract) -> EvalResult: ...


class TransitionKind(StrEnum):
    OBSERVE = "observe"
    CAPABILITY = "capability"


@dataclass(frozen=True)
class Transition:
    id: str
    kind: TransitionKind
    discrepancy_ids: tuple[str, ...]
    rationale: str
    observation_scopes: tuple[Scope, ...] = ()
    capability_request: CapabilityRequest | None = None

    def signature(self) -> tuple[object, ...]:
        request = self.capability_request
        return (
            self.kind, self.observation_scopes,
            request.capability_name if request else None,
            request.capability_version if request else None,
            repr(sorted(request.inputs.items())) if request else None,
            request.requested_mutation_scope if request else None,
        )


class Planner(Protocol):
    def plan(
        self,
        contract: Contract,
        observation: Observation,
        discrepancies: tuple[Discrepancy, ...],
        capabilities: Sequence[CapabilityManifest],
    ) -> Transition | None: ...


class ArtifactLifecycle(Protocol):
    def rollback(self, reason: str) -> None: ...
    def select_result(self, observation: Observation, status: str) -> Mapping[str, object]: ...


class UnfulfilledReason(StrEnum):
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_SAFE_TRANSITION = "no_safe_transition"
    CONTRACT_AMBIGUOUS = "contract_ambiguous"
    CAPABILITY_MISSING = "capability_missing"
    ARTIFACT_INVALID = "artifact_invalid"
    EVALUATION_UNCERTAIN = "evaluation_uncertain"
    NO_PROGRESS = "no_progress"
    OPERATIONAL_EMERGENCY_CEILING = "operational_emergency_ceiling"


@dataclass(frozen=True)
class FulfilmentResult:
    fulfilled: bool
    reason: str
    contract_id: str | None
    iterations: int
    observation_id: str
    artifact: Mapping[str, object]
    open_discrepancies: tuple[Discrepancy, ...]
    completion_status: CompletionStatus = CompletionStatus.UNFULFILLED


class ContractValidator:
    """Structural validation which keeps contracts state-based and evaluable."""

    PROCEDURAL_WORDS = ("first ", "then ", "next ", "step ", "click ", "open ")

    def validate(self, contract: Contract) -> None:
        if not contract.assertions:
            raise ContractAmbiguous("contract has no desired-state assertions")
        required_assertions = {spec.assertion_id for spec in contract.evals if spec.severity == "required"}
        missing = {assertion.id for assertion in contract.assertions} - required_assertions
        if missing:
            raise ContractAmbiguous(f"assertions lack required evals: {sorted(missing)}")
        for assertion in contract.assertions:
            lowered = assertion.description.lower().strip()
            if any(lowered.startswith(word) for word in self.PROCEDURAL_WORDS):
                raise ContractAmbiguous(f"assertion {assertion.id!r} appears procedural")


class DeterministicContractCompiler:
    """Fixture compiler useful for controlled tests without a model dependency."""

    def __init__(self, contracts_by_intent: Mapping[str, Contract]):
        self.contracts_by_intent = dict(contracts_by_intent)

    def compile(self, intent, context, capabilities):
        try:
            return self.contracts_by_intent[intent]
        except KeyError as error:
            raise ContractAmbiguous("intent has no unambiguous fixture contract") from error


class EvaluatorRegistry:
    def __init__(self, evidence: EvidenceStore):
        self.evidence = evidence
        self._evaluators: dict[str, Evaluator] = {}

    def register(self, name: str, evaluator: Evaluator) -> None:
        if name in self._evaluators:
            raise ValueError(f"evaluator already registered: {name}")
        self._evaluators[name] = evaluator

    def run(self, contract: Contract, observation: Observation) -> tuple[EvalResult, ...]:
        results = []
        for spec in contract.evals:
            evaluator = self._evaluators.get(spec.evaluator)
            if evaluator is None:
                result = EvalResult(spec.id, observation.id, EvalStatus.ERROR, "evaluator unavailable")
            else:
                try:
                    result = evaluator.evaluate(spec, observation, contract)
                    if result.eval_id != spec.id or result.observation_id != observation.id:
                        raise ValueError("evaluator returned mismatched ids")
                except Exception as error:
                    result = EvalResult(
                        spec.id, observation.id, EvalStatus.ERROR,
                        f"{type(error).__name__}: {error}",
                    )
            event = self.evidence.append("eval_result", {
                "eval_id": result.eval_id, "observation_id": result.observation_id,
                "status": result.status.value, "message": result.message,
                "details": result.details,
            })
            results.append(EvalResult(
                result.eval_id, result.observation_id, result.status, result.message,
                result.evidence_event_ids + (event.id,), result.details,
            ))
        return tuple(results)


def derive_discrepancies(
    contract: Contract,
    results: Sequence[EvalResult],
    previous: Sequence[Discrepancy] = (),
) -> tuple[Discrepancy, ...]:
    """Resolve old discrepancies only through evals; derive typed new discrepancies."""
    by_eval = {result.eval_id: result for result in results}
    open_items: list[Discrepancy] = []
    for item in previous:
        result = by_eval.get(item.failed_eval_id)
        if result and result.passed:
            resolve_discrepancy(item, result)
        elif result is None:
            open_items.append(item)
        # A new non-pass evaluation supersedes (without resolving) the prior
        # discrepancy below. This permits knowledge -> state reclassification.
    existing = {item.failed_eval_id for item in open_items}
    specs = {spec.id: spec for spec in contract.evals}
    kind_names = {kind.value: kind for kind in DiscrepancyKind}
    for result in results:
        if result.passed or result.eval_id in existing:
            continue
        if result.status in (EvalStatus.ERROR, EvalStatus.UNCERTAIN):
            kind = DiscrepancyKind.EVALUATION_UNCERTAINTY
        elif result.details.get("knowledge_gap"):
            kind = DiscrepancyKind.KNOWLEDGE
        else:
            kind = kind_names.get(str(result.details.get("kind")), DiscrepancyKind.STATE)
        spec = specs[result.eval_id]
        assertion = next(a for a in contract.assertions if a.id == spec.assertion_id)
        open_items.append(Discrepancy(
            id=f"d-{uuid4()}", kind=kind,
            expected=result.details.get("expected", assertion.description),
            observed=result.details.get("observed"), failed_eval_id=result.eval_id,
            likely_causes=tuple(result.details.get("likely_causes", ())),
            confidence=float(result.details.get("confidence", 1.0)),
            permissible_mutation_scope=assertion.target_scope,
        ))
    return tuple(open_items)


class FulfilmentAgent:
    def __init__(
        self, compiler: ContractCompiler, validator: ContractValidator, observer: Observer,
        evaluators: EvaluatorRegistry, planner: Planner, broker: Broker,
        evidence: EvidenceStore, lifecycle: ArtifactLifecycle, *, max_iterations: int = 8,
        max_repeated_transition: int = 1,
    ):
        self.compiler, self.validator, self.observer = compiler, validator, observer
        self.evaluators, self.planner, self.broker = evaluators, planner, broker
        self.evidence, self.lifecycle = evidence, lifecycle
        self.max_iterations, self.max_repeated_transition = max_iterations, max_repeated_transition

    def _finish(self, fulfilled, reason, contract, iteration, observation, discrepancies,
                completion_status=None):
        if completion_status is None:
            epistemic = reason in {
                UnfulfilledReason.CONTRACT_AMBIGUOUS.value,
                UnfulfilledReason.CAPABILITY_MISSING.value,
                UnfulfilledReason.EVALUATION_UNCERTAIN.value,
            } or any(item.kind in {DiscrepancyKind.KNOWLEDGE,
                                   DiscrepancyKind.EVALUATION_UNCERTAINTY}
                     for item in discrepancies)
            completion_status = (CompletionStatus.FULFILLED if fulfilled else
                                 CompletionStatus.UNKNOWN if epistemic else
                                 CompletionStatus.UNFULFILLED)
        artifact = self.lifecycle.select_result(observation, completion_status.value.lower())
        self.evidence.append("termination_decision", {
            "fulfilled": fulfilled, "reason": reason, "contract_id": contract.id if contract else None,
            "completion_status": completion_status.value,
            "observation_id": observation.id, "open_discrepancy_ids": [d.id for d in discrepancies],
            "artifact": artifact,
        })
        return FulfilmentResult(fulfilled, reason, contract.id if contract else None,
                                iteration, observation.id, artifact, tuple(discrepancies),
                                completion_status)

    def run(self, intent: str, initial_observation: Observation) -> FulfilmentResult:
        observation = initial_observation
        try:
            contract = self.compiler.compile(intent, observation, self.broker.manifests())
            self.validator.validate(contract)
        except (ContractAmbiguous, ValueError):
            return self._finish(False, UnfulfilledReason.CONTRACT_AMBIGUOUS.value, None, 0,
                                observation, ())
        self.evidence.append("accepted_contract", {
            "contract_id": contract.id, "version": contract.version, "intent": contract.intent,
        })
        discrepancies: tuple[Discrepancy, ...] = ()
        repeated: dict[tuple[object, ...], int] = {}
        pending_cycle: dict[str, object] | None = None
        for iteration in range(1, self.max_iterations + 1):
            observed_event = self.evidence.append("observation", {
                "observation_id": observation.id, "artifact_hash": observation.artifact_hash,
                "inspected_scope": [s.resource for s in observation.inspected_scope],
                "omitted_scope": [s.resource for s in observation.omitted_scope],
            })
            results = self.evaluators.run(contract, observation)
            discrepancies = derive_discrepancies(contract, results, discrepancies)
            failed_eval_ids = [result.eval_id for result in results if not result.passed]
            for discrepancy in discrepancies:
                self.evidence.append("discrepancy", {
                    "discrepancy_id": discrepancy.id, "kind": discrepancy.kind.value,
                    "failed_eval_id": discrepancy.failed_eval_id,
                    "observation_event_id": observed_event.id,
                    "permissible_mutation_scope": [s.resource for s in discrepancy.permissible_mutation_scope],
                })
            if pending_cycle is not None:
                changed = pending_cycle["artifact_hash_before"] != observation.artifact_hash
                self.evidence.append("reconciliation_cycle", {
                    **pending_cycle,
                    "cycle_number": pending_cycle["cycle_number"],
                    "artifact_hash_after": observation.artifact_hash,
                    "failed_evals_after": failed_eval_ids,
                    "discrepancy_ids_after": [item.id for item in discrepancies],
                    "changed_state": changed,
                    "genuine_cycle": bool(changed),
                })
                pending_cycle = None
            kinds = {item.kind for item in discrepancies}
            completion = decide_completion(
                contract, results, self.evidence.records(),
                desired_state_satisfied=not discrepancies,
                constraints_preserved=DiscrepancyKind.CONSTRAINT not in kinds,
                invariants_hold=DiscrepancyKind.INVARIANT not in kinds,
                artifact_valid=DiscrepancyKind.ARTIFACT_INVALID not in kinds,
            )
            if completion.fulfilled:
                return self._finish(True, "fulfilled", contract, iteration, observation, (),
                                    completion.status)
            if completion.status is CompletionStatus.UNKNOWN and not discrepancies:
                return self._finish(False, UnfulfilledReason.EVALUATION_UNCERTAIN.value,
                                    contract, iteration, observation, (), completion.status)
            if DiscrepancyKind.ARTIFACT_INVALID in kinds:
                return self._finish(False, UnfulfilledReason.ARTIFACT_INVALID.value, contract,
                                    iteration, observation, discrepancies)
            transition = self.planner.plan(contract, observation, discrepancies, self.broker.manifests())
            if transition is None:
                reason = (UnfulfilledReason.EVALUATION_UNCERTAIN.value
                          if kinds == {DiscrepancyKind.EVALUATION_UNCERTAINTY}
                          else UnfulfilledReason.NO_SAFE_TRANSITION.value)
                return self._finish(False, reason, contract, iteration, observation, discrepancies,
                                    completion.status)
            current_ids = {item.id for item in discrepancies}
            if not transition.discrepancy_ids or not set(transition.discrepancy_ids) <= current_ids:
                return self._finish(False, UnfulfilledReason.NO_SAFE_TRANSITION.value, contract,
                                    iteration, observation, discrepancies)
            if DiscrepancyKind.KNOWLEDGE in kinds and transition.kind is not TransitionKind.OBSERVE:
                return self._finish(False, UnfulfilledReason.NO_SAFE_TRANSITION.value, contract,
                                    iteration, observation, discrepancies)
            signature = transition.signature()
            repeated[signature] = repeated.get(signature, 0) + 1
            if repeated[signature] > self.max_repeated_transition:
                return self._finish(False, UnfulfilledReason.NO_PROGRESS.value, contract,
                                    iteration, observation, discrepancies, completion.status)
            self.evidence.append("transition_decision", {
                "transition_id": transition.id, "kind": transition.kind.value,
                "discrepancy_ids": transition.discrepancy_ids, "rationale": transition.rationale,
            })
            if transition.kind is TransitionKind.OBSERVE:
                observation = self.observer.observe(transition.observation_scopes)
                continue
            request = transition.capability_request
            if request is None:
                return self._finish(False, UnfulfilledReason.NO_SAFE_TRANSITION.value, contract,
                                    iteration, observation, discrepancies)
            if set(request.discrepancy_ids) != set(transition.discrepancy_ids):
                return self._finish(False, UnfulfilledReason.NO_SAFE_TRANSITION.value, contract,
                                    iteration, observation, discrepancies)
            try:
                result = self.broker.invoke(contract, request)
            except BrokerError as error:
                reason = (UnfulfilledReason.BUDGET_EXHAUSTED.value if "budget" in str(error)
                          else UnfulfilledReason.CAPABILITY_MISSING.value if "unknown capability" in str(error)
                          else UnfulfilledReason.NO_SAFE_TRANSITION.value)
                self.lifecycle.rollback(str(error))
                return self._finish(False, reason, contract, iteration, observation, discrepancies)
            if not result.succeeded:
                self.lifecycle.rollback(result.error or "capability failed")
            if result.succeeded and result.actual_mutation_scope:
                pending_cycle = {
                    "cycle_number": iteration,
                    "transition_id": transition.id,
                    "capability": request.capability_name,
                    "artifact_hash_before": observation.artifact_hash,
                    "failed_evals_before": failed_eval_ids,
                    "discrepancy_ids_before": [item.id for item in discrepancies],
                }
            observation = self.observer.observe(())
        return self._finish(False, UnfulfilledReason.OPERATIONAL_EMERGENCY_CEILING.value, contract,
                            self.max_iterations, observation, discrepancies)
