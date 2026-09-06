"""Read-only audit of committed final artifacts, independently of runtime flags."""
import argparse
import hashlib
import json
from pathlib import Path
from adapters.spreadsheet_diff import diff_workbooks

parser = argparse.ArgumentParser()
parser.add_argument("--archive-root", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
root = args.archive_root; run = root / "results/D"
manifest = json.loads((root / "evidence/D.manifest.json").read_text())
tasks = {str(task["id"]): task for task in manifest["task_selection"]["tasks"]}
rows = []
for path in sorted((run / "task_results").glob("*.json")):
    result = json.loads(path.read_text()); tid = str(result["id"])
    initial = root / "data/dataset" / tasks[tid]["init_path"]
    output = run / result["output"]
    records = [json.loads(line) for line in (run / "events" / f"{tid}.jsonl").read_text().splitlines()]
    contracts = [event["payload"]["contract"] for event in records
                 if event["event_type"] == "accepted_contract" and "contract" in event["payload"]]
    allowed = set(contracts[-1]["authorized_mutation_scopes"]) if contracts else set()
    same = initial.read_bytes() == output.read_bytes()
    diff = None if same else diff_workbooks(initial, output)
    outside = [] if same else [change for change in diff.semantic_changes if change["scope"] not in allowed]
    checkpoints = []
    for event in records:
        if event["event_type"] in ("mutation_checkpoint", "first_mutation_checkpoint"):
            item = event["payload"]
            candidate = run / item["path"]
            checkpoints.append({"path": item["path"], "hash_matches":
                                hashlib.sha256(candidate.read_bytes()).hexdigest() == item["artifact_hash"]})
    rows.append({"task_id": tid, "byte_identical_to_initial": same,
                 "accepted_contract_present": bool(contracts), "outside_scope": outside,
                 "package_parts_changed": [] if same else list(diff.representation_parts),
                 "checkpoints": checkpoints})
report = {"tasks": rows, "preservation_violations": sum(bool(row["outside_scope"]) for row in rows),
          "all_checkpoint_hashes_match": all(c["hash_matches"] for row in rows for c in row["checkpoints"])}
args.out.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "tasks"}))
