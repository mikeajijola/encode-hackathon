"""Bounded directory/text-config adapter used to test control-plane portability."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from fulfilment import (
    CapabilityEffect,
    CapabilityManifest,
    CapabilityRequest,
    CapabilityResult,
    Contract,
    EvalResult,
    EvalSpec,
    EvalStatus,
    Observation,
    Scope,
)


class SelectorError(ValueError):
    pass


@dataclass(frozen=True)
class FileSelector:
    relative_path: str
    json_pointer: str | None = None

    @classmethod
    def parse(cls, scope: Scope | str) -> "FileSelector":
        resource = scope.resource if isinstance(scope, Scope) else scope
        if not resource.startswith("file/"):
            raise SelectorError("text adapter selectors must start with 'file/'")
        path_and_pointer = resource[5:].split("#", 1)
        relative = path_and_pointer[0]
        parts = Path(relative).parts
        if not relative or Path(relative).is_absolute() or ".." in parts:
            raise SelectorError("selector path must be a bounded relative path")
        pointer = path_and_pointer[1] if len(path_and_pointer) == 2 else None
        if pointer is not None and pointer and not pointer.startswith("/"):
            raise SelectorError("JSON pointer must be empty or start with '/'")
        return cls(relative, pointer)

    @property
    def resource(self) -> str:
        suffix = f"#{self.json_pointer}" if self.json_pointer is not None else ""
        return f"file/{self.relative_path}{suffix}"


def _pointer_get(document: Any, pointer: str) -> Any:
    current = document
    if pointer == "":
        return current
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _pointer_set(document: Any, pointer: str, value: Any) -> Any:
    if pointer == "":
        return value
    current = document
    tokens = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    for token in tokens[:-1]:
        current = current[int(token)] if isinstance(current, list) else current[token]
    final = tokens[-1]
    if isinstance(current, list):
        current[int(final)] = value
    else:
        current[final] = value
    return document


class DirectoryWorkspace:
    """Owns bounded filesystem access, snapshots, rollback, and result selection."""

    def __init__(self, root: Path | str, allowed_scopes: Iterable[Scope]):
        self.root = Path(root).resolve()
        self.allowed_scopes = tuple(allowed_scopes)
        self._allowed = {scope.resource for scope in self.allowed_scopes}
        self._snapshots: list[dict[str, bytes]] = []
        self._observation_number = 0

    def resolve(self, selector: FileSelector) -> Path:
        path = (self.root / selector.relative_path).resolve()
        if self.root != path and self.root not in path.parents:
            raise SelectorError("selector escapes workspace")
        return path

    def _require_allowed(self, scope: Scope) -> FileSelector:
        if scope.resource not in self._allowed:
            raise SelectorError(f"selector outside adapter scope: {scope.resource}")
        return FileSelector.parse(scope)

    def hash(self) -> str:
        digest = sha256()
        for relative in sorted({FileSelector.parse(scope).relative_path for scope in self.allowed_scopes}):
            path = self.resolve(FileSelector(relative))
            digest.update(relative.encode())
            digest.update(path.read_bytes() if path.exists() else b"<missing>")
        return digest.hexdigest()

    def observe(self, scopes: tuple[Scope, ...] = ()) -> Observation:
        selected = scopes or self.allowed_scopes
        facts, validity, errors = {}, {}, {}
        for scope in selected:
            try:
                selector = self._require_allowed(scope)
                text = self.resolve(selector).read_text(encoding="utf-8")
                if selector.relative_path.lower().endswith(".json"):
                    document = json.loads(text)
                    value = (_pointer_get(document, selector.json_pointer)
                             if selector.json_pointer is not None else document)
                else:
                    if selector.json_pointer is not None:
                        raise SelectorError("JSON pointers require a .json file")
                    value = text
                facts[scope.resource] = value
                validity[scope.resource] = True
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as error:
                validity[scope.resource] = False
                errors[scope.resource] = f"{type(error).__name__}: {error}"
        inspected = tuple(selected)
        omitted = tuple(scope for scope in self.allowed_scopes if scope not in inspected)
        self._observation_number += 1
        return Observation(
            f"text-observation-{self._observation_number}", str(self.root), "directory",
            self.hash(), facts, {"selector_validity": validity}, inspected, omitted,
            {"errors": errors},
        )

    def before_mutation(self, request: CapabilityRequest) -> str:
        snapshot = {}
        for scope in request.requested_mutation_scope:
            selector = self._require_allowed(scope)
            path = self.resolve(selector)
            snapshot[selector.relative_path] = path.read_bytes() if path.exists() else b""
        self._snapshots.append(snapshot)
        return self.hash()

    def after_mutation(self, request: CapabilityRequest) -> str:
        return self.hash()

    def rollback(self, reason: str) -> None:
        if not self._snapshots:
            return
        for relative, content in self._snapshots[-1].items():
            self.resolve(FileSelector(relative)).write_bytes(content)

    def select_result(self, observation: Observation, status: str) -> dict[str, object]:
        return {"artifact_path": str(self.root), "artifact_hash": observation.artifact_hash, "status": status}


class InspectTextCapability:
    manifest = CapabilityManifest(
        "inspect_text", "1", ("directory",),
        {"type": "object", "properties": {"selector": {"type": "string"}},
         "required": ["selector"], "additionalProperties": False},
        CapabilityEffect.OBSERVE,
    )

    def __init__(self, workspace: DirectoryWorkspace): self.workspace = workspace

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        observation = self.workspace.observe((Scope(request.inputs["selector"]),))
        return CapabilityResult(request.id, True, {"facts": dict(observation.facts)}, provenance={"actor": "text-adapter"})


class EditTextCapability:
    manifest = CapabilityManifest(
        "edit_text", "1", ("directory",),
        {"type": "object", "properties": {"selector": {"type": "string"}, "value": {}},
         "required": ["selector", "value"], "additionalProperties": False},
        CapabilityEffect.MUTATE, (Scope("file/*"),), provenance_requirements=("actor",),
    )

    def __init__(self, workspace: DirectoryWorkspace): self.workspace = workspace

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        scope = Scope(request.inputs["selector"])
        if request.requested_mutation_scope != (scope,):
            raise SelectorError("input selector and requested mutation scope differ")
        selector = self.workspace._require_allowed(scope)
        path = self.workspace.resolve(selector)
        if selector.json_pointer is None:
            if not isinstance(request.inputs["value"], str):
                raise SelectorError("whole-file text edits require a string")
            path.write_text(request.inputs["value"], encoding="utf-8")
        else:
            document = json.loads(path.read_text(encoding="utf-8"))
            document = _pointer_set(document, selector.json_pointer, request.inputs["value"])
            path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return CapabilityResult(request.id, True, {"selector": scope.resource}, (scope,), {"actor": "text-adapter"})


class ValidateTextCapability:
    manifest = CapabilityManifest(
        "validate_text", "1", ("directory",), {"type": "object"}, CapabilityEffect.VALIDATE,
    )

    def __init__(self, workspace: DirectoryWorkspace): self.workspace = workspace

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        observation = self.workspace.observe()
        validity = observation.interpretations["selector_validity"]
        return CapabilityResult(request.id, all(validity.values()), {"validity": dict(validity)},
                                provenance={"actor": "text-adapter"})


class DesiredSelectorValueEvaluator:
    """Deterministically compares independently observed state with contract data."""

    def evaluate(self, spec: EvalSpec, observation: Observation, contract: Contract) -> EvalResult:
        selector, expected = spec.parameters["selector"], spec.parameters["expected"]
        if selector not in observation.facts:
            return EvalResult(spec.id, observation.id, EvalStatus.FAIL, "selector was not observed",
                              details={"knowledge_gap": True, "expected": expected})
        observed = observation.facts[selector]
        return EvalResult(spec.id, observation.id,
                          EvalStatus.PASS if observed == expected else EvalStatus.FAIL,
                          "desired value present" if observed == expected else "desired value differs",
                          details={"expected": expected, "observed": observed})


class TextArtifactValidityEvaluator:
    def evaluate(self, spec: EvalSpec, observation: Observation, contract: Contract) -> EvalResult:
        selectors = tuple(spec.parameters["selectors"])
        validity = observation.interpretations.get("selector_validity", {})
        invalid = [selector for selector in selectors if not validity.get(selector, False)]
        return EvalResult(spec.id, observation.id,
                          EvalStatus.FAIL if invalid else EvalStatus.PASS,
                          "artifact invalid" if invalid else "artifact valid",
                          details={"kind": "artifact_invalid", "observed": invalid})
