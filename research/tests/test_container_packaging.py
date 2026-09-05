import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import container_preflight


RESEARCH_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = RESEARCH_ROOT.parent


class PreflightTest(unittest.TestCase):
    def test_missing_soffice_is_explicit_and_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"; data.mkdir()
            out = root / "out"; out.mkdir()
            with patch.dict("os.environ", {"SOFFICE": ""}), patch("shutil.which", return_value=None):
                report = container_preflight.dependency_report(data_dir=data, out_dir=out)
            self.assertEqual(report["status"], "error")
            self.assertIn("missing_soffice", report["errors"])
            self.assertIsNone(report["soffice"]["version"])

    def test_report_records_versions_and_can_be_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preflight.json"
            report = {"status": "ok", "python": {"version": "test"}, "errors": []}
            self.assertEqual(container_preflight.emit_report(report, path), 0)
            self.assertEqual(json.loads(path.read_text()), report)

    def test_entrypoint_rejects_paths_outside_mount_contract(self):
        self.assertEqual(container_preflight.run_experiment(Path("/tmp/manifest.json"), Path("/out")), 2)
        self.assertEqual(container_preflight.run_experiment(Path("/data/manifest.json"), Path("/tmp")), 2)
        self.assertEqual(container_preflight.preflight_main([
            "--data-dir", "/data", "--out-dir", "/out", "--record", "/tmp/report.json",
        ]), 2)


class DockerfileStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    def test_repository_root_is_the_only_dockerfile(self):
        candidates = sorted(REPOSITORY_ROOT.rglob("Dockerfile"))
        self.assertEqual(candidates, [REPOSITORY_ROOT / "Dockerfile"])
        self.assertTrue((REPOSITORY_ROOT / ".dockerignore").is_file())

    def test_locked_dependencies_and_recalculation_engine_are_installed(self):
        self.assertIn("libreoffice-calc", self.dockerfile)
        self.assertIn("COPY research/pyproject.toml research/uv.lock", self.dockerfile)
        self.assertIn("uv sync --frozen", self.dockerfile)

    def test_runtime_is_non_root_and_has_healthcheck(self):
        self.assertIn("USER runner", self.dockerfile)
        self.assertIn("HEALTHCHECK", self.dockerfile)
        self.assertIn('ENTRYPOINT ["python", "-m", "container_preflight"]', self.dockerfile)
        self.assertNotIn("--privileged", self.dockerfile)
        self.assertNotIn("curl ", self.dockerfile)

    def test_default_command_obeys_mount_contract(self):
        self.assertIn('"/data/manifest.json"', self.dockerfile)
        self.assertIn('"/out"', self.dockerfile)
        self.assertIn("chown runner:runner /out", self.dockerfile)


if __name__ == "__main__":
    unittest.main()
