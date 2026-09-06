"""Offline paired preservation gate. No runtime imports of this module."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean

from fulfilment.evidence import EvidenceStore
from protocol.analysis import paired_bootstrap_ci, mcnemar_exact


def read(path):
    return json.loads(Path(path).read_text())


def summarize(directory):
    analysis = read(directory / "mechanism_analysis.json")
    official = read(directory / "official_results.json")
    outcomes = {row["id"]: row for row in official["items"]}
    records = {str(row["id"]): row for row in map(read, (directory / "task_results").glob("*.json"))}
    rows = []
    for task in analysis["tasks"]:
        tid = task["task_id"]; result = records[tid]
        rows.append({"task_id": tid, "official_pass": outcomes[tid].get("pass", False),
                     "internal_status": task["internal_completion"],
                     "constraint_violation": result["constraint_violation"],
                     "runtime_validity_flag": result["artifact_valid"],
                     "artifact_valid": outcomes[tid]["status"] == "graded",
                     "actions": task["total_actions_to_termination"],
                     "iterations": task["total_iterations_to_termination"],
                     "tokens": task["total_tokens_to_termination"],
                     "latency_ms": task["wall_time_to_termination_ms"],
                     "estimated_cost": task["estimated_cost_to_termination"],
                     "recovered": task["recovered"], "termination": task["termination_reason"],
                     "failure_classes": result["failure_classes"]})
    fulfilled = [row for row in rows if row["internal_status"] == "FULFILLED"]
    passes = sum(row["official_pass"] for row in rows)
    correct_claims = sum(row["official_pass"] for row in fulfilled)
    summary = {**analysis["summary"], "cell_accuracy": official["summary"]["cell_accuracy"],
               "fulfilled_precision": correct_claims / len(fulfilled) if fulfilled else None,
               "fulfilled_recall": correct_claims / passes if passes else None,
               "fulfilled_claims": len(fulfilled),
               "false_fulfilment_rate": 1 - correct_claims / len(fulfilled) if fulfilled else None,
               "valid_artifacts": sum(row["artifact_valid"] for row in rows),
               "runtime_positive_validity_flags": sum(row["runtime_validity_flag"] is True for row in rows),
               "runtime_unknown_validity_flags": sum(row["runtime_validity_flag"] is None for row in rows),
               "preservation_violations": sum(row["constraint_violation"] is True for row in rows),
               "mean_resources": {key: mean(row[key] for row in rows) for key in
                                  ("actions", "iterations", "tokens", "latency_ms", "estimated_cost")},
               "total_resources": {key: sum(row[key] for row in rows) for key in
                                   ("actions", "iterations", "tokens", "latency_ms", "estimated_cost")}}
    return rows, summary


def compare(prior_dir, current_dir, output):
    before, old = summarize(prior_dir); after, new = summarize(current_dir)
    by_old = {row["task_id"]: row for row in before}
    assert set(by_old) == {row["task_id"] for row in after} and len(after) == 20
    integrity = []
    for path in (current_dir / "events").glob("*.broker.jsonl"):
        records = EvidenceStore(path).verify()
        integrity.append({"file": path.name, "events": len(records), "verified": True})
    hashes = []
    for path in (current_dir / "task_results").glob("*.json"):
        result = read(path)
        actual = hashlib.sha256((current_dir / result["output"]).read_bytes()).hexdigest()
        hashes.append({"task_id": result["id"], "matches": actual == result["output_artifact_hash"]})
    fixed = [row for row in after if row["task_id"] in ("47766", "50971")]
    claim_logs = {f"{row['task_id']}.broker.jsonl" for row in after if row["internal_status"] == "FULFILLED"}
    verified_logs = {row["file"] for row in integrity}
    gate = {
        "preservation_at_most_prior_baseline_one": new["preservation_violations"] <= 1,
        "original_fixed_cases_remain_fixed": all(not row["constraint_violation"] for row in fixed),
        "FFR_zero": new["false_fulfilment_rate"] == 0,
        "precision_100_percent_nonvacuous": new["fulfilled_precision"] == 1,
        "valid_artifacts_100_percent": new["valid_artifacts"] == 20,
        "official_pass_rate_at_least_parent": new["official_pass_rate"] >= old["official_pass_rate"],
        "evidence_integrity": claim_logs <= verified_logs and all(row["matches"] for row in hashes),
    }
    result = {"parent_commit": "c70e0b5", "before": old, "after": new,
              "paired": [{"task_id": row["task_id"], "before": by_old[row["task_id"]], "after": row} for row in after],
              "paired_pass_difference_ci95": paired_bootstrap_ci(before, after, samples=10000, seed=20260906),
              "mcnemar": mcnemar_exact(before, after), "decision_gate": gate,
              "proceed_ABCD": all(gate.values()), "hash_verification": hashes, "evidence_verification": integrity,
              "false_fulfilments": [row for row in after if row["internal_status"] == "FULFILLED" and not row["official_pass"]],
              "recoveries": [row for row in after if row["recovered"]],
              "failure_distribution": dict(Counter(item for row in after for item in row["failure_classes"]))}
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"after": new, "decision_gate": gate, "proceed_ABCD": result["proceed_ABCD"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    compare(args.prior, args.current, args.out)
