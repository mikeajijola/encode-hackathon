import json
import tempfile
import unittest
from pathlib import Path

from experiment.manifests import build_manifests, write_manifest_set
from protocol.analysis import validate_ledger
from protocol.offline_report import analyze
from protocol.registered_run import (_stage_blind_dataset, _write_ledger, fulfilment_command,
                                     preflight, scorer_command)


DATASET = Path(__file__).resolve().parents[1] / "data" / "spreadsheetbench_verified_400"
DIGEST = "sha256:" + "a" * 64


class RegisteredRunTest(unittest.TestCase):
    def fixture(self):
        td = tempfile.TemporaryDirectory(); root = Path(td.name)
        manifests = build_manifests(
            experiment_id="registered-test", model="provider/model", model_version="release-1",
            container_digest=DIGEST, soffice_version="LibreOffice 25.2.0",
            scorer_commit="b" * 40,
            dataset_metadata_sha256="bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7",
            dataset_json=DATASET / "dataset.json", environment="linux-amd64", max_cost=1,
        )
        manifest_dir, run_root = root / "manifests", root / "runs"
        write_manifest_set(manifests, manifest_dir, run_root)
        return td, manifest_dir, run_root

    def test_preflight_binds_dataset_image_and_four_empty_arms(self):
        td, manifests, runs = self.fixture(); self.addCleanup(td.cleanup)
        report = preflight(manifests, runs, DATASET, "test@" + DIGEST, require_runtime=False)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["arms"], ["A", "B", "C", "D"])
        with self.assertRaisesRegex(ValueError, "exact manifest container digest"):
            preflight(manifests, runs, DATASET, "test@sha256:" + "c" * 64, require_runtime=False)
        (runs / "A" / "unexpected").write_text("x")
        with self.assertRaisesRegex(ValueError, "empty"):
            preflight(manifests, runs, DATASET, "test@" + DIGEST, require_runtime=False)

    def test_fulfilment_and_scorer_have_separate_mount_and_entrypoint_contracts(self):
        td, manifests, runs = self.fixture(); self.addCleanup(td.cleanup)
        fulfil = fulfilment_command("test@" + DIGEST, manifests, DATASET, runs / "A", "A")
        score = scorer_command("test@" + DIGEST, DATASET, runs / "A")
        self.assertIn(f"{DATASET.resolve()}:/data/dataset:ro", fulfil)
        self.assertIn("/manifests/A.json", fulfil)
        self.assertIn("--user", fulfil)
        self.assertIn("HOME=/tmp/run-home", fulfil)
        self.assertNotIn("--entrypoint", fulfil)
        self.assertIn("--entrypoint", score)
        self.assertIn("/run/official_results.json", score)
        self.assertNotIn(str(manifests.resolve()), score)

    def test_manifests_never_contain_golden_or_expected_answers(self):
        td, manifests, runs = self.fixture(); self.addCleanup(td.cleanup)
        for path in manifests.glob("*.json"):
            serialized = json.dumps(json.loads(path.read_text())).lower()
            self.assertNotIn("golden", serialized)
            self.assertNotIn("expected_answer", serialized)

    def test_provisional_ledger_is_schema_valid_and_evidence_bound(self):
        td, manifest_dir, runs = self.fixture(); self.addCleanup(td.cleanup)
        manifests = {arm: json.loads((manifest_dir / f"{arm}.json").read_text())
                     for arm in "ABCD"}
        def row(task_id, passed):
            return {"task_id": task_id, "official_pass": passed, "internal_status": "FULFILLED",
                    "artifact_valid": True, "constraint_violation": False, "first_mutation_pass": passed,
                    "correct_cells": int(passed), "total_cells": 1, "actions": 1, "tokens": 2,
                    "latency_ms": 3, "cost_usd": .01, "failure_classes": []}
        report = analyze({arm: [row("one", arm == "D"), row("two", True)] for arm in "ABCD"}, samples=20)
        (runs / "analysis.json").write_text(json.dumps(report))
        _write_ledger(runs, manifest_dir, manifests, report)
        ledger = json.loads((runs / "ledger.json").read_text())
        self.assertEqual(validate_ledger(ledger), [])
        self.assertEqual(ledger["decision"], "inconclusive")
        self.assertRegex(ledger["provenance"]["evidence_root_sha256"], r"^[0-9a-f]{64}$")

    def test_blind_fulfilment_dataset_contains_no_reference_artifacts(self):
        td, manifests, runs = self.fixture(); self.addCleanup(td.cleanup)
        target = Path(td.name) / "blind"
        _stage_blind_dataset(DATASET, target, {"13-1", "51-12"})
        self.assertEqual((target / "dataset.json").read_bytes(), (DATASET / "dataset.json").read_bytes())
        files = [path.name for path in target.rglob("*") if path.is_file()]
        self.assertTrue(any("init" in name for name in files))
        self.assertFalse(any("golden" in name.lower() for name in files))
        self.assertEqual(len(list(target.rglob("*init*.xlsx"))), 2)


if __name__ == "__main__": unittest.main()
