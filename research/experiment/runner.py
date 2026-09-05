"""Artifact-neutral four-arm runner.

Domain behavior is injected through ``Services``. This module owns treatment
boundaries, budgets, traces, manifests, output projection, and hashes only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import shutil
from time import monotonic, time
from typing import Any, Mapping, Protocol


class Arm(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True)
class Task:
    id: str
    intent: str
    artifact: Path
    artifact_kind: str
    context: Mapping[str, Any]
    capability_manifests: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class RunConfig:
    experiment_id: str
    arm: Arm
    model: str
    model_version: str
    temperature: float
    max_tokens: int
    max_actions: int
    max_wall_time_ms: int
    max_cost: float
    environment_image_digest: str
    recalculation_engine: str
    scorer_commit: str
    retry_policy: Mapping[str, Any]
    deviations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelReply:
    text: str
    input_tokens: int
    output_tokens: int
    cost: float = 0.0
    provider_request_id: str | None = None


class ModelProvider(Protocol):
    def complete(self, prompt: str, *, model: str, temperature: float) -> ModelReply: ...


@dataclass(frozen=True)
class ExecutionResult:
    artifact: Path
    status: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    status: str
    details: Mapping[str, Any]


class Services(Protocol):
    """Dependency-injected semantics; implementations must not access goldens."""

    def compile_contract(self, task: Task, runtime: "TaskRuntime") -> Mapping[str, Any]: ...
    def execute_once(self, task: Task, contract: Mapping[str, Any] | None,
                     destination: Path, runtime: "TaskRuntime") -> ExecutionResult: ...
    def evaluate_once(self, task: Task, contract: Mapping[str, Any], artifact: Path,
                      runtime: "TaskRuntime") -> EvaluationResult: ...
    def reconcile(self, task: Task, contract: Mapping[str, Any], destination: Path,
                  runtime: "TaskRuntime") -> tuple[ExecutionResult, EvaluationResult]: ...


class BudgetExceeded(RuntimeError):
    pass


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class TaskRuntime:
    """Common accounting and trace boundary shared by all treatments."""

    def __init__(self, config: RunConfig, provider: ModelProvider, trace_path: Path, event_path: Path):
        self.config = config
        self.provider = provider
        self.trace_path = trace_path
        self.event_path = event_path
        self.started = monotonic()
        self.actions = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.model_calls = 0

    def _elapsed_ms(self) -> int:
        return int((monotonic() - self.started) * 1000)

    def _check(self) -> None:
        if self.actions > self.config.max_actions:
            raise BudgetExceeded("action_budget_exhausted")
        if self.input_tokens + self.output_tokens > self.config.max_tokens:
            raise BudgetExceeded("token_budget_exhausted")
        if self._elapsed_ms() > self.config.max_wall_time_ms:
            raise BudgetExceeded("wall_clock_budget_exhausted")
        if self.cost > self.config.max_cost:
            raise BudgetExceeded("cost_budget_exhausted")

    def event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        sequence = len(self.event_path.read_text(encoding="utf-8").splitlines()) if self.event_path.exists() else 0
        record = {"sequence": sequence,
                  "timestamp_unix": time(), "event_type": event_type, "payload": payload}
        with self.event_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    def action(self, name: str, details: Mapping[str, Any] | None = None) -> None:
        self.actions += 1
        self._check()
        self.event("action", {"name": name, "details": details or {}, "actions": self.actions})

    def complete(self, prompt: str, *, purpose: str) -> ModelReply:
        self._check()
        started = monotonic()
        error = None
        reply = None
        try:
            reply = self.provider.complete(prompt, model=self.config.model, temperature=self.config.temperature)
            self.input_tokens += reply.input_tokens
            self.output_tokens += reply.output_tokens
            self.cost += reply.cost
            self.model_calls += 1
            self._check()
            return reply
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            trace = {
                "step": self.model_calls + (0 if reply else 1), "purpose": purpose,
                "model": self.config.model, "model_version": self.config.model_version,
                "temperature": self.config.temperature, "prompt": prompt,
                "response": reply.text if reply else None,
                "input_tokens": reply.input_tokens if reply else None,
                "output_tokens": reply.output_tokens if reply else None,
                "cost": reply.cost if reply else None,
                "latency_ms": int((monotonic() - started) * 1000), "error": error,
                "provider_request_id": reply.provider_request_id if reply else None,
            }
            with self.trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(trace, sort_keys=True) + "\n")

    def usage(self) -> dict[str, Any]:
        return {"actions": self.actions, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "tokens": self.input_tokens + self.output_tokens,
                "latency_ms": self._elapsed_ms(), "cost": self.cost, "model_calls": self.model_calls}


class ExperimentRunner:
    def __init__(self, config: RunConfig, services: Services, provider: ModelProvider, out_dir: Path):
        self.config, self.services, self.provider, self.out_dir = config, services, provider, Path(out_dir)

    def _prepare(self) -> None:
        if self.out_dir.exists() and any(self.out_dir.iterdir()):
            raise FileExistsError("output directory must be empty")
        for name in ("outputs", "traces", "events", "task_results"):
            (self.out_dir / name).mkdir(parents=True, exist_ok=True)
        manifest = {"schema_version": "1.0.0", **asdict(self.config)}
        manifest["arm"] = self.config.arm.value
        manifest["created_unix"] = time()
        manifest["golden_access"] = "offline_scoring_only"
        (self.out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        (self.out_dir / "predictions.jsonl").touch()
        (self.out_dir / "run.log").touch()

    def run(self, tasks: list[Task]) -> list[dict[str, Any]]:
        task_ids = [task.id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task ids must be unique")
        if any(not task_id or Path(task_id).name != task_id for task_id in task_ids):
            raise ValueError("task ids must be nonempty path-safe names")
        if any(not task.artifact.is_file() for task in tasks):
            raise FileNotFoundError("every input artifact must be a file")
        self._prepare()
        results = []
        for task in tasks:
            results.append(self._run_task(task))
        return results

    def _run_task(self, task: Task) -> dict[str, Any]:
        destination = self.out_dir / "outputs" / f"{task.id}{task.artifact.suffix}"
        runtime = TaskRuntime(self.config, self.provider, self.out_dir / "traces" / f"{task.id}.jsonl",
                              self.out_dir / "events" / f"{task.id}.jsonl")
        before = file_hash(task.artifact)
        contract = None
        evaluation = None
        try:
            runtime.event("task_started", {"task_id": task.id, "artifact_hash": before, "arm": self.config.arm.value})
            if self.config.arm is Arm.A:
                execution = self.services.execute_once(task, None, destination, runtime)
            else:
                contract = self.services.compile_contract(task, runtime)
                runtime.event("accepted_contract", {"contract": contract})
                if self.config.arm is Arm.D:
                    execution, evaluation = self.services.reconcile(task, contract, destination, runtime)
                else:
                    execution = self.services.execute_once(task, contract, destination, runtime)
                    if self.config.arm is Arm.C:
                        evaluation = self.services.evaluate_once(task, contract, execution.artifact, runtime)
                        runtime.event("terminal_evaluation", asdict(evaluation))
            status = execution.status
        except Exception as exc:
            status = f"error: {type(exc).__name__}: {exc}"[:500]
            runtime.event("task_error", {"error": status})
        if not destination.exists():
            shutil.copy2(task.artifact, destination)
            runtime.event("fallback_projection", {"reason": status})
        after = file_hash(destination)
        result = {
            "id": task.id, "arm": self.config.arm.value, "status": status,
            "output": f"outputs/{destination.name}", "input_artifact_hash": before,
            "output_artifact_hash": after, "contract_compiled": contract is not None,
            "terminal_eval": asdict(evaluation) if evaluation else None, "usage": runtime.usage(),
            "rendered_eval": "delegated_to_adapter",
        }
        runtime.event("task_finished", result)
        (self.out_dir / "task_results" / f"{task.id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        with (self.out_dir / "predictions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"id": task.id, "output": result["output"], "status": status}) + "\n")
        with (self.out_dir / "run.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{task.id} arm={self.config.arm.value} status={status} actions={runtime.actions}\n")
        return result
