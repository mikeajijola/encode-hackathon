"""Deterministic, golden-blind task selection manifests."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
from typing import Any


FORBIDDEN_KEY_FRAGMENTS = ("golden", "expected_answer", "answer_value")


def canonical_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_no_leakage(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise ValueError(f"forbidden fulfilment-time field at {path}.{key}")
            validate_no_leakage(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_no_leakage(item, f"{path}[{index}]")


def safe_task(task: dict, dataset_root: Path | None = None) -> dict:
    """Project public dataset metadata without resolving or reading any golden file."""
    relative_folder = Path(task["spreadsheet_path"])
    init_path = relative_folder / f"1_{task['id']}_init.xlsx"
    if dataset_root is not None:
        candidates = sorted((dataset_root / relative_folder).glob("*init*.xlsx"))
        if len(candidates) != 1:
            raise ValueError(f"expected exactly one initial artifact for task {task['id']}")
        init_path = candidates[0].relative_to(dataset_root)
    return {
        "id": str(task["id"]),
        "instruction": task["instruction"],
        "instruction_type": task["instruction_type"],
        "spreadsheet_path": task["spreadsheet_path"],
        "init_path": init_path.as_posix(),
        "answer_position": task.get("answer_position"),
        "answer_sheet": task.get("answer_sheet"),
        "data_position": task.get("data_position"),
    }


def select_stratified(tasks: list[dict], counts: dict[str, int], seed: int,
                      dataset_root: Path | None = None) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    selected_ids: set[str] = set()
    for stratum, count in sorted(counts.items()):
        members = sorted((task for task in tasks if task["instruction_type"] == stratum), key=lambda task: str(task["id"]))
        if count < 0 or count > len(members):
            raise ValueError(f"invalid count {count} for {stratum!r} with {len(members)} tasks")
        selected_ids.update(str(task["id"]) for task in rng.sample(members, count))
    selected = [safe_task(task, dataset_root) for task in tasks if str(task["id"]) in selected_ids]
    heldout = [safe_task(task, dataset_root) for task in tasks if str(task["id"]) not in selected_ids]
    return sorted(selected, key=lambda task: task["id"]), sorted(heldout, key=lambda task: task["id"])


def manifest(name: str, tasks: list[dict], seed: int, source_sha256: str) -> dict:
    body = {"schema_version": "1.0.0", "name": name, "seed": seed,
            "source_metadata_sha256": source_sha256, "reference_answer_access": "prohibited",
            "tasks": tasks}
    validate_no_leakage(body)
    return {**body, "selection_sha256": canonical_hash(body)}


def validate_manifest(value: dict) -> None:
    validate_no_leakage(value)
    digest = value.get("selection_sha256")
    body = {key: item for key, item in value.items() if key != "selection_sha256"}
    if digest != canonical_hash(body):
        raise ValueError("selection manifest hash mismatch")
    ids = [task["id"] for task in value["tasks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-json", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--heldout-out")
    parser.add_argument("--all-out")
    parser.add_argument("--cell", type=int, default=10)
    parser.add_argument("--sheet", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()
    source = Path(args.dataset_json).read_bytes()
    tasks = json.loads(source)
    counts = {"Cell-Level Manipulation": args.cell, "Sheet-Level Manipulation": args.sheet}
    development, heldout = select_stratified(tasks, counts, args.seed, Path(args.dataset_json).parent)
    Path(args.out).write_text(json.dumps(manifest("development", development, args.seed, sha256(source).hexdigest()), indent=2) + "\n")
    if args.heldout_out:
        Path(args.heldout_out).write_text(json.dumps(manifest("heldout", heldout, args.seed, sha256(source).hexdigest()), indent=2) + "\n")
    if args.all_out:
        all_tasks = sorted((safe_task(task, Path(args.dataset_json).parent) for task in tasks),
                           key=lambda task: task["id"])
        Path(args.all_out).write_text(json.dumps(manifest("all-400", all_tasks, args.seed,
                                                         sha256(source).hexdigest()), indent=2) + "\n")


if __name__ == "__main__":
    main()
