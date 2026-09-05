"""Dependency-free paired analysis for the four-arm fulfilment experiment.

Input rows are dictionaries keyed by task_id. Goldens enter only after each run has
terminated and are represented by ``official_pass``/``correct_cells`` fields.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def arm_metrics(rows: list[dict]) -> dict:
    """Compute preregistered metrics for one arm from completed per-task rows."""
    n = len(rows)
    fulfilled = [r for r in rows if r["internal_status"] == "FULFILLED"]
    official_success = [r for r in rows if r["official_pass"]]
    true_fulfilled = [r for r in fulfilled if r["official_pass"]]
    first_failed = [r for r in rows if r.get("first_mutation_pass") is False]
    recovered = [r for r in first_failed if r["official_pass"]]
    total_cells = sum(r.get("total_cells", 0) for r in rows)
    correct_cells = sum(r.get("correct_cells", 0) for r in rows)
    return {
        "tasks": n,
        "pass_rate": safe_ratio(len(official_success), n),
        "cell_accuracy": safe_ratio(correct_cells, total_cells),
        "false_fulfilment_rate": safe_ratio(len(fulfilled) - len(true_fulfilled), len(fulfilled)),
        "internal_eval_precision": safe_ratio(len(true_fulfilled), len(fulfilled)),
        "internal_eval_recall": safe_ratio(len(true_fulfilled), len(official_success)),
        "recovery_yield": safe_ratio(len(recovered), len(first_failed)),
        "artifact_validity_rate": safe_ratio(sum(bool(r["artifact_valid"]) for r in rows), n),
        "constraint_violation_rate": safe_ratio(sum(bool(r.get("constraint_violation")) for r in rows), n),
        "actions_mean": safe_ratio(sum(r.get("actions", 0) for r in rows), n),
        "tokens_mean": safe_ratio(sum(r.get("tokens", 0) for r in rows), n),
        "latency_ms_mean": safe_ratio(sum(r.get("latency_ms", 0) for r in rows), n),
        "cost_usd_mean": safe_ratio(sum(r.get("cost_usd", 0.0) for r in rows), n),
    }


def paired_pass_difference(control: list[dict], treatment: list[dict]) -> float:
    pairs = _pairs(control, treatment)
    return sum(int(t["official_pass"]) - int(c["official_pass"]) for c, t in pairs) / len(pairs)


def paired_bootstrap_ci(
    control: list[dict], treatment: list[dict], *, samples: int = 10_000,
    seed: int = 20260905, confidence: float = 0.95,
) -> dict:
    """Percentile CI for paired pass-rate difference, resampling task pairs."""
    pairs = _pairs(control, treatment)
    effects = [int(t["official_pass"]) - int(c["official_pass"]) for c, t in pairs]
    rng = random.Random(seed)
    estimates = sorted(sum(rng.choice(effects) for _ in effects) / len(effects) for _ in range(samples))
    alpha = (1 - confidence) / 2
    return {
        "estimate": sum(effects) / len(effects),
        "lower": _quantile(estimates, alpha),
        "upper": _quantile(estimates, 1 - alpha),
        "confidence": confidence,
        "samples": samples,
        "seed": seed,
    }


def mcnemar_exact(control: list[dict], treatment: list[dict]) -> dict:
    """Exact two-sided McNemar test using discordant task pairs."""
    pairs = _pairs(control, treatment)
    control_only = sum(c["official_pass"] and not t["official_pass"] for c, t in pairs)
    treatment_only = sum(t["official_pass"] and not c["official_pass"] for c, t in pairs)
    discordant = control_only + treatment_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(control_only, treatment_only) + 1)) / (2**discordant)
        p_value = min(1.0, 2 * tail)
    return {"control_only": control_only, "treatment_only": treatment_only, "discordant": discordant, "p_value": p_value}


def breakdown(rows: list[dict], field: str) -> dict[str, dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get(field, "unknown"))].append(row)
    return {name: arm_metrics(group) for name, group in sorted(groups.items())}


def failure_distribution(rows: list[dict]) -> dict[str, int]:
    return dict(sorted(Counter(label for row in rows for label in row.get("failure_classes", [])).items()))


def validate_ledger(entry: dict) -> list[str]:
    """Fast structural validation; JSON Schema remains the normative definition."""
    required = {"experiment_id", "protocol_version", "hypothesis", "change", "control", "treatment", "task_set", "model", "budgets", "results", "confidence_intervals", "failure_distribution", "interpretation", "decision", "next_experiment", "provenance"}
    errors = [f"missing:{key}" for key in sorted(required - entry.keys())]
    if entry.get("decision") not in {"supported", "unsupported", "inconclusive"}:
        errors.append("invalid:decision")
    for key in ("git_commit", "run_manifest_sha256", "evidence_root_sha256", "scorer_commit", "created_at"):
        if key not in entry.get("provenance", {}):
            errors.append(f"missing:provenance.{key}")
    for key in ("tokens", "actions", "wall_clock_seconds"):
        if not isinstance(entry.get("budgets", {}).get(key), int) or entry.get("budgets", {}).get(key, 0) < 1:
            errors.append(f"invalid:budgets.{key}")
    return errors


def _pairs(control: list[dict], treatment: list[dict]) -> list[tuple[dict, dict]]:
    left = {r["task_id"]: r for r in control}
    right = {r["task_id"]: r for r in treatment}
    if left.keys() != right.keys() or not left:
        raise ValueError("paired analysis requires identical non-empty task_id sets")
    return [(left[key], right[key]) for key in sorted(left)]


def _quantile(values: list[float], q: float) -> float:
    index = (len(values) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - index) + values[upper] * (index - lower)
