import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment.manifests import (
    ARMS, DEFAULT_SELECTION, build_manifests, file_hash, parse_args,
    validate_manifest_set, write_manifest_set,
)


DATASET_HASH = json.loads(DEFAULT_SELECTION.read_text())["source_metadata_sha256"]


def pins(**overrides):
    values = dict(
        experiment_id="development-four-arm-v1",
        model="provider/model-2026-08-31",
        model_version="release-2026-08-31",
        container_digest="sha256:" + "a" * 64,
        soffice_version="LibreOffice 25.2.4.3",
        scorer_commit="b" * 40,
        dataset_metadata_sha256=DATASET_HASH,
        environment="linux-amd64-python3.13",
        max_cost=25.0,
    )
    values.update(overrides)
    return values


class RunManifestTest(unittest.TestCase):
    def test_four_arms_have_identical_fixed_conditions_and_only_arm_differs(self):
        manifests = build_manifests(**pins())
        self.assertEqual(set(manifests), set(ARMS))
        normalized = []
        for arm, manifest in manifests.items():
            self.assertEqual(manifest["run_config"]["arm"], arm)
            self.assertEqual(manifest["run_config"]["max_tokens"], 16000)
            self.assertEqual(manifest["run_config"]["max_actions"], 12)
            self.assertEqual(manifest["run_config"]["max_wall_time_ms"], 300000)
            self.assertEqual(manifest["backend_config"]["context_limits"],
                             {"max_cells": 400, "max_chars": 30000})
            self.assertEqual(manifest["backend_config"]["provider"]["timeout_seconds"], 120)
            self.assertEqual(manifest["task_selection"]["name"], "development")
            self.assertEqual(len(manifest["task_selection"]["tasks"]), 20)
            clone = copy.deepcopy(manifest)
            clone["run_config"].pop("arm")
            normalized.append(clone)
        self.assertTrue(all(value == normalized[0] for value in normalized[1:]))

    def test_reproducibility_hashes_and_delegated_multimodal_are_recorded(self):
        manifest = build_manifests(**pins(), deviations=("provider outage window excluded",))["A"]
        metadata = manifest["reproducibility"]
        self.assertEqual(metadata["selection_file_sha256"], file_hash(DEFAULT_SELECTION))
        self.assertEqual(metadata["dataset_metadata_sha256"], DATASET_HASH)
        self.assertRegex(metadata["uv_lock_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(metadata["deviations"], ["provider outage window excluded"])
        self.assertEqual(metadata["multimodal_eval"],
                         "delegated_to_adapter_when_intent_has_visual_semantics")

    def test_heldout_selection_is_embedded_and_hash_bound(self):
        protocol = Path(__file__).resolve().parents[1] / "protocol"
        selection = protocol / "heldout_selection.json"
        manifests = build_manifests(**pins(), selection_path=selection)
        self.assertEqual(manifests["A"]["task_selection"]["name"], "heldout")
        self.assertEqual(len(manifests["A"]["task_selection"]["tasks"]), 380)
        self.assertEqual(manifests["A"]["reproducibility"]["selection_file_sha256"], file_hash(selection))
        validate_manifest_set(manifests, selection_path=selection)
        development = json.loads((protocol / "development_selection.json").read_text())
        all_tasks = json.loads((protocol / "all_tasks_selection.json").read_text())
        dev_ids = {item["id"] for item in development["tasks"]}
        heldout_ids = {item["id"] for item in manifests["A"]["task_selection"]["tasks"]}
        all_ids = {item["id"] for item in all_tasks["tasks"]}
        self.assertFalse(dev_ids & heldout_ids)
        self.assertEqual(dev_ids | heldout_ids, all_ids)
        self.assertEqual(len(all_ids), 400)

    def test_registered_experiment_rejects_development_selection(self):
        with self.assertRaisesRegex(ValueError, "preregistered held-out selection"):
            build_manifests(**pins(experiment_id="four-arm-heldout-v1"))
        heldout = Path(__file__).resolve().parents[1] / "protocol" / "heldout_selection.json"
        manifests = build_manifests(**pins(experiment_id="four-arm-heldout-v1"),
                                    selection_path=heldout)
        self.assertEqual(manifests["D"]["task_selection"]["name"], "heldout")

    def test_missing_or_placeholder_pins_are_rejected(self):
        for key, value in (("model", "TODO"), ("model_version", "latest"),
                           ("container_digest", "TO_BE_PINNED"), ("soffice_version", "placeholder")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_manifests(**pins(**{key: value}))
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(SystemExit):
            parse_args(["--manifest-dir", "m", "--run-root", "r", "--experiment-id", "e",
                        "--container-digest", "sha256:" + "a" * 64, "--soffice-version", "v",
                        "--scorer-commit", "b" * 40, "--dataset-metadata-sha256", DATASET_HASH,
                        "--environment", "linux", "--max-cost", "1"])

    def test_selection_format_and_source_hash_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "selection.json"
            selection = json.loads(DEFAULT_SELECTION.read_text())
            selection["tasks"].append(selection["tasks"][0])
            bad.write_text(json.dumps(selection))
            with self.assertRaises(ValueError):
                build_manifests(**pins(), selection_path=bad)
        with self.assertRaisesRegex(ValueError, "selection source"):
            build_manifests(**pins(dataset_metadata_sha256="c" * 64))

    def test_validator_detects_arm_drift_and_output_paths_cannot_be_reused(self):
        manifests = build_manifests(**pins())
        changed = copy.deepcopy(manifests)
        changed["D"]["run_config"]["max_actions"] = 99
        with self.assertRaisesRegex(ValueError, "fixed conditions"):
            validate_manifest_set(changed)
        uniformly_changed = copy.deepcopy(manifests)
        for value in uniformly_changed.values(): value["run_config"]["max_actions"] = 99
        with self.assertRaisesRegex(ValueError, "preregistered"):
            validate_manifest_set(uniformly_changed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_dir, run_root = root / "manifests", root / "runs"
            write_manifest_set(manifests, manifest_dir, run_root)
            self.assertEqual(sorted(path.name for path in manifest_dir.iterdir()),
                             ["A.json", "B.json", "C.json", "D.json"])
            self.assertTrue(all(not any((run_root / arm).iterdir()) for arm in ARMS))
            with self.assertRaises(FileExistsError):
                write_manifest_set(manifests, manifest_dir, root / "other-runs")


if __name__ == "__main__":
    unittest.main()
