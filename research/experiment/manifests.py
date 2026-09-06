"""Generate and validate reproducible four-arm SpreadsheetBench run manifests."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from protocol.selection import validate_manifest as validate_selection


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "protocol" / "preregistered_experiment.json"
DEFAULT_SELECTION = ROOT / "protocol" / "development_selection.json"
DEFAULT_LOCK = ROOT / "uv.lock"
BACKEND = "backends.spreadsheetbench:factory"
ARMS = ("A", "B", "C", "D")
FORBIDDEN_PIN_MARKERS = ("todo", "to_be_", "placeholder", "unpinned", "latest")
DEFAULT_GEMINI_MODEL = "gemini-3.7-flash"
DEFAULT_GEMINI_MODEL_VERSION = "3.7-flash-08-2026"


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require_pin(name: str, value: str) -> str:
    value = value.strip()
    if not value or any(marker in value.lower() for marker in FORBIDDEN_PIN_MARKERS):
        raise ValueError(f"{name} must be explicitly pinned (not TODO/latest/placeholder)")
    return value


def _require_sha256(name: str, value: str, *, prefixed: bool = False) -> str:
    value = _require_pin(name, value).lower()
    expression = r"sha256:[0-9a-f]{64}" if prefixed else r"[0-9a-f]{64}"
    if not re.fullmatch(expression, value):
        raise ValueError(f"{name} must be a {'sha256:' if prefixed else ''}64-hex digest")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_manifests(
    *, experiment_id: str, model: str, model_version: str, container_digest: str,
    soffice_version: str, scorer_commit: str, dataset_metadata_sha256: str,
    environment: str, max_cost: float, selection_path: Path = DEFAULT_SELECTION,
    protocol_path: Path = DEFAULT_PROTOCOL, lock_path: Path = DEFAULT_LOCK,
    context_max_cells: int = 400, context_max_chars: int = 30_000,
    provider_timeout_seconds: int = 120, deviations: Sequence[str] = (),
    dataset_json: Path | None = None, provider: str = "gemini",
) -> dict[str, dict[str, Any]]:
    protocol, selection = _load_json(protocol_path), _load_json(selection_path)
    validate_selection(selection)
    selection_hash = selection["selection_sha256"]
    dataset_hash = _require_sha256("dataset_metadata_sha256", dataset_metadata_sha256)
    if dataset_hash != selection["source_metadata_sha256"]:
        raise ValueError("dataset metadata hash differs from committed selection source")
    if dataset_json is not None and file_hash(dataset_json) != dataset_hash:
        raise ValueError("dataset.json content does not match dataset metadata pin")
    if context_max_cells < 1 or context_max_chars < 100 or provider_timeout_seconds < 1:
        raise ValueError("context limits and provider timeout must be positive")
    if max_cost < 0:
        raise ValueError("max_cost must be non-negative")
    if provider not in {"gemini", "openrouter"}:
        raise ValueError("provider must be gemini or openrouter")

    model = _require_pin("model", model)
    model_version = _require_pin("model_version", model_version)
    experiment_id = _require_pin("experiment_id", experiment_id)
    if (experiment_id == protocol.get("experiment_id") and
            selection_hash != protocol.get("task_set", {}).get("selection_manifest_sha256")):
        raise ValueError("registered experiment must use the preregistered held-out selection")
    container_digest = _require_sha256("container_digest", container_digest, prefixed=True)
    soffice_version = _require_pin("soffice_version", soffice_version)
    environment = _require_pin("environment", environment)
    if not re.fullmatch(r"[0-9a-f]{40}", scorer_commit.lower()):
        raise ValueError("scorer_commit must be a full 40-hex Git commit")
    if not all(isinstance(item, str) and item.strip() for item in deviations):
        raise ValueError("deviations must be non-empty strings")

    fixed = protocol["fixed_conditions"]
    common = {
        "schema_version": "1.0.0",
        "backend": BACKEND,
        "task_selection": selection,
        "backend_config": {
            "dataset_dir": "/data/dataset",
            "context_limits": {"max_cells": context_max_cells, "max_chars": context_max_chars},
            "provider": {"type": provider, "timeout_seconds": provider_timeout_seconds},
        },
        "reproducibility": {
            "protocol_sha256": file_hash(protocol_path),
            "selection_sha256": selection_hash,
            "selection_file_sha256": file_hash(selection_path),
            "dataset_metadata_sha256": dataset_hash,
            "uv_lock_sha256": file_hash(lock_path),
            "backend_factory": BACKEND,
            "environment": environment,
            "container_digest": container_digest,
            "soffice_version": soffice_version,
            "context_limits": {"max_cells": context_max_cells, "max_chars": context_max_chars},
            "provider_timeout_seconds": provider_timeout_seconds,
            "deviations": list(deviations),
            "multimodal_eval": "delegated_to_adapter_when_intent_has_visual_semantics",
        },
        "run_config": {
            "experiment_id": experiment_id,
            "model": model,
            "model_version": model_version,
            "temperature": fixed["temperature"],
            "max_tokens": fixed["token_budget"],
            "max_actions": fixed["action_budget"],
            "max_wall_time_ms": fixed["wall_clock_seconds"] * 1000,
            "max_cost": max_cost,
            "environment_image_digest": container_digest,
            "recalculation_engine": soffice_version,
            "scorer_commit": scorer_commit.lower(),
            "retry_policy": fixed["retry_policy"],
            "deviations": list(deviations),
            "token_policy": "fixed_research_budget",
            "operational_emergency_token_ceiling": None,
        },
    }
    manifests = {}
    for arm in ARMS:
        manifest = json.loads(json.dumps(common))
        manifest["run_config"]["arm"] = arm
        manifests[arm] = manifest
    validate_manifest_set(manifests, protocol_path=protocol_path,
                          selection_path=selection_path, lock_path=lock_path)
    return manifests


def validate_manifest_set(
    manifests: Mapping[str, Mapping[str, Any]], *, protocol_path: Path = DEFAULT_PROTOCOL,
    selection_path: Path | None = DEFAULT_SELECTION, lock_path: Path = DEFAULT_LOCK,
) -> None:
    if set(manifests) != set(ARMS):
        raise ValueError("manifest set must contain exactly arms A, B, C, D")
    protocol = _load_json(protocol_path)
    fixed = protocol["fixed_conditions"]
    selection = (_load_json(selection_path) if selection_path is not None
                 else json.loads(json.dumps(manifests.get("A", {}).get("task_selection"))))
    if not isinstance(selection, dict):
        raise ValueError("manifest set lacks an embedded task selection")
    validate_selection(selection)
    expected_hashes = {
        "protocol_sha256": file_hash(protocol_path),
        "selection_sha256": selection["selection_sha256"],
        "uv_lock_sha256": file_hash(lock_path),
    }
    if selection_path is not None:
        expected_hashes["selection_file_sha256"] = file_hash(selection_path)
    normalized = []
    for arm in ARMS:
        value = manifests[arm]
        if value.get("backend") != BACKEND or value.get("run_config", {}).get("arm") != arm:
            raise ValueError(f"manifest {arm} has wrong backend or arm")
        reproducibility = value.get("reproducibility") or {}
        embedded_selection = value.get("task_selection")
        if not isinstance(embedded_selection, dict):
            raise ValueError(f"manifest {arm} lacks embedded task selection")
        validate_selection(embedded_selection)
        if embedded_selection != selection:
            raise ValueError(f"manifest {arm} embedded task selection differs from selection pin")
        for key, expected in expected_hashes.items():
            if reproducibility.get(key) != expected:
                raise ValueError(f"manifest {arm} has invalid {key}")
        _require_sha256("dataset_metadata_sha256", reproducibility.get("dataset_metadata_sha256", ""))
        _require_sha256("container_digest", reproducibility.get("container_digest", ""), prefixed=True)
        _require_pin("environment", str(reproducibility.get("environment", "")))
        _require_pin("soffice_version", str(reproducibility.get("soffice_version", "")))
        run = value["run_config"]
        for key in ("experiment_id", "model", "model_version", "recalculation_engine"):
            _require_pin(key, str(run.get(key, "")))
        if not re.fullmatch(r"[0-9a-f]{40}", str(run.get("scorer_commit", ""))):
            raise ValueError("invalid scorer commit pin")
        expected_fixed = {
            "temperature": fixed["temperature"],
            "max_tokens": fixed["token_budget"],
            "max_actions": fixed["action_budget"],
            "max_wall_time_ms": fixed["wall_clock_seconds"] * 1000,
            "retry_policy": fixed["retry_policy"],
        }
        if any(run.get(key) != expected for key, expected in expected_fixed.items()):
            raise ValueError(f"manifest {arm} differs from preregistered fixed conditions")
        if run.get("environment_image_digest") != reproducibility.get("container_digest"):
            raise ValueError(f"manifest {arm} has inconsistent container digest")
        if run.get("recalculation_engine") != reproducibility.get("soffice_version"):
            raise ValueError(f"manifest {arm} has inconsistent soffice version")
        if reproducibility.get("dataset_metadata_sha256") != selection["source_metadata_sha256"]:
            raise ValueError(f"manifest {arm} dataset hash differs from selection source")
        backend = value.get("backend_config") or {}
        if backend.get("context_limits") != reproducibility.get("context_limits"):
            raise ValueError(f"manifest {arm} has inconsistent context limits")
        if (backend.get("provider") or {}).get("timeout_seconds") != reproducibility.get("provider_timeout_seconds"):
            raise ValueError(f"manifest {arm} has inconsistent provider timeout")
        copy = json.loads(json.dumps(value))
        copy["run_config"].pop("arm")
        normalized.append(copy)
    if any(value != normalized[0] for value in normalized[1:]):
        raise ValueError("arms differ in conditions other than treatment arm")


def write_manifest_set(manifests: Mapping[str, Mapping[str, Any]], manifest_dir: Path, run_root: Path) -> None:
    if manifest_dir.resolve() == run_root.resolve():
        raise ValueError("manifest and run output paths must be distinct")
    for path in (manifest_dir, run_root):
        if path.exists():
            raise FileExistsError(f"refusing to reuse output path: {path}")
    manifest_dir.mkdir(parents=True)
    run_root.mkdir(parents=True)
    for arm in ARMS:
        (manifest_dir / f"{arm}.json").write_text(
            json.dumps(manifests[arm], indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        (run_root / arm).mkdir()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate pinned A-D SpreadsheetBench manifests")
    parser.add_argument("--manifest-dir", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--model", default=os.environ.get("EXPERIMENT_MODEL", DEFAULT_GEMINI_MODEL))
    parser.add_argument("--model-version", default=os.environ.get(
        "EXPERIMENT_MODEL_VERSION", DEFAULT_GEMINI_MODEL_VERSION))
    parser.add_argument("--container-digest", required=True)
    parser.add_argument("--soffice-version", required=True)
    parser.add_argument("--scorer-commit", required=True)
    parser.add_argument("--dataset-metadata-sha256", required=True)
    parser.add_argument("--dataset-json")
    parser.add_argument("--selection", default=str(DEFAULT_SELECTION))
    parser.add_argument("--environment", required=True)
    parser.add_argument("--max-cost", required=True, type=float)
    parser.add_argument("--context-max-cells", type=int, default=400)
    parser.add_argument("--context-max-chars", type=int, default=30_000)
    parser.add_argument("--provider-timeout-seconds", type=int, default=120)
    parser.add_argument("--provider", choices=("gemini", "openrouter"), default="gemini")
    parser.add_argument("--deviation", action="append", default=[])
    args = parser.parse_args(argv)
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    manifests = build_manifests(
        experiment_id=args.experiment_id, model=args.model, model_version=args.model_version,
        container_digest=args.container_digest, soffice_version=args.soffice_version,
        scorer_commit=args.scorer_commit, dataset_metadata_sha256=args.dataset_metadata_sha256,
        dataset_json=Path(args.dataset_json) if args.dataset_json else None,
        selection_path=Path(args.selection),
        environment=args.environment, max_cost=args.max_cost,
        context_max_cells=args.context_max_cells, context_max_chars=args.context_max_chars,
        provider_timeout_seconds=args.provider_timeout_seconds, deviations=args.deviation,
        provider=args.provider,
    )
    write_manifest_set(manifests, Path(args.manifest_dir), Path(args.run_root))


if __name__ == "__main__":
    main()
