"""Run the deterministic infrastructure-only four-arm synthetic experiment.

This uses no SpreadsheetBench tasks or reference answers. Its scripted behavior is
designed to test treatment separation, evidence projection, and offline analysis;
it is not evidence about model quality or the research hypothesis.
"""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from experiment.runner import Arm, EvaluationResult, ExecutionResult, ExperimentRunner, ModelReply, RunConfig, Task
from protocol.analysis import validate_ledger
from protocol.offline_report import analyze, join_results, markdown_table
from protocol.selection import canonical_hash


TASK_DEFINITIONS = (
    {"id": "s1", "intent": "Set the artifact state to alpha.", "expected": "alpha", "instruction_type": "Cell-Level Manipulation", "task_family": "value", "visual": False},
    {"id": "s2", "intent": "Set the artifact state to exact beta, preserving case.", "expected": "beta", "instruction_type": "Cell-Level Manipulation", "task_family": "value", "visual": False},
    {"id": "s3", "intent": "Present gamma without clipping in the rendered region.", "expected": "gamma", "instruction_type": "Sheet-Level Manipulation", "task_family": "visual", "visual": True},
    {"id": "s4", "intent": "Derive and set the multi-step delta state.", "expected": "delta", "instruction_type": "Sheet-Level Manipulation", "task_family": "formula", "visual": False},
)


class ScriptedProvider:
    def complete(self, prompt: str, *, model: str, temperature: float) -> ModelReply:
        # Responses describe phases, never synthetic offline reference values.
        return ModelReply(text=json.dumps({"phase_acknowledged": prompt.split(":", 1)[0]}),
                          input_tokens=3, output_tokens=2, cost=0.0,
                          provider_request_id="deterministic-" + sha256(prompt.encode()).hexdigest()[:12])


class ScriptedServices:
    def compile_contract(self, task: Task, runtime):
        runtime.complete(f"compile:{task.id}:{task.intent}", purpose="contract")
        return {"id": f"contract-{task.id}", "version": 1, "intent": task.intent,
                "assertions": [{"id": "desired", "property": "intent_satisfied"}]}

    def execute_once(self, task: Task, contract, destination: Path, runtime):
        runtime.complete(f"act:{task.id}:{'direct' if contract is None else 'contract'}", purpose="action_generation")
        runtime.action("synthetic_write", {"task_id": task.id})
        arm = runtime.config.arm
        if task.id == "s1": value = "alpha"
        elif task.id == "s2": value = "wrong" if arm is Arm.A else "beta"
        elif task.id == "s3": value = "near-gamma"
        else: value = "almost-delta"
        destination.write_text(value, encoding="utf-8")
        return ExecutionResult(destination, "ok", {"scripted": True})

    def evaluate_once(self, task: Task, contract, artifact: Path, runtime):
        value = artifact.read_text(encoding="utf-8")
        # Deliberate false positive s3 falsifies any assumption that eval presence
        # alone guarantees completion precision.
        passed = task.id in {"s1", "s2", "s3"}
        status = "pass" if passed else "fail"
        return EvaluationResult(passed, status, {"observed": value, "synthetic_blind_spot": task.id == "s3"})

    def reconcile(self, task: Task, contract, destination: Path, runtime):
        runtime.event("observation", {"iteration": 0, "state": "initial"})
        runtime.event("evaluation", {"iteration": 0, "passed": False})
        runtime.event("discrepancy", {"kind": "state_discrepancy", "iteration": 0})
        runtime.action("bounded_transition", {"iteration": 1})
        first_value = {"s1": "alpha", "s2": "beta", "s3": "near-gamma", "s4": "almost-delta"}[task.id]
        destination.write_text(first_value, encoding="utf-8")
        first_pass = task.id in {"s1", "s2"}
        runtime.event("evaluation", {"iteration": 1, "passed": first_pass})
        if not first_pass:
            runtime.event("discrepancy", {"kind": "state_discrepancy", "iteration": 1})
            runtime.action("bounded_transition", {"iteration": 2})
            destination.write_text("gamma" if task.id == "s3" else "delta", encoding="utf-8")
            runtime.event("evaluation", {"iteration": 2, "passed": True})
        if task.context["visual"]:
            render_dir = destination.parent.parent / "renders"
            render_dir.mkdir(exist_ok=True)
            # Portable pixmap: a deterministic rendered artifact with a green
            # pass pixel. This tests render evidence plumbing, not vision quality.
            render = render_dir / f"{task.id}.ppm"
            render.write_bytes(b"P6\n1 1\n255\n\x00\xff\x00")
            runtime.event("render_eval", {"artifact": f"renders/{render.name}", "clipped": False, "passed": True,
                                          "renderer": "synthetic-ppm-v1"})
        evaluation = EvaluationResult(True, "pass", {"first_mutation_pass": first_pass})
        return ExecutionResult(destination, "fulfilled", {"iterations": 1 if first_pass else 2}), evaluation


def digest_tree(root: Path) -> str:
    digest = sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def config(arm: Arm) -> RunConfig:
    return RunConfig("SYNTH-INFRA-001", arm, "scripted-provider", "1.0.0", 0, 100, 4, 10_000, 0,
                     "not-built:synthetic", "not-applicable:text", "synthetic-offline-v1", {"transport": 0},
                     ("Synthetic scripted services; not benchmark/model evidence.",))


def main() -> None:
    root = RESEARCH / "synthetic"
    output_root = root / "results"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    fixture_dir = output_root / "fixtures"
    fixture_dir.mkdir()
    tasks = []
    for definition in TASK_DEFINITIONS:
        artifact = fixture_dir / f"{definition['id']}.txt"
        artifact.write_text("initial", encoding="utf-8")
        tasks.append(Task(definition["id"], definition["intent"], artifact, "text/plain",
                          {"visual": definition["visual"]}))

    task_manifest_body = {"schema_version": "1.0.0", "experiment": "SYNTH-INFRA-001",
                          "warning": "NOT BENCHMARK OR MODEL EVIDENCE",
                          "tasks": [{key: value for key, value in item.items() if key != "expected"} for item in TASK_DEFINITIONS]}
    task_manifest = {**task_manifest_body, "selection_sha256": canonical_hash(task_manifest_body)}
    (output_root / "task_manifest.json").write_text(json.dumps(task_manifest, indent=2) + "\n")

    joined = {}
    run_hashes = {}
    for arm in Arm:
        arm_dir = output_root / arm.value
        ExperimentRunner(config(arm), ScriptedServices(), ScriptedProvider(), arm_dir).run(tasks)
        official_items = []
        internal = []
        for definition in TASK_DEFINITIONS:
            task_id = definition["id"]
            actual = (arm_dir / "outputs" / f"{task_id}.txt").read_text()
            passed = actual == definition["expected"]
            official_items.append({"id": task_id, "status": "graded", "pass": passed,
                                   "correct": int(passed), "cells": 1})
            item = json.loads((arm_dir / "task_results" / f"{task_id}.json").read_text())
            terminal = item.get("terminal_eval")
            item["internal_status"] = "FULFILLED" if terminal and terminal["passed"] else "UNFULFILLED"
            item["artifact_valid"] = True
            item["first_mutation_pass"] = terminal.get("details", {}).get("first_mutation_pass") if terminal else None
            item.update({key: definition[key] for key in ("instruction_type", "task_family")})
            if not passed:
                item["failure_classes"] = ["evaluation_false_positive"] if item["internal_status"] == "FULFILLED" else ["execution_failure"]
            internal.append(item)
        official = {"summary": {"items": len(official_items), "warning": "synthetic offline scorer"}, "items": official_items}
        (arm_dir / "official_results.json").write_text(json.dumps(official, indent=2) + "\n")
        analysis_input = arm_dir / "analysis_input.json"
        analysis_input.write_text(json.dumps(internal, indent=2) + "\n")
        joined[arm.value] = join_results(internal, official_items)
        run_hashes[arm.value] = sha256((arm_dir / "run_manifest.json").read_bytes()).hexdigest()

    report = analyze(joined, samples=1_000, seed=20260905)
    report["scope_warning"] = "INFRASTRUCTURE/TREATMENT-SEPARATION TEST ONLY; NOT SPREADSHEETBENCH OR MODEL EVIDENCE"
    (output_root / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    table = markdown_table(report)
    (output_root / "REPORT.md").write_text(
        "# Synthetic four-arm infrastructure experiment\n\n"
        "> **Not benchmark or model evidence.** Scripted outcomes test orchestration, treatment separation, metrics, and evidence plumbing only.\n\n"
        + table + "\n\n"
        "Expected falsification signal: Arm C deliberately records one false fulfilment; Arm D recovers both first-transition failures. "
        "Observed metrics match that construction. The result validates infrastructure arithmetic only and cannot support the research hypothesis.\n\n"
        "The visual-intent task s3 retains a deterministic PPM render and `render_eval` event. This validates multimodal evidence plumbing, not visual-model accuracy.\n",
        encoding="utf-8")

    assignments = []
    for arm, rows in joined.items():
        for row in rows:
            if row["official_pass"]:
                continue
            assignments.append({"task_id": row["task_id"], "arm": arm,
                                "classes": row["failure_classes"],
                                "evidence_event_ids": [f"{arm}/{row['task_id']}:task_finished"],
                                "rationale": "Scripted fixture assignment backed by the retained task event and offline outcome.",
                                "assigned_by": "synthetic-fixture-rule-v1"})
    (output_root / "failure_assignments.json").write_text(json.dumps(assignments, indent=2) + "\n")

    evidence_hash = digest_tree(output_root)
    ledger = {
        "experiment_id": "SYNTH-INFRA-001", "protocol_version": "1.0.0",
        "hypothesis": "The runner preserves four treatment boundaries and offline analysis detects an injected false fulfilment and reconciliation recoveries.",
        "change": "Run fixed scripted tasks through A/B/C/D and offline analysis.", "control": "A", "treatment": "D",
        "task_set": {"manifest_sha256": task_manifest["selection_sha256"], "task_count": 4},
        "model": {"name": "scripted-provider", "version": "1.0.0", "temperature": 0},
        "budgets": {"tokens": 100, "actions": 4, "wall_clock_seconds": 10},
        "deviations": [{"reason": "Synthetic scripted environment; no benchmark, hosted model, spreadsheet adapter, or official grader."}],
        "results": report["metrics"], "confidence_intervals": report["paired_comparisons"],
        "failure_distribution": report["failure_distribution"],
        "interpretation": "Infrastructure behavior matched construction; this is not evidence for fulfilment reliability.",
        "decision": "inconclusive", "next_experiment": "Run preregistered development tasks with a pinned hosted model.",
        "provenance": {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RESEARCH, text=True).strip(),
                       "run_manifest_sha256": canonical_hash(run_hashes),
                       "evidence_root_sha256": evidence_hash, "scorer_commit": "synthetic-offline-v1",
                       "created_at": "2026-09-05T00:00:00Z"},
    }
    errors = validate_ledger(ledger)
    if errors:
        raise RuntimeError(f"invalid ledger: {errors}")
    (output_root / "ledger.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    print(table)
    print("task_manifest_sha256", task_manifest["selection_sha256"])
    print("evidence_root_sha256_before_ledger", evidence_hash)


if __name__ == "__main__":
    main()
