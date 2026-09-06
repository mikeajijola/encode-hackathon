"""Evidence-based completion gate."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .evidence import EvidenceEvent
from .models import Contract, EvalResult, EvalStatus


class CompletionStatus(StrEnum):
    FULFILLED = "FULFILLED"
    UNFULFILLED = "UNFULFILLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CompletionDecision:
    fulfilled: bool
    reason: str
    failed_conditions: tuple[str, ...]
    status: CompletionStatus


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
    missing = required - set(latest)
    uncertain = {eval_id for eval_id in required if eval_id in latest and
                 latest[eval_id].status in {EvalStatus.ERROR, EvalStatus.UNCERTAIN}}
    inadequate = {eval_id for eval_id in required if eval_id in latest and
                  latest[eval_id].details.get("completion_evidence_adequate") is False}
    failures = []
    unknowns = []
    if not desired_state_satisfied:
        (unknowns if missing or uncertain or inadequate else failures).append(
            "desired_state_unestablished" if missing or uncertain or inadequate else "desired_state_unsatisfied")
    if missing:
        unknowns.append("required_evals_missing")
    if uncertain:
        unknowns.append("required_evals_uncertain")
    if inadequate:
        unknowns.append("required_eval_evidence_inadequate")
    if contract.completion.require_all_required_evals and any(
        eval_id in latest and latest[eval_id].status is EvalStatus.FAIL and eval_id not in inadequate
        for eval_id in required
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
        unknowns.append("required_evidence_missing")
    if failures:
        status = CompletionStatus.UNFULFILLED
    elif unknowns:
        status = CompletionStatus.UNKNOWN
    else:
        status = CompletionStatus.FULFILLED
    conditions = tuple((*failures, *unknowns))
    return CompletionDecision(status is CompletionStatus.FULFILLED, status.value.lower(),
                              conditions, status)
