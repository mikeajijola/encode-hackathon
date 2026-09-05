"""Immutable, artifact-neutral records used by the fulfilment control plane."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping


Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]


class FrozenDict(dict):
    """JSON-serializable dictionary that rejects mutation after construction."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("mapping is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _nonempty(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class Scope:
    """A generic, adapter-interpreted scope identifier."""

    resource: str

    def __post_init__(self) -> None:
        _nonempty(self.resource, "scope.resource")


@dataclass(frozen=True)
class DesiredAssertion:
    id: str
    description: str
    target_scope: tuple[Scope, ...]


class EvalStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class EvalSpec:
    id: str
    assertion_id: str
    evaluator: str
    severity: str = "required"
    parameters: Mapping[str, Json] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in {"required", "advisory"}:
            raise ValueError("eval severity must be required or advisory")
        object.__setattr__(self, "parameters", _freeze(self.parameters))


@dataclass(frozen=True)
class CompletionConditions:
    require_all_required_evals: bool = True
    require_constraints: bool = True
    require_invariants: bool = True
    require_valid_artifact: bool = True
    require_evidence: bool = True


@dataclass(frozen=True)
class EvidenceRequirements:
    event_types: tuple[str, ...] = (
        "accepted_contract",
        "observation",
        "eval_result",
        "termination_decision",
    )


@dataclass(frozen=True)
class Contract:
    id: str
    version: int
    intent: str
    assertions: tuple[DesiredAssertion, ...]
    constraints: tuple[str, ...]
    invariants: tuple[str, ...]
    evals: tuple[EvalSpec, ...]
    authorized_mutation_scopes: tuple[Scope, ...]
    completion: CompletionConditions = CompletionConditions()
    evidence: EvidenceRequirements = EvidenceRequirements()

    def __post_init__(self) -> None:
        _nonempty(self.id, "contract.id")
        _nonempty(self.intent, "contract.intent")
        if self.version < 1:
            raise ValueError("contract.version must be >= 1")
        assertion_ids = [item.id for item in self.assertions]
        eval_ids = [item.id for item in self.evals]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ValueError("assertion ids must be unique")
        if len(eval_ids) != len(set(eval_ids)):
            raise ValueError("eval ids must be unique")
        unknown = {item.assertion_id for item in self.evals} - set(assertion_ids)
        if unknown:
            raise ValueError(f"evals reference unknown assertions: {sorted(unknown)}")


@dataclass(frozen=True)
class Observation:
    id: str
    artifact_id: str
    artifact_kind: str
    artifact_hash: str
    facts: Mapping[str, Json]
    interpretations: Mapping[str, Json]
    inspected_scope: tuple[Scope, ...]
    omitted_scope: tuple[Scope, ...]
    environment: Mapping[str, Json] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", _freeze(self.facts))
        object.__setattr__(self, "interpretations", _freeze(self.interpretations))
        object.__setattr__(self, "environment", _freeze(self.environment))


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    observation_id: str
    status: EvalStatus
    message: str
    evidence_event_ids: tuple[str, ...] = ()
    details: Mapping[str, Json] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _freeze(self.details))

    @property
    def passed(self) -> bool:
        return self.status is EvalStatus.PASS


class DiscrepancyKind(StrEnum):
    STATE = "state_discrepancy"
    KNOWLEDGE = "knowledge_discrepancy"
    CONSTRAINT = "constraint_violation"
    INVARIANT = "invariant_violation"
    ARTIFACT_INVALID = "artifact_invalid"
    CAPABILITY_FAILURE = "capability_failure"
    EVALUATION_UNCERTAINTY = "evaluation_uncertainty"


class DiscrepancyStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Discrepancy:
    id: str
    kind: DiscrepancyKind
    expected: Json
    observed: Json
    failed_eval_id: str
    likely_causes: tuple[str, ...]
    confidence: float
    permissible_mutation_scope: tuple[Scope, ...]
    status: DiscrepancyStatus = DiscrepancyStatus.OPEN
    resolved_by_eval: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


def resolve_discrepancy(discrepancy: Discrepancy, evaluation: EvalResult) -> Discrepancy:
    """The sole lifecycle transition to resolved; it requires a matching passing eval."""
    if discrepancy.status is not DiscrepancyStatus.OPEN:
        raise ValueError("discrepancy is not open")
    if evaluation.eval_id != discrepancy.failed_eval_id:
        raise ValueError("evaluation does not address discrepancy")
    if not evaluation.passed:
        raise ValueError("only a passing evaluation may resolve a discrepancy")
    return replace(
        discrepancy,
        status=DiscrepancyStatus.RESOLVED,
        resolved_by_eval=evaluation.eval_id,
    )


class CapabilityEffect(StrEnum):
    OBSERVE = "observe"
    COMPUTE = "compute"
    MUTATE = "mutate"
    EXECUTE = "execute"
    VALIDATE = "validate"
    RENDER = "render"


@dataclass(frozen=True)
class CapabilityManifest:
    name: str
    version: str
    accepted_artifact_kinds: tuple[str, ...]
    input_schema: Mapping[str, Json]
    effect: CapabilityEffect
    possible_mutation_scope: tuple[Scope, ...] = ()
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    risk: str = "low"
    estimated_cost: float = 0.0
    provenance_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", _freeze(self.input_schema))


@dataclass(frozen=True)
class CapabilityRequest:
    id: str
    capability_name: str
    capability_version: str
    artifact_id: str
    artifact_kind: str
    inputs: Mapping[str, Json]
    requested_mutation_scope: tuple[Scope, ...]
    discrepancy_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", _freeze(self.inputs))


@dataclass(frozen=True)
class CapabilityResult:
    request_id: str
    succeeded: bool
    output: Mapping[str, Json]
    actual_mutation_scope: tuple[Scope, ...] = ()
    provenance: Mapping[str, Json] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", _freeze(self.output))
        object.__setattr__(self, "provenance", _freeze(self.provenance))


@dataclass(frozen=True)
class Budget:
    max_actions: int
    max_tokens: int
    max_wall_time_ms: int
    max_cost: float


@dataclass(frozen=True)
class BudgetUsage:
    actions: int = 0
    tokens: int = 0
    wall_time_ms: int = 0
    cost: float = 0.0

    def within(self, budget: Budget) -> bool:
        return (
            self.actions <= budget.max_actions
            and self.tokens <= budget.max_tokens
            and self.wall_time_ms <= budget.max_wall_time_ms
            and self.cost <= budget.max_cost
        )
