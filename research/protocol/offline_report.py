"""Offline-only join and report generation after official scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .analysis import arm_metrics, breakdown, failure_distribution, mcnemar_exact, paired_bootstrap_ci


ARMS = ("A", "B", "C", "D")
BREAKDOWN_FIELDS = ("instruction_type", "task_family", "mutation_count", "formula_vs_value",
                    "complexity", "initial_observation_size_bucket", "reconciliation_iteration_count")


def load_internal(directory: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted((directory / "task_results").glob("*.json"))]


def load_official(path: Path) -> list[dict]:
    value = json.loads(path.read_text())
    return value["items"] if isinstance(value, dict) else value


def join_results(internal: list[dict], official: list[dict], metadata: dict[str, dict] | None = None) -> list[dict]:
    left = {str(row["id"]): row for row in internal}
    right = {str(row["id"]): row for row in official}
    if len(left) != len(internal) or len(right) != len(official):
        raise ValueError("duplicate task ids in result input")
    if left.keys() != right.keys() or not left:
        raise ValueError("internal and official results require identical non-empty task ids")
    rows = []
    for task_id in sorted(left):
        internal_row, official_row = left[task_id], right[task_id]
        terminal = internal_row.get("terminal_eval")
        declared = internal_row.get("internal_status")
        if declared is None:
            declared = "FULFILLED" if terminal and terminal.get("passed") is True else "UNFULFILLED"
        if declared not in {"FULFILLED", "FULFILLED_UNVERIFIED", "UNFULFILLED"}:
            raise ValueError(f"unknown internal_status for task {task_id}: {declared!r}")
        internal_artifact_valid = internal_row.get("artifact_valid")
        artifact_valid = (official_row.get("status") == "graded" if internal_artifact_valid is None
                          else bool(internal_artifact_valid))
        row = {
            "task_id": task_id, "internal_status": declared,
            "official_pass": bool(official_row.get("pass", False)),
            "correct_cells": int(official_row.get("correct", 0)),
            "total_cells": int(official_row.get("cells", 0)),
            "artifact_valid": artifact_valid,
            "constraint_violation": bool(internal_row.get("constraint_violation", False)),
            "first_mutation_pass": internal_row.get("first_mutation_pass"),
            "actions": internal_row.get("usage", {}).get("actions", 0),
            "tokens": internal_row.get("usage", {}).get("tokens", 0),
            "latency_ms": internal_row.get("usage", {}).get("latency_ms", 0),
            "cost_usd": internal_row.get("usage", {}).get("cost", 0),
            "failure_classes": internal_row.get("failure_classes", []),
        }
        classes = set(row["failure_classes"])
        terminal = internal_row.get("terminal_eval")
        if terminal and terminal.get("passed") is True and not row["official_pass"]:
            classes.add("evaluation_false_positive")
        if terminal and terminal.get("passed") is False and row["official_pass"]:
            classes.add("evaluation_false_negative")
        row["failure_classes"] = sorted(classes)
        for field in BREAKDOWN_FIELDS:
            if field in internal_row:
                row[field] = internal_row[field]
        row.update((metadata or {}).get(task_id, {}))
        rows.append(row)
    return rows


def analyze(arms: dict[str, list[dict]], *, samples: int = 10_000, seed: int = 20260905) -> dict:
    if set(arms) != set(ARMS):
        raise ValueError("analysis requires exactly arms A, B, C, D")
    metrics = {arm: arm_metrics(arms[arm]) for arm in ARMS}
    paired = {}
    for control, treatment in (("A", "B"), ("B", "C"), ("C", "D"), ("A", "D")):
        paired[f"{treatment}_minus_{control}"] = {
            "bootstrap": paired_bootstrap_ci(arms[control], arms[treatment], samples=samples, seed=seed),
            "mcnemar": mcnemar_exact(arms[control], arms[treatment]),
        }
    return {
        "metrics": metrics, "paired_comparisons": paired,
        "breakdowns": {arm: {field: breakdown(arms[arm], field) for field in BREAKDOWN_FIELDS} for arm in ARMS},
        "failure_distribution": {arm: failure_distribution(arms[arm]) for arm in ARMS},
        "failure_examples": {arm: failure_examples(arms[arm]) for arm in ARMS},
        "overhead_vs_A": {arm: overhead(metrics["A"], metrics[arm]) for arm in ("B", "C", "D")},
        "resource_distributions": {arm: resource_distribution(arms[arm]) for arm in ARMS},
        "multimodal": {"status": "not_applicable", "rationale": "Analysis records have no rendered semantics; adapter evidence is analyzed by reference."},
    }


def overhead(control: dict, treatment: dict) -> dict:
    return {key: treatment[key] - control[key] for key in
            ("actions_mean", "tokens_mean", "latency_ms_mean", "cost_usd_mean")}


def resource_distribution(rows: list[dict]) -> dict:
    def stats(field: str) -> dict:
        values = sorted(float(row.get(field, 0)) for row in rows)
        def percentile(fraction: float) -> float:
            return values[min(len(values) - 1, int((len(values) - 1) * fraction))]
        return {"mean": sum(values) / len(values), "median": percentile(.5), "p95": percentile(.95),
                "min": values[0], "max": values[-1]}
    return {field: stats(field) for field in ("actions", "tokens", "latency_ms", "cost_usd")}


def failure_examples(rows: list[dict], limit: int = 3) -> dict[str, list[str]]:
    examples: dict[str, list[str]] = {}
    for row in rows:
        for label in row.get("failure_classes", []):
            examples.setdefault(label, [])
            if len(examples[label]) < limit:
                examples[label].append(row["task_id"])
    return dict(sorted(examples.items()))


def markdown_table(report: dict) -> str:
    headers = ("Arm", "Pass rate", "Cell accuracy", "FFR", "Recovery yield", "Valid artifacts", "Actions", "Tokens", "Latency", "Cost")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    keys = ("pass_rate", "cell_accuracy", "false_fulfilment_rate", "recovery_yield", "artifact_validity_rate",
            "actions_mean", "tokens_mean", "latency_ms_mean", "cost_usd_mean")
    for arm in ARMS:
        values = [arm] + ["N/A" if report["metrics"][arm][key] is None else f"{report['metrics'][arm][key]:.4f}" for key in keys]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, help="JSON mapping arm to {internal_dir, official_results}")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", required=True)
    parser.add_argument("--selection", help="golden-blind selection manifest providing task metadata")
    args = parser.parse_args()
    spec = json.loads(Path(args.inputs).read_text())
    metadata = None
    if args.selection:
        selected = json.loads(Path(args.selection).read_text())
        metadata = {str(task["id"]): task for task in selected["tasks"]}
    joined = {arm: join_results(load_internal(Path(spec[arm]["internal_dir"])),
                                load_official(Path(spec[arm]["official_results"])), metadata) for arm in ARMS}
    report = analyze(joined)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    Path(args.markdown_out).write_text(markdown_table(report) + "\n")


if __name__ == "__main__":
    main()
