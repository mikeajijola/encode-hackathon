import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]


class SyntheticExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / "results"
        subprocess.run([sys.executable, str(RESEARCH / "synthetic" / "run.py"),
                        "--out-dir", str(cls.root)], check=True, capture_output=True, text=True)
        cls.analysis = json.loads((cls.root / "analysis.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_injected_false_fulfilment_and_recovery_are_detected(self):
        self.assertEqual(self.analysis["metrics"]["C"]["false_fulfilment_rate"], 1 / 3)
        self.assertEqual(self.analysis["metrics"]["D"]["recovery_yield"], 1.0)
        self.assertEqual(self.analysis["metrics"]["D"]["pass_rate"], 1.0)

    def test_all_arms_retain_required_raw_evidence(self):
        for arm in "ABCD":
            directory = self.root / arm
            for name in ("run_manifest.json", "predictions.jsonl", "run.log", "official_results.json", "analysis_input.json"):
                self.assertTrue((directory / name).is_file(), f"{arm}/{name}")
            self.assertEqual(len(list((directory / "outputs").glob("*.txt"))), 4)
            self.assertEqual(len(list((directory / "events").glob("*.jsonl"))), 4)
            self.assertEqual(len(list((directory / "traces").glob("*.jsonl"))), 4)

    def test_visual_evidence_and_non_claim_are_explicit(self):
        self.assertTrue((self.root / "D" / "renders" / "s3.ppm").is_file())
        events = (self.root / "D" / "events" / "s3.jsonl").read_text()
        self.assertIn('"event_type": "render_eval"', events)
        self.assertIn("Not benchmark or model evidence", (self.root / "REPORT.md").read_text())

    def test_ledger_and_hashes_are_well_formed(self):
        ledger = json.loads((self.root / "ledger.json").read_text())
        self.assertEqual(ledger["decision"], "inconclusive")
        self.assertEqual(len(ledger["provenance"]["evidence_root_sha256"]), 64)
        self.assertEqual(len(ledger["task_set"]["manifest_sha256"]), 64)
        self.assertIn("| Arm | Pass rate | Cell accuracy | FFR |", (self.root / "REPORT.md").read_text())
        digest = __import__("hashlib").sha256()
        for path in sorted(item for item in self.root.rglob("*") if item.is_file() and item.name != "ledger.json"):
            digest.update(path.relative_to(self.root).as_posix().encode())
            digest.update(path.read_bytes())
        self.assertEqual(digest.hexdigest(), ledger["provenance"]["evidence_root_sha256"])
        assignments = json.loads((self.root / "failure_assignments.json").read_text())
        self.assertTrue(assignments)
        self.assertTrue(all(item["evidence_event_ids"] for item in assignments))


if __name__ == "__main__": unittest.main()
