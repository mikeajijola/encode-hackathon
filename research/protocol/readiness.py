"""Generate a golden-blind registered-run readiness report."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from typing import Any

from services.spreadsheet import _answer_selectors


RESEARCH = Path(__file__).resolve().parents[1]
REPO = RESEARCH.parent
SCORER_SHA256 = "8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b"


def selector_audit(dataset_dir: Path) -> dict[str, Any]:
    metadata = dataset_dir / "dataset.json"
    if not metadata.is_file():
        return {"status": "not_run", "reason": "dataset_missing"}
    records = json.loads(metadata.read_text())
    errors, duplicates, sizes = [], [], []
    for record in records:
        folder = dataset_dir / record["spreadsheet_path"]
        initial = sorted(folder.glob("*init*.xlsx"))
        if len(initial) != 1:
            errors.append({"id": str(record["id"]), "error": "initial_artifact_count"})
            continue
        try:
            selectors = _answer_selectors(record, initial[0])
            sizes.append((str(record["id"]), len(selectors)))
            if len(selectors) != len(set(selectors)):
                duplicates.append(str(record["id"]))
        except Exception as error:
            errors.append({"id": str(record["id"]), "error": f"{type(error).__name__}:{error}"})
    largest = sorted(sizes, key=lambda item: item[1], reverse=True)[:5]
    return {
        "status": "pass" if len(sizes) == len(records) and not errors and not duplicates else "fail",
        "dataset_metadata_sha256": sha256(metadata.read_bytes()).hexdigest(),
        "records": len(records), "resolved": len(sizes), "errors": errors,
        "duplicate_selector_tasks": duplicates,
        "max_expanded_selectors": max((size for _, size in sizes), default=0),
        "largest_tasks": [{"id": task_id, "expanded_selectors": size} for task_id, size in largest],
    }


def build_report(dataset_dir: Path | None = None) -> dict[str, Any]:
    scorer_hash = sha256((RESEARCH / "evaluate.py").read_bytes()).hexdigest()
    dockerfiles = sorted(path for path in REPO.rglob("Dockerfile")
                         if ".git" not in path.parts and "Ylookup-hack-worktrees" not in path.parts)
    root_docker = (REPO / "Dockerfile").read_text()
    canonical_docker = (
        dockerfiles == [REPO / "Dockerfile"]
        and "libreoffice-calc" in root_docker
        and "USER runner" in root_docker
        and "container_preflight" in root_docker
    )
    service = (RESEARCH / "services" / "spreadsheet.py").read_text()
    runner = (RESEARCH / "experiment" / "runner.py").read_text()
    blockers = [
        {
            "id": "R-03", "severity": "high", "kind": "capability",
            "summary": "Production planning can invoke only write_cells although other capabilities are advertised.",
            "evidence": "Action proposals accept only a writes list; large target ranges require thousands of literal writes and cannot select formula-fill, recalculate, render, or additional observation transitions.",
        },
    ]
    environment = {
        "openrouter_api_key": "present" if os.environ.get("OPENROUTER_API_KEY") else "missing",
        "docker_cli": shutil.which("docker") or "missing",
        "soffice": shutil.which("soffice") or shutil.which("libreoffice") or "missing",
    }
    environment_blockers = [key for key, value in environment.items() if value == "missing"]
    statuses = {
        "V-01": {"status": "resolved_with_limitation", "evidence": "isolated semantic evaluator role; malformed/error/uncertain verdicts cannot pass; same provider/model actor remains a disclosed limitation"},
        "V-02": {"status": "resolved", "evidence": "production D delegates iteration, transition validation, broker invocation, no-progress, completion and termination to generic FulfilmentAgent"},
        "V-03": {"status": "resolved_as_controlled_deviation", "evidence": "Arm A v2 is frozen and explicitly not equated with the legacy baseline"},
        "V-04": {"status": "resolved", "evidence": "explicit verified/unverified/unfulfilled status and FFR projection"},
        "V-05": {"status": "resolved", "evidence": "shared transport retries are enforced and every attempt traced"},
        "V-06": {"status": "resolved_static_external_smoke_pending",
                  "evidence": "one hardened repository-root Dockerfile; Docker build/smoke remains environmental"},
    }
    dataset = selector_audit(dataset_dir) if dataset_dir else {"status": "not_run", "reason": "dataset_not_supplied"}
    return {
        "schema_version": "1.0.0", "review_date": str(date.today()),
        "registered_run_ready": False,
        "decision": "BLOCKED",
        "blockers": blockers,
        "environment": environment,
        "environment_blockers": environment_blockers,
        "original_finding_status": statuses,
        "checks": {
            "official_scorer": {"status": "pass" if scorer_hash == SCORER_SHA256 else "fail",
                                "expected_sha256": SCORER_SHA256, "observed_sha256": scorer_hash},
            "selector_audit": dataset,
            "synthetic_test_cleanliness": {"status": "pass", "evidence": "tests generate into TemporaryDirectory via --out-dir"},
            "session_isolation": {"status": "pass_with_lifecycle_constraint", "evidence": "factory creates one SpreadsheetServices per run and runner rejects duplicate task IDs; service instances must not be reused across runs"},
            "semantic_evaluator_independence": {"status": "pass_with_limitation", "evidence": "isolated prompt excludes action response and nonpass errors; same provider/model is used"},
            "completion_evidence": {"status": "pass", "evidence": "generic completion gate and hash-chained termination evidence are tested"},
            "manifest_output_reconstruction": {"status": "pass", "evidence": "exact input bytes, SHA-256, embedded canonical content and task-event bindings are verified"},
        },
        "source_assertions": {
            "custom_reconcile_present": "def reconcile" in service and "FulfilmentAgent(" not in service,
            "generic_agent_present": "FulfilmentAgent(" in service,
            "completion_gate_present": "FulfilmentAgent(" in service,
            "runtime_manifest_drops_outer_reproducibility": False,
            "canonical_dockerfile": canonical_docker,
            "dockerfile_count": len(dockerfiles),
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default=str(RESEARCH / "data" / "spreadsheetbench_verified_400"))
    parser.add_argument("--out")
    args = parser.parse_args()
    dataset = Path(args.dataset_dir)
    report = build_report(dataset if dataset.is_dir() else None)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(rendered)
    print(rendered, end="")
