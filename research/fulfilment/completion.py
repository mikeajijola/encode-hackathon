"""Evidence-based completion gate."""

from dataclasses import dataclass
from typing import Iterable

from .evidence import EvidenceEvent
from .models import Contract, EvalResult, EvalStatus


@dataclass(frozen=True)
class CompletionDecision:
    fulfilled: bool
    reason: str
    failed_conditions: tuple[str, ...]


def decide_completion(
    contract: Contract,
    eval_results: Iterable[EvalResult],
    evidence: Iterable[EvidenceEvent],
    *,
    desired_state_satisfied: bool,
    constraints_preserved: bool,
    invariants_hold: bool,
    artifact_valid: bool,
) -> CompletionDecision:
    latest = {result.eval_id: result for result in eval_results}
    required = {spec.id for spec in contract.evals if spec.severity == "required"}
    failures = []
    if not desired_state_satisfied:
        failures.append("desired_state_unsatisfied")
    if contract.completion.require_all_required_evals and any(
        eval_id not in latest or latest[eval_id].status is not EvalStatus.PASS for eval_id in required
    ):
        failures.append("required_evals_not_passed")
    if contract.completion.require_constraints and not constraints_preserved:
        failures.append("constraints_not_preserved")
    if contract.completion.require_invariants and not invariants_hold:
        failures.append("invariants_not_held")
    if contract.completion.require_valid_artifact and not artifact_valid:
        failures.append("artifact_invalid")
    present = {event.event_type for event in evidence}
    # termination_decision is produced after this prospective decision.
    prereqs = set(contract.evidence.event_types) - {"termination_decision"}
    if contract.completion.require_evidence and not prereqs <= present:
        failures.append("required_evidence_missing")
    return CompletionDecision(not failures, "fulfilled" if not failures else "unfulfilled", tuple(failures))
