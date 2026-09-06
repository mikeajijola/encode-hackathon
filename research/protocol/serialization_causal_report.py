"""Extract compiler and trajectory evidence for paired task losses, offline."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--archive-root", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args(); root = args.archive_root
old, new = root / "retained", root / "results/D"
def events(path): return [json.loads(line) for line in path.read_text().splitlines()]
def first_contract(directory, tid):
    return next(item for item in events(directory / "traces" / f"{tid}.jsonl") if item["purpose"] == "contract")
compiler = []
for path in sorted((new / "task_results").glob("*.json")):
    result = json.loads(path.read_text()); tid = str(result["id"])
    a, b = first_contract(old, tid), first_contract(new, tid)
    compiler.append({"task_id": tid, "identical_prompt": a["prompt"] == b["prompt"],
                     "before_prompt_sha256": sha256(a["prompt"].encode()).hexdigest(),
                     "after_prompt_sha256": sha256(b["prompt"].encode()).hexdigest(),
                     "before_response_sha256": sha256(a["response"].encode()).hexdigest(),
                     "after_response_sha256": sha256(b["response"].encode()).hexdigest(),
                     "termination": result["status"], "actions": result["usage"]["actions"]})
trajectory = []
for path in sorted((new / "checkpoint-results").glob("*.official.json")):
    row = next((r for r in json.loads(path.read_text())["items"] if r["id"] == "120-24"), None)
    if row:
        trajectory.append({"checkpoint": path.name, "official_pass": row["pass"],
                           "correct_cells": row["correct"], "total_cells": row["cells"]})
decision_evidence = [item for item in events(new / "events/120-24.jsonl") if 100 <= item["sequence"] <= 119]
invalid = root / "results-invalid-default-home/D"
partial_usage = {}
if (invalid / "traces").exists():
    rows = [item for path in (invalid / "traces").glob("*.jsonl") for item in events(path)]
    partial_usage = {"completed_model_calls": len(rows),
                     "input_tokens": sum(item.get("input_tokens", 0) for item in rows),
                     "output_tokens": sum(item.get("output_tokens", 0) for item in rows),
                     "completed_task_records": len(list((invalid / "task_results").glob("*.json"))),
                     "reason_excluded": "independent live LibreOffice profile failure; aborted before official scoring"}
report = {"compiler_comparison": compiler, "120-24_checkpoint_trajectory": trajectory,
          "120-24_correct_state_to_regression_evidence": decision_evidence,
          "excluded_operational_trial": partial_usage,
          "remaining_failure_mechanisms": {
              "105-24": "compiler emitted contract_schema_version instead of schema_version before mutation",
              "37554": "compiler emitted contract_schema_version instead of schema_version before mutation",
              "168-17": "proposed A1:E1 mutation exceeds A2:E12 authorization; no broker invocation",
              "120-24": "correct states at mutations 2-4 followed by an in-scope regression at mutation 5; nonblank/type and deferred semantic gates supplied discrepancies"}}
args.out.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"identical_compiler_prompts": sum(row["identical_prompt"] for row in compiler),
                  "tasks": len(compiler), "excluded_operational_trial": partial_usage}))
