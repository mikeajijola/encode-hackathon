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
    token_policy: str = "fixed_research_budget"
    operational_emergency_token_ceiling: int | None = None


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


class ManifestIntegrityError(RuntimeError):
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
        self.successful_model_calls = 0

    def _elapsed_ms(self) -> int:
        return int((monotonic() - self.started) * 1000)

    def _check(self) -> None:
        if self.actions > self.config.max_actions:
            raise BudgetExceeded("action_budget_exhausted")
        tokens = self.input_tokens + self.output_tokens
        if self.config.token_policy == "fixed_research_budget" and tokens > self.config.max_tokens:
            raise BudgetExceeded("token_budget_exhausted")
        if self.config.token_policy == "measured_cost" and (
            self.config.operational_emergency_token_ceiling is not None
            and tokens > self.config.operational_emergency_token_ceiling
        ):
            raise BudgetExceeded("operational_emergency_token_ceiling")
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
        retries = self.config.retry_policy.get(
            "model_transport_retries", self.config.retry_policy.get("transport", 0))
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
            raise ValueError("model transport retry count must be a non-negative integer")
        last_exception: Exception | None = None
        for attempt in range(1, retries + 2):
            self._check()
            started = monotonic()
            error = None
            reply = None
            self.model_calls += 1
            try:
                reply = self.provider.complete(prompt, model=self.config.model, temperature=self.config.temperature)
            except Exception as exc:
                last_exception = exc
                error = f"{type(exc).__name__}: {exc}"
            trace = {
                "step": self.model_calls, "attempt": attempt, "max_attempts": retries + 1,
                "purpose": purpose,
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
            if reply is None:
                if attempt <= retries:
                    self.event("model_transport_retry", {"purpose": purpose, "failed_attempt": attempt,
                                                          "max_attempts": retries + 1, "error": error})
                    continue
                assert last_exception is not None
                raise last_exception
            self.input_tokens += reply.input_tokens
            self.output_tokens += reply.output_tokens
            self.cost += reply.cost
            self.successful_model_calls += 1
            self._check()
            return reply
        raise AssertionError("unreachable retry loop")

    def usage(self) -> dict[str, Any]:
        return {"actions": self.actions, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "tokens": self.input_tokens + self.output_tokens,
                "latency_ms": self._elapsed_ms(), "cost": self.cost, "model_calls": self.model_calls,
                "successful_model_calls": self.successful_model_calls}


class ExperimentRunner:
    def __init__(self, config: RunConfig, services: Services, provider: ModelProvider, out_dir: Path,
                 *, source_manifest_bytes: bytes | None = None):
        self.config, self.services, self.provider, self.out_dir = config, services, provider, Path(out_dir)
        self.source_manifest_bytes = source_manifest_bytes
        self.source_manifest_sha256 = sha256(source_manifest_bytes).hexdigest() if source_manifest_bytes else None

    def _source_manifest(self) -> Mapping[str, Any] | None:
        if self.source_manifest_bytes is None:
            return None
        try:
            source = json.loads(self.source_manifest_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ManifestIntegrityError(f"source manifest is not valid UTF-8 JSON: {error}") from error
        if not isinstance(source, dict) or not isinstance(source.get("run_config"), dict):
            raise ManifestIntegrityError("source manifest must be an object containing run_config")
        expected = json.loads(json.dumps(asdict(self.config), default=str))
        expected["arm"] = self.config.arm.value
        observed = source["run_config"]
        source_defaults = {
            "deviations": [],
            "token_policy": "fixed_research_budget",
            "operational_emergency_token_ceiling": None,
        }
        mismatched = sorted(
            key for key, value in expected.items()
            if observed.get(key, source_defaults.get(key)) != value
        )
        if mismatched:
            raise ManifestIntegrityError(f"source manifest differs from runtime config: {mismatched}")
        if not isinstance(source.get("backend"), str) or not isinstance(source.get("backend_config"), dict):
            raise ManifestIntegrityError("source manifest lacks backend provenance")
        reproducibility = source.get("reproducibility")
        required_pins = {"protocol_sha256", "selection_sha256", "dataset_metadata_sha256",
                         "uv_lock_sha256", "container_digest"}
        if not isinstance(reproducibility, dict) or not required_pins <= set(reproducibility):
            raise ManifestIntegrityError("source manifest lacks required reproducibility pins")
        return source

    def _prepare(self) -> None:
        source = self._source_manifest()
        if self.out_dir.exists() and any(self.out_dir.iterdir()):
            raise FileExistsError("output directory must be empty")
        for name in ("outputs", "traces", "events", "task_results", "checkpoints"):
            (self.out_dir / name).mkdir(parents=True, exist_ok=True)
        manifest = {"schema_version": "1.1.0", **asdict(self.config)}
        manifest["arm"] = self.config.arm.value
        manifest["runtime_created_unix"] = time()
        manifest["golden_access"] = "offline_scoring_only"
        manifest["source_manifest_sha256"] = self.source_manifest_sha256
        manifest["source_manifest_path"] = "input_manifest.json" if source is not None else None
        manifest["source_manifest"] = source
        if self.source_manifest_bytes is not None:
            (self.out_dir / "input_manifest.json").write_bytes(self.source_manifest_bytes)
        (self.out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n")
        (self.out_dir / "predictions.jsonl").touch()
        (self.out_dir / "first_mutation_predictions.jsonl").touch()
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
        execution = None
        termination_reason = "execution_not_started"
        try:
            runtime.event("task_started", {"task_id": task.id, "artifact_hash": before, "arm": self.config.arm.value,
                                           "source_manifest_sha256": self.source_manifest_sha256})
            if self.config.arm is Arm.A:
                execution = self.services.execute_once(task, None, destination, runtime)
            else:
                phase_before = runtime.usage()
                contract = self.services.compile_contract(task, runtime)
                runtime.event("phase_usage", {"phase": "contract_compilation",
                    "before": phase_before, "after": runtime.usage()})
                runtime.event("accepted_contract", {"contract": contract})
                if self.config.arm is Arm.D:
                    execution, evaluation = self.services.reconcile(task, contract, destination, runtime)
                else:
                    execution = self.services.execute_once(task, contract, destination, runtime)
                    if self.config.arm is Arm.C:
                        evaluation = self.services.evaluate_once(task, contract, execution.artifact, runtime)
                        runtime.event("terminal_evaluation", asdict(evaluation))
            status = execution.status
            if self.config.arm in (Arm.A, Arm.B):
                internal_status = "FULFILLED_UNVERIFIED" if status == "ok" else "UNFULFILLED"
                termination_reason = "one_shot_completed_unverified" if status == "ok" else "execution_failed"
            else:
                passed = evaluation is not None and evaluation.passed
                internal_status = "FULFILLED" if passed else "UNFULFILLED"
                termination_reason = "required_internal_evals_passed" if passed else (
                    f"internal_eval_{evaluation.status}" if evaluation else "evaluation_missing")
        except Exception as exc:
            status = f"error: {type(exc).__name__}: {exc}"[:500]
            internal_status = "UNFULFILLED"
            termination_reason = ("operational_emergency_ceiling"
                                  if "operational_emergency" in str(exc)
                                  else "execution_error")
            runtime.event("task_error", {"error": status})
        if not destination.exists():
            shutil.copy2(task.artifact, destination)
            runtime.event("fallback_projection", {"reason": status})
        after = file_hash(destination)
        eval_rows = list((evaluation.details if evaluation else {}).get("evals", ()))
        eval_status = {row.get("eval_id"): row.get("status") for row in eval_rows}
        artifact_valid = eval_status.get("artifact-valid") == "pass" if evaluation else None
        constraint_violation = eval_status.get("preservation") not in (None, "pass")
        failure_classes = _failure_classes(status, termination_reason, evaluation, internal_status)
        checkpoint = execution.details.get("first_mutation_artifact") if execution else None
        checkpoint_path = Path(checkpoint) if checkpoint else None
        checkpoint_relative = (checkpoint_path.relative_to(self.out_dir).as_posix()
                               if checkpoint_path and checkpoint_path.is_file() else None)
        mutation_outputs = []
        for item in (execution.details.get("mutation_artifacts", ()) if execution else ()):
            path = Path(item)
            if path.is_file():
                mutation_outputs.append(path.relative_to(self.out_dir).as_posix())
        result = {
            "id": task.id, "arm": self.config.arm.value, "status": status,
            "output": f"outputs/{destination.name}", "input_artifact_hash": before,
            "output_artifact_hash": after, "contract_compiled": contract is not None,
            "internal_status": internal_status, "termination_reason": termination_reason,
            "terminal_eval": asdict(evaluation) if evaluation else None, "usage": runtime.usage(),
            "rendered_eval": "delegated_to_adapter",
            "artifact_valid": artifact_valid, "constraint_violation": constraint_violation,
            "failure_classes": failure_classes, "first_mutation_output": checkpoint_relative,
            "first_mutation_pass": None, "mutation_outputs": mutation_outputs,
        }
        runtime.event("task_finished", result)
        (self.out_dir / "task_results" / f"{task.id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        with (self.out_dir / "predictions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"id": task.id, "output": result["output"], "status": status}) + "\n")
        if checkpoint_relative:
            with (self.out_dir / "first_mutation_predictions.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"id": task.id, "output": checkpoint_relative,
                                         "status": "checkpoint"}) + "\n")
        with (self.out_dir / "run.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{task.id} arm={self.config.arm.value} status={status} actions={runtime.actions}\n")
        return result


def _failure_classes(status: str, termination_reason: str, evaluation: EvaluationResult | None,
                     internal_status: str) -> list[str]:
    """Pre-score failure labels; official-score disagreement is added offline."""
    labels: set[str] = set()
    lowered = f"{status} {termination_reason}".lower()
    if "budget" in lowered:
        labels.add("budget_failure")
    if "contract" in lowered or "valueerror" in lowered and "transition" not in lowered:
        labels.add("specification_failure")
    if "capability" in lowered:
        labels.add("capability_failure")
    if "no_safe_transition" in lowered:
        labels.add("planning_failure")
    if "no_progress" in lowered:
        labels.add("reconciliation_failure")
    if "execution_error" in lowered:
        labels.add("execution_failure")
    details = evaluation.details if evaluation else {}
    for discrepancy in details.get("discrepancies", ()):
        kind = discrepancy.get("kind")
        mapped = {
            "knowledge_discrepancy": "knowledge_gap",
            "constraint_violation": "constraint_violation",
            "artifact_invalid": "artifact_corruption",
            "capability_failure": "capability_failure",
        }.get(kind)
        if mapped:
            labels.add(mapped)
    if internal_status != "UNFULFILLED":
        return []
    return sorted(labels)


def verify_run_manifest(out_dir: Path | str) -> Mapping[str, Any]:
    """Reconstruct and verify the retained source manifest and its runtime binding."""
    root = Path(out_dir)
    try:
        runtime = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestIntegrityError(f"runtime manifest unreadable: {error}") from error
    expected_hash = runtime.get("source_manifest_sha256")
    relative = runtime.get("source_manifest_path")
    if not expected_hash or relative != "input_manifest.json":
        raise ManifestIntegrityError("runtime manifest has no retained source-manifest binding")
    source_path = root / relative
    try:
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestIntegrityError(f"retained source manifest unreadable: {error}") from error
    observed_hash = sha256(source_bytes).hexdigest()
    if observed_hash != expected_hash:
        raise ManifestIntegrityError("retained source manifest hash mismatch")
    if source != runtime.get("source_manifest"):
        raise ManifestIntegrityError("embedded source manifest differs from retained bytes")
    events = sorted((root / "events").glob("*.jsonl"))
    for path in events:
        if path.name.endswith(".broker.jsonl"):
            continue
        first = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        if first.get("event_type") != "task_started" or first.get("payload", {}).get("source_manifest_sha256") != expected_hash:
            raise ManifestIntegrityError(f"task event is not bound to source manifest: {path.name}")
    return runtime
