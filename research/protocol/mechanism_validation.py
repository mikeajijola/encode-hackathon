"""Register and summarize the D-only unbounded-token mechanism validation.

The official scorer is invoked separately, after fulfilment has terminated. This
module never reads reference workbooks or golden cell values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_EMERGENCY_TOKENS = 250_000


def revise_d_manifest(base: dict[str, Any], experiment_id: str,
                      emergency_tokens: int = DEFAULT_EMERGENCY_TOKENS) -> dict[str, Any]:
    value = json.loads(json.dumps(base))
    run = value.get("run_config") or {}
    selection = value.get("task_selection") or {}
    if run.get("arm") != "D":
        raise ValueError("mechanism validation requires an Arm D manifest")
    if selection.get("name") != "development" or len(selection.get("tasks", ())) != 20:
        raise ValueError("mechanism validation requires the frozen 20-task development selection")
    if run.get("max_tokens") != 16_000:
        raise ValueError("base manifest must preserve the prior 16,000-token fixed policy")
    if emergency_tokens < 100_000:
        raise ValueError("operational emergency ceiling must be at least 100,000 tokens")
    run.update({
        "experiment_id": experiment_id,
        "token_policy": "measured_cost",
        "operational_emergency_token_ceiling": emergency_tokens,
    })
    deviation = (
        "Arm D research token budget removed for mechanism validation; token usage is an outcome. "
        f"A separate {emergency_tokens:,}-token operational emergency ceiling prevents runaway execution."
    )
    run["deviations"] = [*run.get("deviations", ()), deviation]
    value.setdefault("reproducibility", {})["deviations"] = [
        *value.get("reproducibility", {}).get("deviations", ()), deviation,
    ]
    value["experiment_revision"] = {
        "kind": "d_only_mechanism_validation",
        "supersedes": None,
        "preserves_prior_result": "fixed-budget development experiment — 16,000 tokens/task",
        "research_token_budget_per_task": None,
        "token_usage_treatment": "measured_outcome",
        "operational_emergency_token_ceiling": emergency_tokens,
        "heldout_access": "forbidden",
    }
    return value


def write_revision(base_path: Path, output_path: Path, experiment_id: str,
                   emergency_tokens: int = DEFAULT_EMERGENCY_TOKENS) -> None:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite experiment revision: {output_path}")
    base = json.loads(base_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(revise_d_manifest(base, experiment_id, emergency_tokens),
                                      indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_checkpoint_predictions(run_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite checkpoint predictions: {output_dir}")
    output_dir.mkdir(parents=True)
    by_mutation: dict[int, list[dict[str, Any]]] = {}
    for path in sorted((run_dir / "task_results").glob("*.json")):
        result = json.loads(path.read_text())
        for number, output in enumerate(result.get("mutation_outputs", ()), 1):
            by_mutation.setdefault(number, []).append({
                "id": str(result["id"]), "output": output, "status": "offline_checkpoint",
            })
    for number, rows in by_mutation.items():
        path = output_dir / f"mutation-{number:02d}.jsonl"
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _checkpoint_scores(directory: Path | None) -> dict[tuple[str, int], bool]:
    scores: dict[tuple[str, int], bool] = {}
    if directory is None or not directory.is_dir():
        return scores
    for path in sorted(directory.glob("mutation-*.official.json")):
        number = int(path.name.split("-")[1].split(".")[0])
        payload = json.loads(path.read_text())
        for item in payload.get("items", ()):
            scores[(str(item["id"]), number)] = bool(item.get("pass"))
    return scores


def summarize(run_dir: Path, official_path: Path,
              checkpoint_results_dir: Path | None = None) -> dict[str, Any]:
    official_payload = json.loads(official_path.read_text())
    official = {str(item["id"]): item for item in official_payload["items"]}
    checkpoint_scores = _checkpoint_scores(checkpoint_results_dir)
    tasks = []
    for result_path in sorted((run_dir / "task_results").glob("*.json")):
        result = json.loads(result_path.read_text())
        task_id = str(result["id"])
        events = _events(run_dir / "events" / f"{task_id}.jsonl")
        traces = _events(run_dir / "traces" / f"{task_id}.jsonl")
        phase = next((event["payload"] for event in events
                      if event["event_type"] == "phase_usage" and
                      event["payload"].get("phase") == "contract_compilation"), None)
        contract_tokens = 0 if phase is None else (
            phase["after"]["tokens"] - phase["before"]["tokens"])
        first_planning_index = next((index for index, trace in enumerate(traces)
                                     if trace.get("purpose") == "action_generation"), len(traces))
        initial_evaluation_tokens = sum(
            int(trace.get("input_tokens") or 0) + int(trace.get("output_tokens") or 0)
            for trace in traces[:first_planning_index]
            if trace.get("purpose") == "independent_evaluation"
        )
        cycles = []
        for event in events:
            if event["event_type"] != "reconciliation_cycle":
                continue
            payload = event["payload"]
            usage = payload.get("usage", {})
            cycles.append({
                "cycle_number": len(cycles) + 1,
                "observation_tokens": 0,
                "evaluation_tokens": 0,
                "discrepancy_tokens": 0,
                "planning_tokens": 0,
                "action_tokens": 0,
                "total_cycle_tokens": 0,
                "action_count": 1,
                "failed_evals_before": payload.get("failed_evals_before", []),
                "failed_evals_after": payload.get("failed_evals_after", []),
                "discrepancy_count_before": len(payload.get("discrepancy_ids_before", [])),
                "discrepancy_count_after": len(payload.get("discrepancy_ids_after", [])),
                "artifact_hash_before": payload.get("artifact_hash_before"),
                "artifact_hash_after": payload.get("artifact_hash_after"),
                "genuine_cycle": bool(payload.get("genuine_cycle")),
                "usage_at_cycle_end": usage,
            })
        # Attribute model tokens between successive cycle-end snapshots by purpose.
        trace_index = 0
        prior_tokens = contract_tokens
        for cycle in cycles:
            end_tokens = int(cycle["usage_at_cycle_end"].get("tokens", prior_tokens))
            cycle["total_cycle_tokens"] = max(0, end_tokens - prior_tokens)
            while trace_index < len(traces):
                trace = traces[trace_index]
                amount = int(trace.get("input_tokens") or 0) + int(trace.get("output_tokens") or 0)
                purpose = trace.get("purpose")
                key = "evaluation_tokens" if purpose == "independent_evaluation" else (
                    "planning_tokens" if purpose == "action_generation" else None)
                if key:
                    cycle[key] += amount
                trace_index += 1
                if sum(int(t.get("input_tokens") or 0) + int(t.get("output_tokens") or 0)
                       for t in traces[:trace_index]) >= end_tokens:
                    break
            prior_tokens = end_tokens
            cycle.pop("usage_at_cycle_end", None)
        item = official.get(task_id, {})
        checkpoint_events = [event["payload"] for event in events
                             if event["event_type"] == "mutation_checkpoint"]
        first_correct = next((event for event in checkpoint_events
                              if checkpoint_scores.get((task_id, int(event["mutation_number"])))), None)
        first_attempt_pass = checkpoint_scores.get((task_id, 1))
        no_progress_class = None
        status_lower = str(result["status"]).lower()
        if "no_progress" in status_lower:
            no_progress_class = "repeated_same_transition"
        elif any(not cycle["genuine_cycle"] for cycle in cycles):
            no_progress_class = "action_has_no_effect"
        elif "capability_missing" in status_lower:
            no_progress_class = "missing_capability"
        elif "contract_ambiguous" in status_lower:
            no_progress_class = "contract_too_ambiguous"
        elif "evaluation_uncertain" in status_lower:
            no_progress_class = "eval_not_actionable"
        task_row = {
            "task_id": task_id,
            "contract_compilation_tokens": contract_tokens,
            "initial_observation_tokens": 0,
            "initial_evaluation_tokens": initial_evaluation_tokens,
            "reconciliation_cycles": cycles,
            "total_tokens_to_termination": result["usage"]["tokens"],
            "total_actions_to_termination": result["usage"]["actions"],
            "total_iterations_to_termination": (result.get("terminal_eval") or {}).get("details", {}).get("iteration", 0),
            "wall_time_to_termination_ms": result["usage"]["latency_ms"],
            "estimated_cost_to_termination": result["usage"]["cost"],
            "termination_reason": result["status"],
            "internal_completion": result["internal_status"],
            "official_benchmark_result": "PASS" if item.get("pass") else "FAIL",
            "official_cell_accuracy": (item.get("correct", 0) / item.get("cells", 1)) if item else 0,
            "tokens_to_first_correct_state": (first_correct or {}).get("usage", {}).get("tokens"),
            "actions_to_first_correct_state": (first_correct or {}).get("usage", {}).get("actions"),
            "iterations_to_first_correct_state": (first_correct or {}).get("mutation_number"),
            "first_mutation_official_pass": first_attempt_pass,
            "recovered": first_attempt_pass is False and bool(item.get("pass")) and
                         len(result.get("mutation_outputs", ())) >= 2,
            "no_progress_failure_mode": no_progress_class,
            "no_progress_token_cost": result["usage"]["tokens"] if no_progress_class else 0,
        }
        tasks.append(task_row)
    genuine_counts = [sum(1 for cycle in task["reconciliation_cycles"] if cycle["genuine_cycle"])
                      for task in tasks]
    fulfilled = [task for task in tasks if task["internal_completion"] == "FULFILLED"]
    official_passes = [task for task in tasks if task["official_benchmark_result"] == "PASS"]
    false_fulfilled = [task for task in fulfilled if task["official_benchmark_result"] == "FAIL"]
    false_unfulfilled = [task for task in tasks if task["internal_completion"] == "UNFULFILLED"
                         and task["official_benchmark_result"] == "PASS"]
    genuine_cycles = [cycle for task in tasks for cycle in task["reconciliation_cycles"] if cycle["genuine_cycle"]]
    recoverable = [task for task in tasks if task["first_mutation_official_pass"] is False]
    recoveries = [task for task in tasks if task["recovered"]]
    ceiling = [task for task in tasks if "operational_emergency" in task["termination_reason"]]
    return {
        "experiment_kind": "d_only_uncapped_token_mechanism_validation",
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "official_pass_rate": len(official_passes) / len(tasks) if tasks else 0,
            "false_fulfilment_rate": len(false_fulfilled) / len(fulfilled) if fulfilled else 0,
            "false_unfulfilment_rate": len(false_unfulfilled) / (len(tasks) - len(fulfilled)) if len(tasks) > len(fulfilled) else 0,
            "tasks_completing_ge_1_cycle": sum(value >= 1 for value in genuine_counts),
            "tasks_completing_ge_2_cycles": sum(value >= 2 for value in genuine_counts),
            "tasks_completing_ge_3_cycles": sum(value >= 3 for value in genuine_counts),
            "median_cycles_per_task": median(genuine_counts) if genuine_counts else 0,
            "median_tokens_per_cycle": median([cycle["total_cycle_tokens"] for cycle in genuine_cycles]) if genuine_cycles else 0,
            "median_actions_per_cycle": median([cycle["action_count"] for cycle in genuine_cycles]) if genuine_cycles else 0,
            "recoverable_first_attempt_failures": len(recoverable),
            "successful_recoveries": len(recoveries),
            "recovery_yield": len(recoveries) / len(recoverable) if recoverable else 0,
            "operational_emergency_ceiling_terminations": len(ceiling),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--base", required=True, type=Path)
    register.add_argument("--out", required=True, type=Path)
    register.add_argument("--experiment-id", required=True)
    register.add_argument("--emergency-tokens", type=int, default=DEFAULT_EMERGENCY_TOKENS)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--run-dir", required=True, type=Path)
    analyze.add_argument("--official", required=True, type=Path)
    analyze.add_argument("--checkpoint-results", type=Path)
    analyze.add_argument("--out", required=True, type=Path)
    checkpoints = sub.add_parser("checkpoints")
    checkpoints.add_argument("--run-dir", required=True, type=Path)
    checkpoints.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "register":
        write_revision(args.base, args.out, args.experiment_id, args.emergency_tokens)
    elif args.command == "checkpoints":
        write_checkpoint_predictions(args.run_dir, args.out_dir)
    else:
        args.out.write_text(json.dumps(summarize(args.run_dir, args.official, args.checkpoint_results), indent=2,
                                               sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
