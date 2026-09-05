import json
import sys
import tempfile
import unittest
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))

from experiment.runner import (
    Arm, ExecutionResult, ExperimentRunner, ManifestIntegrityError, ModelReply,
    RunConfig, Task, verify_run_manifest,
)


class Provider:
    def complete(self, prompt, *, model, temperature):
        return ModelReply("ok", 1, 1)


class Services:
    def execute_once(self, task, contract, destination, runtime):
        runtime.complete("direct", purpose="action_generation")
        runtime.action("write")
        destination.write_text("output")
        return ExecutionResult(destination, "ok", {})


def config():
    return RunConfig("provenance", Arm.A, "model", "version", 0, 10, 2, 10000, 1,
                     "sha256:" + "a" * 64, "LibreOffice pinned", "b" * 40,
                     {"model_transport_retries": 0, "action_retries": 0}, ("fixture",))


def source_bytes(cfg):
    run = cfg.__dict__.copy(); run["arm"] = cfg.arm.value
    run["deviations"] = list(cfg.deviations)
    value = {
        "schema_version": "1.0.0", "backend": "fixture:factory",
        "backend_config": {"selection_manifest": "/app/protocol/development_selection.json"},
        "reproducibility": {
            "protocol_sha256": "1" * 64, "selection_sha256": "2" * 64,
            "dataset_metadata_sha256": "3" * 64, "uv_lock_sha256": "4" * 64,
            "container_digest": "sha256:" + "a" * 64,
        },
        "run_config": run,
    }
    # Deliberate whitespace proves retention is byte-equivalent, not reserialized.
    return (json.dumps(value, indent=3, sort_keys=False) + "\n").encode()


class ManifestProvenanceTest(unittest.TestCase):
    def run_fixture(self, root):
        artifact = root / "initial.txt"; artifact.write_text("initial")
        cfg = config(); raw = source_bytes(cfg); out = root / "out"
        ExperimentRunner(cfg, Services(), Provider(), out, source_manifest_bytes=raw).run(
            [Task("t1", "intent", artifact, "text", {})])
        return out, raw

    def test_complete_source_is_byte_retained_embedded_hashed_and_event_bound(self):
        with tempfile.TemporaryDirectory() as td:
            out, raw = self.run_fixture(Path(td))
            self.assertEqual((out / "input_manifest.json").read_bytes(), raw)
            runtime = verify_run_manifest(out)
            self.assertEqual(runtime["source_manifest"]["reproducibility"]["protocol_sha256"], "1" * 64)
            self.assertIn("runtime_created_unix", runtime)
            first = json.loads((out / "events" / "t1.jsonl").read_text().splitlines()[0])
            self.assertEqual(first["payload"]["source_manifest_sha256"], runtime["source_manifest_sha256"])

    def test_retained_byte_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            out, _ = self.run_fixture(Path(td))
            path = out / "input_manifest.json"
            path.write_bytes(path.read_bytes().replace(b'"model"', b'"tampered_model"', 1))
            with self.assertRaisesRegex(ManifestIntegrityError, "hash mismatch"):
                verify_run_manifest(out)

    def test_embedded_manifest_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            out, _ = self.run_fixture(Path(td))
            path = out / "run_manifest.json"; value = json.loads(path.read_text())
            value["source_manifest"]["reproducibility"]["protocol_sha256"] = "9" * 64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ManifestIntegrityError, "embedded source"):
                verify_run_manifest(out)

    def test_source_runtime_config_mismatch_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "initial.txt"; artifact.write_text("initial")
            cfg = config(); value = json.loads(source_bytes(cfg)); value["run_config"]["model"] = "other"
            with self.assertRaisesRegex(ManifestIntegrityError, "differs from runtime config"):
                ExperimentRunner(cfg, Services(), Provider(), root / "out",
                                 source_manifest_bytes=json.dumps(value).encode()).run(
                    [Task("t1", "intent", artifact, "text", {})])

    def test_missing_registered_reproducibility_pins_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "initial.txt"; artifact.write_text("initial")
            cfg = config(); value = json.loads(source_bytes(cfg)); del value["reproducibility"]["selection_sha256"]
            with self.assertRaisesRegex(ManifestIntegrityError, "reproducibility pins"):
                ExperimentRunner(cfg, Services(), Provider(), root / "out",
                                 source_manifest_bytes=json.dumps(value).encode()).run(
                    [Task("t1", "intent", artifact, "text", {})])


if __name__ == "__main__": unittest.main()
