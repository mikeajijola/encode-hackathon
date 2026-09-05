"""Artifact-neutral primitives for declarative fulfilment."""

from .broker import Broker, BrokerError, CapabilityHandler, SnapshotHooks
from .completion import CompletionDecision, decide_completion
from .control import (
    ArtifactLifecycle,
    ContractAmbiguous,
    ContractCompiler,
    ContractValidator,
    DeterministicContractCompiler,
    Evaluator,
    EvaluatorRegistry,
    FulfilmentAgent,
    FulfilmentResult,
    Observer,
    Planner,
    Transition,
    TransitionKind,
    UnfulfilledReason,
    derive_discrepancies,
)
from .evidence import EvidenceEvent, EvidenceStore, EvidenceIntegrityError
from .models import (
    Budget,
    BudgetUsage,
    CapabilityEffect,
    CapabilityManifest,
    CapabilityRequest,
    CapabilityResult,
    CompletionConditions,
    Contract,
    DesiredAssertion,
    Discrepancy,
    DiscrepancyKind,
    DiscrepancyStatus,
    EvalResult,
    EvalSpec,
    EvalStatus,
    EvidenceRequirements,
    Observation,
    Scope,
    resolve_discrepancy,
)

__all__ = [name for name in globals() if not name.startswith("_")]
