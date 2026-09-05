"""Capability registration, authorization, validation and traced invocation."""

from __future__ import annotations

from dataclasses import replace
from time import monotonic
from typing import Any, Mapping, Protocol

from .evidence import EvidenceStore
from .models import Budget, BudgetUsage, CapabilityEffect, CapabilityManifest, CapabilityRequest, CapabilityResult, Contract, Scope


class BrokerError(RuntimeError):
    pass


class CapabilityHandler(Protocol):
    def invoke(self, request: CapabilityRequest) -> CapabilityResult: ...


class SnapshotHooks(Protocol):
    def before_mutation(self, request: CapabilityRequest) -> str: ...
    def after_mutation(self, request: CapabilityRequest) -> str: ...


def _covers(parent: Scope, child: Scope) -> bool:
    prefix = parent.resource[:-2] if parent.resource.endswith("/*") else parent.resource
    return child.resource == prefix or (parent.resource.endswith("/*") and child.resource.startswith(prefix + "/"))


def _authorized(scopes: tuple[Scope, ...], allowed: tuple[Scope, ...]) -> bool:
    return all(any(_covers(parent, child) for parent in allowed) for child in scopes)


def _validate_json_schema(inputs: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if schema.get("type") not in (None, "object"):
        raise BrokerError("capability input schema root must be object")
    required = schema.get("required", [])
    missing = set(required) - set(inputs)
    if missing:
        raise BrokerError(f"missing required inputs: {sorted(missing)}")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extras = set(inputs) - set(properties)
        if extras:
            raise BrokerError(f"unexpected inputs: {sorted(extras)}")
    types = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
    for name, value in inputs.items():
        expected = properties.get(name, {}).get("type")
        if expected in types and (not isinstance(value, types[expected]) or expected == "integer" and isinstance(value, bool)):
            raise BrokerError(f"input {name!r} must be {expected}")


class Broker:
    def __init__(self, evidence: EvidenceStore, snapshots: SnapshotHooks | None = None, budget: Budget | None = None):
        self.evidence = evidence
        self.snapshots = snapshots
        self.budget = budget
        self.usage = BudgetUsage()
        self._capabilities: dict[tuple[str, str], tuple[CapabilityManifest, CapabilityHandler]] = {}

    def register(self, manifest: CapabilityManifest, handler: CapabilityHandler) -> None:
        key = (manifest.name, manifest.version)
        if key in self._capabilities:
            raise BrokerError(f"capability already registered: {key}")
        self._capabilities[key] = (manifest, handler)

    def invoke(self, contract: Contract, request: CapabilityRequest) -> CapabilityResult:
        key = (request.capability_name, request.capability_version)
        if key not in self._capabilities:
            raise BrokerError(f"unknown capability: {key}")
        manifest, handler = self._capabilities[key]
        if request.artifact_kind not in manifest.accepted_artifact_kinds:
            raise BrokerError("artifact kind is not accepted by capability")
        _validate_json_schema(request.inputs, manifest.input_schema)
        mutating = manifest.effect is CapabilityEffect.MUTATE
        if request.requested_mutation_scope and not mutating:
            raise BrokerError("non-mutating capability requested mutation scope")
        if mutating:
            if not request.discrepancy_ids:
                raise BrokerError("mutation must be linked to a discrepancy")
            if not request.requested_mutation_scope:
                raise BrokerError("mutation scope is required")
            if not _authorized(request.requested_mutation_scope, contract.authorized_mutation_scopes):
                raise BrokerError("mutation scope is outside contract authorization")
            if not _authorized(request.requested_mutation_scope, manifest.possible_mutation_scope):
                raise BrokerError("mutation scope is outside capability manifest")
            if self.snapshots is None:
                raise BrokerError("mutation requires snapshot hooks")

        projected = replace(self.usage, actions=self.usage.actions + 1, cost=self.usage.cost + manifest.estimated_cost)
        if self.budget is not None and not projected.within(self.budget):
            raise BrokerError("capability invocation would exceed budget")

        started = monotonic()
        before_hash = self.snapshots.before_mutation(request) if mutating else None
        requested = self.evidence.append("capability_request", {
            "request_id": request.id, "capability": request.capability_name,
            "discrepancy_ids": request.discrepancy_ids, "before_hash": before_hash,
            "effect": manifest.effect.value,
        })
        result = None
        invocation_error = None
        try:
            result = handler.invoke(request)
        except Exception as error:
            invocation_error = f"{type(error).__name__}: {error}"
        after_hash = self.snapshots.after_mutation(request) if mutating else None
        elapsed = int((monotonic() - started) * 1000)
        tokens = int(result.provenance.get("tokens", 0)) if result else 0
        self.usage = replace(projected, tokens=projected.tokens + tokens, wall_time_ms=projected.wall_time_ms + elapsed)
        validation_error = None
        if result is not None and result.request_id != request.id:
            validation_error = "capability result request id mismatch"
        elif result is not None and not _authorized(result.actual_mutation_scope, request.requested_mutation_scope):
            validation_error = "capability mutated outside requested scope"
        elif result is not None:
            missing_provenance = set(manifest.provenance_requirements) - set(result.provenance)
            if missing_provenance:
                validation_error = f"missing required provenance: {sorted(missing_provenance)}"
        self.evidence.append("capability_result", {
            "request_event_id": requested.id, "request_id": request.id,
            "succeeded": result.succeeded if result else False,
            "actual_mutation_scope": [s.resource for s in result.actual_mutation_scope] if result else [],
            "before_hash": before_hash, "after_hash": after_hash,
            "provenance": result.provenance if result else {},
            "error": invocation_error or validation_error or (result.error if result else None),
            "usage": {"actions": self.usage.actions, "tokens": self.usage.tokens,
                      "wall_time_ms": self.usage.wall_time_ms, "cost": self.usage.cost},
        })
        if invocation_error or validation_error:
            raise BrokerError(invocation_error or validation_error)
        if self.budget is not None and not self.usage.within(self.budget):
            raise BrokerError("capability invocation exceeded budget")
        assert result is not None
        return result
