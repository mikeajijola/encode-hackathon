"""Prepare only frozen development inputs and offline retained evidence."""
import argparse
import io
import json
from pathlib import Path
import tarfile

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--retained", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "results/gcp-d-preservation-20260906/D.manifest.json").read_text())
ids = {str(task["id"]) for task in manifest["task_selection"]["tasks"]}
assert len(ids) == 20
metadata = json.loads((args.dataset / "dataset.json").read_text())
selected = [task for task in metadata if str(task["id"]) in ids]
manifest["run_config"]["experiment_id"] = "development-d-serialization-firewall-v1"
manifest["run_config"]["scorer_commit"] = "c70e0b555e79f7be1ef5eb726eaf7b415d0c3349"
manifest["experiment_revision"] = {
    "parent": "c70e0b5", "kind": "d_only_serialization_preservation",
    "changed_component": "transactional_scope_firewall",
    "completion_semantics": "unchanged", "heldout_access": "forbidden",
    "hypothesis": "scoped original-package reconstruction eliminates save drift without weakening preservation",
    "build_isolation_change": "exclude research/results from image; offline labels never available to fulfilment",
}
with tarfile.open(args.out, "w:gz") as archive:
    def add_json(name, value):
        content = (json.dumps(value, indent=2) + "\n").encode()
        info = tarfile.TarInfo(name); info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    add_json("data/manifest.json", manifest)
    archive.add(args.dataset / "dataset.json", "data/dataset/dataset.json")
    add_json("scorer-dataset/dataset.json", selected)
    for task in selected:
        folder = args.dataset / task["spreadsheet_path"]
        for path in folder.glob("*.xlsx"):
            if "init" in path.name:
                archive.add(path, f"data/dataset/{task['spreadsheet_path']}/{path.name}")
            archive.add(path, f"scorer-dataset/{task['spreadsheet_path']}/{path.name}")
    archive.add(args.retained, "retained")
print(json.dumps({"selected_tasks": len(selected), "payload": str(args.out)}))
