"""Fail-closed orchestration for a preregistered four-arm experiment.

Fulfilment containers see initial artifacts and public metadata. Reference artifacts
are exposed only to fresh scorer containers after all four arms have terminated.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Sequence

from experiment.manifests import ARMS, file_hash, validate_manifest_set
from protocol.offline_report import analyze, join_results, load_internal, load_official, markdown_table


RESEARCH = Path(__file__).resolve().parents[1]


def _load_manifests(directory: Path) -> dict[str, dict[str, Any]]:
    values = {arm: json.loads((directory / f"{arm}.json").read_text()) for arm in ARMS}
    validate_manifest_set(values, selection_path=None)
    return values


def _tree_hash(root: Path, *, exclude: frozenset[str] = frozenset()) -> str:
    digest = sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in exclude):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def preflight(manifest_dir: Path, run_root: Path, dataset_dir: Path, image: str,
              *, require_runtime: bool = True) -> dict[str, Any]:
    manifests = _load_manifests(manifest_dir)
    pins = {value["reproducibility"]["container_digest"] for value in manifests.values()}
    if len(pins) != 1 or not image.endswith("@" + next(iter(pins))):
        raise ValueError("image reference must end with the exact manifest container digest")
    metadata = dataset_dir / "dataset.json"
    if not metadata.is_file():
        raise FileNotFoundError("dataset.json missing")
    expected_dataset = manifests["A"]["reproducibility"]["dataset_metadata_sha256"]
    if file_hash(metadata) != expected_dataset:
        raise ValueError("dataset metadata differs from registered manifest pin")
    for arm in ARMS:
        output = run_root / arm
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError(f"run directory must exist and be empty: {output}")
    environment = {
        "docker": shutil.which("docker"),
        "openrouter_api_key": bool(os.environ.get("OPENROUTER_API_KEY")),
    }
    if require_runtime and (not environment["docker"] or not environment["openrouter_api_key"]):
        missing = [key for key, value in environment.items() if not value]
        raise RuntimeError("registered runtime prerequisites missing: " + ", ".join(missing))
    return {"status": "pass", "arms": list(ARMS), "dataset_sha256": expected_dataset,
            "container_digest": next(iter(pins)), "environment": environment}


def fulfilment_command(image: str, manifest_dir: Path, dataset_dir: Path,
                       output_dir: Path, arm: str) -> list[str]:
    identity = f"{os.getuid()}:{os.getgid()}"
    return ["docker", "run", "--rm", "--user", identity,
            "--tmpfs", "/tmp:rw,exec,nosuid,size=1g", "-e", "HOME=/tmp/run-home",
            "-e", "OPENROUTER_API_KEY",
            "-v", f"{dataset_dir.resolve()}:/data/dataset:ro",
            "-v", f"{manifest_dir.resolve()}:/manifests:ro",
            "-v", f"{output_dir.resolve()}:/out", image,
            "run", "--manifest", f"/manifests/{arm}.json", "--out-dir", "/out"]


def scorer_command(image: str, dataset_dir: Path, output_dir: Path) -> list[str]:
    identity = f"{os.getuid()}:{os.getgid()}"
    return ["docker", "run", "--rm", "--user", identity,
            "--tmpfs", "/tmp:rw,exec,nosuid,size=1g", "-e", "HOME=/tmp/run-home",
            "--entrypoint", "python",
            "-v", f"{dataset_dir.resolve()}:/data/dataset:ro",
            "-v", f"{output_dir.resolve()}:/run", image, "-m", "evaluate",
            "--predictions", "/run/predictions.jsonl", "--dataset-dir", "/data/dataset",
            "--out", "/run/official_results.json", "--quiet"]


def _run(command: list[str], log_path: Path) -> None:
    with log_path.open("wb") as stream:
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}); see {log_path}")


def _verify_arm_termination(output: Path, expected_tasks: set[str]) -> None:
    predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
    observed = {str(item["id"]) for item in predictions}
    task_results = {path.stem for path in (output / "task_results").glob("*.json")}
    if observed != expected_tasks or task_results != expected_tasks:
        raise RuntimeError(f"arm output is incomplete: {output}")
    if len(predictions) != len(observed):
        raise RuntimeError(f"arm output contains duplicate predictions: {output}")


def _stage_blind_dataset(source: Path, target: Path, selected_ids: set[str]) -> None:
    """Materialize only public metadata, prompts, and initial artifacts."""
    if target.exists():
        raise FileExistsError(f"refusing to reuse blind dataset path: {target}")
    records = json.loads((source / "dataset.json").read_text())
    by_id = {str(record["id"]): record for record in records}
    if not selected_ids <= by_id.keys():
        raise ValueError("selection contains task absent from dataset")
    target.mkdir(parents=True)
    shutil.copy2(source / "dataset.json", target / "dataset.json")
    for task_id in sorted(selected_ids):
        record = by_id[task_id]
        source_folder = source / record["spreadsheet_path"]
        target_folder = target / record["spreadsheet_path"]
        target_folder.mkdir(parents=True)
        initial = sorted(source_folder.glob("*init*.xlsx"))
        if len(initial) != 1:
            raise FileNotFoundError(f"task {task_id} must have exactly one initial artifact")
        shutil.copy2(initial[0], target_folder / initial[0].name)
        prompt = source_folder / "prompt.txt"
        if prompt.is_file():
            shutil.copy2(prompt, target_folder / prompt.name)
    forbidden = [path for path in target.rglob("*") if path.is_file() and "golden" in path.name.lower()]
    if forbidden:
        raise RuntimeError("blind dataset staging included a reference artifact")


def _write_analysis(run_root: Path, selection: dict[str, Any]) -> dict[str, Any]:
    metadata = {str(task["id"]): task for task in selection["tasks"]}
    joined = {
        arm: join_results(load_internal(run_root / arm),
                          load_official(run_root / arm / "official_results.json"), metadata)
        for arm in ARMS
    }
    report = analyze(joined)
    (run_root / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (run_root / "arm_table.md").write_text(markdown_table(report) + "\n")
    return report


def _write_ledger(run_root: Path, manifest_dir: Path, manifests: dict[str, dict[str, Any]],
                  report: dict[str, Any]) -> None:
    run = manifests["A"]["run_config"]
    protocol = json.loads((RESEARCH / "protocol" / "preregistered_experiment.json").read_text())
    combined_manifest = sha256(b"".join((manifest_dir / f"{arm}.json").read_bytes() for arm in ARMS)).hexdigest()
    comparison = report["paired_comparisons"]["D_minus_A"]
    ledger = {
        "experiment_id": run["experiment_id"], "protocol_version": protocol["protocol_version"],
        "hypothesis": protocol["research_hypothesis"],
        "change": "A through D add declarative state, executable evals, then iterative reconciliation",
        "control": "A", "treatment": "D",
        "task_set": {"manifest_sha256": manifests["A"]["reproducibility"]["selection_sha256"],
                     "task_count": len(manifests["A"]["task_selection"]["tasks"])},
        "model": {"name": run["model"], "version": run["model_version"],
                  "temperature": run["temperature"]},
        "budgets": {"tokens": run["max_tokens"], "actions": run["max_actions"],
                    "wall_clock_seconds": run["max_wall_time_ms"] // 1000},
        "deviations": [{"description": item} for item in run.get("deviations", [])],
        "results": report["metrics"], "confidence_intervals": comparison,
        "failure_distribution": report["failure_distribution"],
        "interpretation": "Provisional automated report generated without changing preregistered decision thresholds; final validity and cost-defensibility review remains required.",
        "decision": "inconclusive", "next_experiment": "Apply preregistered success criteria and complete evidence-linked failure review.",
        "provenance": {"git_commit": run["scorer_commit"], "run_manifest_sha256": combined_manifest,
                       "evidence_root_sha256": _tree_hash(run_root, exclude=frozenset({"ledger.json"})),
                       "scorer_commit": run["scorer_commit"],
                       "created_at": datetime.now(timezone.utc).isoformat()},
    }
    (run_root / "ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")


def execute(manifest_dir: Path, run_root: Path, dataset_dir: Path, image: str) -> None:
    manifests = _load_manifests(manifest_dir)
    preflight(manifest_dir, run_root, dataset_dir, image)
    selection = manifests["A"]["task_selection"]
    expected = {str(item["id"]) for item in selection["tasks"]}
    blind_dataset = run_root / "blind_fulfilment_input"
    _stage_blind_dataset(dataset_dir, blind_dataset, expected)
    # Goldens are inaccessible to all fulfilment processes by protocol and chronology:
    # scoring does not begin until each arm has a complete terminal output set.
    for arm in ARMS:
        _run(fulfilment_command(image, manifest_dir, blind_dataset, run_root / arm, arm),
             run_root / arm / "container.log")
        _verify_arm_termination(run_root / arm, expected)
    for arm in ARMS:
        _run(scorer_command(image, dataset_dir, run_root / arm), run_root / arm / "scorer.log")
    report = _write_analysis(run_root, selection)
    _write_ledger(run_root, manifest_dir, manifests, report)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run, score, and analyze a pinned four-arm experiment")
    parser.add_argument("--manifest-dir", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--image", required=True, help="image@sha256:<digest> matching every manifest")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    paths = (Path(args.manifest_dir), Path(args.run_root), Path(args.dataset_dir))
    if args.preflight_only:
        print(json.dumps(preflight(*paths, args.image, require_runtime=False), indent=2, sort_keys=True))
    else:
        execute(*paths, args.image)


if __name__ == "__main__":
    main()
