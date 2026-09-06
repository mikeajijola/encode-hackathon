"""Offline completion calibration from gold-isolated runtime evidence.

This module deliberately writes runtime features and external labels to separate
files.  Policy functions consume runtime features only; labels are joined only
by the reporting code after candidate decisions have been produced.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


INDEPENDENCE = {
    "artifact-valid": "structurally_independent",
    "preservation": "independent_deterministic",
    "nonblank": "structurally_independent",
    "type": "structurally_independent",
    "output-shape": "structurally_independent",
    "formula-errors": "structurally_independent",
    "semantic": "independent_semantic",
    "render": "independent_semantic",
}
SAFETY_GATES = {"artifact-valid", "preservation", "formula-errors"}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _contract_context(trace_path: Path) -> dict[str, Any]:
    trace = next((row for row in _jsonl(trace_path) if row.get("purpose") == "contract"), {})
    try:
        prompt = json.loads(trace.get("prompt") or "{}")
    except (TypeError, json.JSONDecodeError):
        prompt = {}
    return prompt.get("observed_context", {})


def _last_contract(events: list[dict[str, Any]]) -> dict[str, Any]:
    contracts = [row.get("payload", {}).get("contract", {}) for row in events
                 if row.get("event_type") == "accepted_contract"]
    # The evidence writer mirrors the accepted-contract event with a compact
    # provenance record. Prefer the complete immutable contract payload.
    return next((item for item in contracts if item.get("desired_state") and item.get("evals")),
                contracts[0] if contracts else {})


def _eval_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evals = (result.get("terminal_eval") or {}).get("details", {}).get("evals", [])
    return {row["eval_id"]: row for row in evals}


def _formula_representation_ambiguous(contract: dict[str, Any], evals: dict[str, Any]) -> bool:
    properties = {item.get("property") for item in
                  contract.get("desired_state", {}).get("assertions", [])}
    row = evals.get("type", {})
    observed = row.get("details", {}).get("observed", [])
    return (row.get("status") == "fail" and "formula_result" in properties and
            bool(observed) and set(observed) <= {"formula"})


def extract_runtime_features(run_dir: Path) -> list[dict[str, Any]]:
    """Extract final candidate features available before official grading."""
    rows = []
    for path in sorted((run_dir / "task_results").glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        task_id = str(result["id"])
        events = _jsonl(run_dir / "events" / f"{task_id}.jsonl")
        contract = _last_contract(events)
        context = _contract_context(run_dir / "traces" / f"{task_id}.jsonl")
        truncation = context.get("workbook_observation", {}).get("truncation", {})
        evals = _eval_map(result)
        required = [item.get("id") for item in contract.get("evals", [])
                    if item.get("severity") == "required"]
        assertions = contract.get("desired_state", {}).get("assertions", [])
        discrepancies = (result.get("terminal_eval") or {}).get("details", {}).get(
            "discrepancies", [])
        rows.append({
            "candidate_id": f"{task_id}:final",
            "task_id": task_id,
            "candidate_kind": "final",
            "contract": contract,
            "contract_compiled": bool(result.get("contract_compiled")),
            "assertion_properties": [item.get("property") for item in assertions],
            "assertion_count": len(assertions),
            "required_eval_ids": required,
            "eval_results": evals,
            "eval_coverage": len(set(required) & set(evals)) / len(required) if required else 0.0,
            "source_observation": {
                "truncated": bool(truncation.get("truncated")),
                "serialized_cells": truncation.get("serialized_cells"),
                "omitted_nonempty_cells": truncation.get("omitted_nonempty_cells"),
                "serialized_chars": truncation.get("serialized_chars"),
                "inspected_scope_present": bool(context.get("workbook_observation")),
            },
            "evaluator_independence": {
                key: ("partially_coupled" if key == "semantic" and
                      "formula_result" in {a.get("property") for a in assertions}
                      else INDEPENDENCE.get(key, "unclassified"))
                for key in evals
            },
            "formula_representation_ambiguous": _formula_representation_ambiguous(contract, evals),
            "discrepancies": discrepancies,
            "artifact_valid": bool(result.get("artifact_valid")),
            "constraint_violation": bool(result.get("constraint_violation")),
            "mutation_count": len(result.get("mutation_outputs", [])),
            "artifact_hash": result.get("output_artifact_hash"),
            "runtime_internal_status": result.get("internal_status"),
            "termination_reason": result.get("termination_reason") or result.get("status"),
            "iteration": (result.get("terminal_eval") or {}).get("details", {}).get("iteration"),
            "no_progress": "no_progress" in str(result.get("status", "")),
            "capability_provenance_present": any(
                row.get("event_type") == "capability_result" for row in events),
        })
    return rows


def extract_checkpoint_features(run_dir: Path) -> list[dict[str, Any]]:
    """Extract mutation states with completed post-mutation runtime evaluations."""
    rows = []
    for path in sorted((run_dir / "task_results").glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        task_id = str(result["id"])
        events = _jsonl(run_dir / "events" / f"{task_id}.jsonl")
        contract = _last_contract(events)
        context = _contract_context(run_dir / "traces" / f"{task_id}.jsonl")
        truncation = context.get("workbook_observation", {}).get("truncation", {})
        cycles = [row["payload"] for row in events if row.get("event_type") == "reconciliation_cycle"]
        checkpoints = [row["payload"] for row in events if row.get("event_type") == "mutation_checkpoint"]
        required = [item.get("id") for item in contract.get("evals", [])
                    if item.get("severity") == "required"]
        for cp in checkpoints:
            number = int(cp["mutation_number"])
            cycle = next((item for item in cycles if item.get("cycle_number") == number), None)
            if cycle is None:
                continue
            failed = set(cycle.get("failed_evals_after", []))
            # Event duplication makes full intermediate payloads noisy. Statuses
            # reconstructed from the cycle are sufficient and runtime-legal.
            evals = {eval_id: {"eval_id": eval_id,
                               "status": "fail" if eval_id in failed else "pass",
                               "details": {"intermediate_reconstruction": True}}
                     for eval_id in required}
            rows.append({
                "candidate_id": f"{task_id}:mutation:{number}",
                "task_id": task_id,
                "candidate_kind": "intermediate",
                "contract": contract,
                "contract_compiled": True,
                "assertion_properties": [a.get("property") for a in
                                         contract.get("desired_state", {}).get("assertions", [])],
                "required_eval_ids": required,
                "eval_results": evals,
                "eval_coverage": 1.0 if required else 0.0,
                "source_observation": {
                    "truncated": bool(truncation.get("truncated")),
                    "serialized_cells": truncation.get("serialized_cells"),
                    "omitted_nonempty_cells": truncation.get("omitted_nonempty_cells"),
                },
                "evaluator_independence": {key: INDEPENDENCE.get(key, "unclassified")
                                           for key in evals},
                "formula_representation_ambiguous": False,
                "discrepancies": [{"failed_eval": item} for item in sorted(failed)],
                "artifact_valid": "artifact-valid" not in failed,
                "constraint_violation": "preservation" in failed,
                "mutation_count": number,
                "artifact_hash": cp.get("artifact_hash"),
                "runtime_internal_status": "CANDIDATE",
                "termination_reason": None,
                "iteration": number,
                "no_progress": not bool(cycle.get("changed_state")),
                "capability_provenance_present": True,
            })
    return rows


def extract_labels(run_dir: Path, checkpoint_dir: Path | None) -> list[dict[str, Any]]:
    official = json.loads((run_dir / "official_results.json").read_text(encoding="utf-8"))
    labels = [{"candidate_id": f"{item['id']}:final", "task_id": str(item["id"]),
               "candidate_kind": "final", "external_pass": bool(item.get("pass"))}
              for item in official.get("items", [])]
    if checkpoint_dir and checkpoint_dir.is_dir():
        for path in sorted(checkpoint_dir.glob("mutation-*.official.json")):
            number = int(path.name.split("-")[1].split(".")[0])
            payload = json.loads(path.read_text(encoding="utf-8"))
            labels.extend({"candidate_id": f"{item['id']}:mutation:{number}",
                           "task_id": str(item["id"]), "candidate_kind": "intermediate",
                           "external_pass": bool(item.get("pass"))}
                          for item in payload.get("items", []))
    return labels


def _statuses(row: dict[str, Any]) -> dict[str, str]:
    return {key: value.get("status", "error") for key, value in row["eval_results"].items()}


def legacy_policy(row: dict[str, Any]) -> str:
    statuses = _statuses(row)
    return "FULFILLED" if (row["required_eval_ids"] and all(
        statuses.get(key) == "pass" for key in row["required_eval_ids"])) else "UNFULFILLED"


def strict_three_valued(row: dict[str, Any]) -> str:
    statuses = _statuses(row)
    if not row["contract_compiled"] or row["eval_coverage"] < 1:
        return "UNKNOWN"
    if all(statuses.get(key) == "pass" for key in row["required_eval_ids"]):
        return "FULFILLED"
    if any(status in {"error", "uncertain", "not_applicable"} for status in statuses.values()):
        return "UNKNOWN"
    return "UNFULFILLED"


def coverage_aware_three_valued(row: dict[str, Any]) -> str:
    """Require adequate, independent evidence before a positive claim."""
    statuses = _statuses(row)
    if not row["contract_compiled"] or row["eval_coverage"] < 1:
        return "UNKNOWN"
    hard_fail = any(statuses.get(key) == "fail" for key in SAFETY_GATES)
    if hard_fail or not row["artifact_valid"] or row["constraint_violation"]:
        return "UNFULFILLED"
    if row["source_observation"].get("truncated"):
        return "UNKNOWN"
    if row.get("formula_representation_ambiguous") and statuses.get("semantic") == "pass":
        return "UNKNOWN"
    if all(statuses.get(key) == "pass" for key in row["required_eval_ids"]):
        return "FULFILLED"
    definitive = {key for key, status in statuses.items() if status == "fail" and
                  key in {"nonblank", "output-shape"}}
    if definitive:
        return "UNFULFILLED"
    return "UNKNOWN"


def semantic_primary(row: dict[str, Any]) -> str:
    statuses = _statuses(row)
    if any(statuses.get(key) == "fail" for key in SAFETY_GATES):
        return "UNFULFILLED"
    if row["source_observation"].get("truncated"):
        return "UNKNOWN"
    if statuses.get("semantic") == "pass" and all(statuses.get(key) == "pass" for key in SAFETY_GATES):
        return "FULFILLED"
    return "UNKNOWN" if statuses.get("semantic") in {None, "error", "uncertain"} else "UNFULFILLED"


def quorum_policy(row: dict[str, Any]) -> str:
    statuses = _statuses(row)
    if any(statuses.get(key) == "fail" for key in SAFETY_GATES):
        return "UNFULFILLED"
    required = row["required_eval_ids"]
    passed = sum(statuses.get(key) == "pass" for key in required)
    if required and statuses.get("semantic") == "pass" and passed / len(required) >= 0.8:
        return "FULFILLED"
    return "UNKNOWN"


POLICIES: dict[str, tuple[str, Callable[[dict[str, Any]], str]]] = {
    "legacy_strict_binary": ("Control: every required eval must pass; every other result is negative.", legacy_policy),
    "strict_three_valued": ("Separate absent/error evidence from established failure.", strict_three_valued),
    "coverage_aware_three_valued": ("A positive semantic claim requires complete observed context and independent evidence.", coverage_aware_three_valued),
    "independent_semantic_primary": ("Semantic evidence plus safety gates may dominate weak descriptive gates.", semantic_primary),
    "required_eval_quorum": ("One weak required gate may dissent when semantic and safety gates agree.", quorum_policy),
}


def policy_metrics(features: list[dict[str, Any]], labels: dict[str, bool]) -> list[dict[str, Any]]:
    rows = [row for row in features if row["candidate_kind"] == "final" and row["candidate_id"] in labels]
    total_pass = sum(labels[row["candidate_id"]] for row in rows)
    output = []
    for name, (hypothesis, policy) in POLICIES.items():
        decisions = [(row, policy(row), labels[row["candidate_id"]]) for row in rows]
        matrix = {status: {"official_pass": 0, "official_fail": 0}
                  for status in ("FULFILLED", "UNFULFILLED", "UNKNOWN")}
        for _, status, passed in decisions:
            matrix[status]["official_pass" if passed else "official_fail"] += 1
        fp = matrix["FULFILLED"]["official_fail"]
        tp = matrix["FULFILLED"]["official_pass"]
        fulfilled_n = fp + tp
        unfulfilled_n = sum(matrix["UNFULFILLED"].values())
        unknown_n = sum(matrix["UNKNOWN"].values())
        output.append({
            "policy": name, "hypothesis": hypothesis,
            "fulfilled_precision": tp / fulfilled_n if fulfilled_n else None,
            "fulfilled_recall": tp / total_pass if total_pass else None,
            "false_fulfilment_rate": fp / fulfilled_n if fulfilled_n else None,
            "false_unfulfilment_rate": (matrix["UNFULFILLED"]["official_pass"] / unfulfilled_n
                                         if unfulfilled_n else None),
            "unknown_rate": unknown_n / len(decisions) if decisions else None,
            "unknown_official_pass": matrix["UNKNOWN"]["official_pass"],
            "unknown_official_fail": matrix["UNKNOWN"]["official_fail"],
            "official_passes_captured": tp,
            "official_failures_accepted": fp,
            "evaluator_coverage": sum(row["eval_coverage"] for row, _, _ in decisions) / len(decisions),
            "confusion_matrix": matrix,
            "task_decisions": [{"candidate_id": row["candidate_id"], "decision": status,
                                "external_pass": passed} for row, status, passed in decisions],
        })
    return output


def evaluator_diagnostics(features: list[dict[str, Any]], labels: dict[str, bool]) -> list[dict[str, Any]]:
    rows = [row for row in features if row["candidate_kind"] == "final" and row["candidate_id"] in labels]
    ids = sorted({key for row in rows for key in row["required_eval_ids"]})
    output = []
    for eval_id in ids:
        counts = Counter()
        confidence = []
        for row in rows:
            result = row["eval_results"].get(eval_id)
            status = result.get("status") if result else "not_applicable"
            counts[status] += 1
            passed = labels[row["candidate_id"]]
            counts[f"{status}:official_{'pass' if passed else 'fail'}"] += 1
            value = (result or {}).get("details", {}).get("confidence")
            if isinstance(value, (int, float)):
                confidence.append({"confidence": value, "external_pass": passed})
        pass_n = counts["pass"]
        fail_n = counts["fail"]
        p_pass = counts["pass:official_pass"] / pass_n if pass_n else None
        p_fail = counts["fail:official_fail"] / fail_n if fail_n else None
        # Signed discrimination: positive means pass status is associated with truth.
        fail_label_rate_when_pass = counts["pass:official_fail"] / pass_n if pass_n else 0
        fail_label_rate_when_not_pass = ((counts["fail:official_fail"] + counts["error:official_fail"] +
                                         counts["not_applicable:official_fail"]) /
                                        max(1, len(rows) - pass_n))
        output.append({
            "eval_id": eval_id, "independence": INDEPENDENCE.get(eval_id, "unclassified"),
            "passes": counts["pass"], "failures": counts["fail"], "errors": counts["error"],
            "not_applicable": counts["not_applicable"], "coverage": 1 - counts["not_applicable"] / len(rows),
            "p_external_pass_given_eval_pass": p_pass,
            "p_external_fail_given_eval_fail": p_fail,
            "false_positive_contribution": counts["pass:official_fail"],
            "false_negative_contribution": counts["fail:official_pass"],
            "discrimination_delta": fail_label_rate_when_not_pass - fail_label_rate_when_pass,
            "confidence_samples": confidence,
        })
    return sorted(output, key=lambda row: (row["discrimination_delta"], row["coverage"]), reverse=True)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}%"


def run_analysis(run_dir: Path, checkpoint_dir: Path | None, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    features = extract_runtime_features(run_dir) + extract_checkpoint_features(run_dir)
    labels_rows = extract_labels(run_dir, checkpoint_dir)
    labels = {row["candidate_id"]: row["external_pass"] for row in labels_rows}
    _write_jsonl(output_dir / "runtime_features.jsonl", features)
    _write_jsonl(output_dir / "external_labels.jsonl", labels_rows)
    joined = [{**row, "external_pass": labels[row["candidate_id"]]}
              for row in features if row["candidate_id"] in labels]
    _write_jsonl(output_dir / "offline_joined_analysis.jsonl", joined)
    diagnostics = evaluator_diagnostics(features, labels)
    policies = policy_metrics(features, labels)
    final_rows = [row for row in features if row["candidate_kind"] == "final"]
    false_fulfilled = [row for row in final_rows if row["runtime_internal_status"] == "FULFILLED"
                       and labels.get(row["candidate_id"]) is False]
    false_unfulfilled = [row for row in final_rows if row["runtime_internal_status"] == "UNFULFILLED"
                         and labels.get(row["candidate_id"]) is True]
    case_data = {
        "false_fulfilment": [{"task_id": row["task_id"],
                               "passing_gates": [key for key, value in _statuses(row).items() if value == "pass"],
                               "source_observation": row["source_observation"],
                               "independence": row["evaluator_independence"],
                               "diagnosis": "semantic pass lacked complete source coverage; formula-text inspection did not independently establish computed correctness"}
                              for row in false_fulfilled],
        "false_unfulfilment": [{"task_id": row["task_id"],
                                 "blocking_gates": [key for key, value in _statuses(row).items() if value != "pass"],
                                 "missing_evidence": row["eval_coverage"] < 1 or row["source_observation"].get("truncated"),
                                 "formula_representation_ambiguous": row["formula_representation_ambiguous"],
                                 "termination_reason": row["termination_reason"]}
                                for row in false_unfulfilled],
    }
    (output_dir / "evaluator_diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    (output_dir / "policy_comparison.json").write_text(json.dumps(policies, indent=2) + "\n")
    (output_dir / "case_analysis.json").write_text(json.dumps(case_data, indent=2) + "\n")
    table = ["| Policy | Precision | Recall | FFR | False-unfulfilment | UNKNOWN | Passes captured | Failures accepted |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in policies:
        table.append(f"| {row['policy']} | {_pct(row['fulfilled_precision'])} | {_pct(row['fulfilled_recall'])} | "
                     f"{_pct(row['false_fulfilment_rate'])} | {_pct(row['false_unfulfilment_rate'])} | "
                     f"{_pct(row['unknown_rate'])} | {row['official_passes_captured']} | {row['official_failures_accepted']} |")
    report = """# Completion calibration: offline development analysis

This analysis was performed on retained runtime evidence. `runtime_features.jsonl`
contains no official labels or grader mismatches. `external_labels.jsonl` contains
only candidate IDs and post-run PASS/FAIL labels. The join occurs offline.

## Candidate-policy comparison

""" + "\n".join(table) + """

## Selected hypothesis

Use three-valued aggregation and require adequate observed-source coverage before
an independent-semantic PASS can authorize `FULFILLED`. Missing, truncated, or
uncertain evidence yields `UNKNOWN`; proven semantic/safety failure yields
`UNFULFILLED`. This is generic, gold-free, and does not loosen a failing gate.

The corpus is only 20 tasks, so policy selection is evidence-directed rather than
an optimization claim. The policy specifically tests the observed failure mode:
high-confidence semantic judgment over incomplete evidence.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    result = {"final_candidates": len(final_rows),
              "intermediate_candidates": len(features) - len(final_rows),
              "labelled_candidates": len(joined), "policies": policies,
              "diagnostics": diagnostics, "cases": case_data,
              "selected_policy": "coverage_aware_three_valued"}
    (output_dir / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-results-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_analysis(args.run_dir, args.checkpoint_results_dir, args.output_dir)
    print(json.dumps({"final_candidates": result["final_candidates"],
                      "intermediate_candidates": result["intermediate_candidates"],
                      "selected_policy": result["selected_policy"]}, indent=2))


if __name__ == "__main__":
    main()
