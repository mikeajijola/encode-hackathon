"""Container dependency preflight and constrained experiment entrypoint."""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


REQUIRED_PACKAGES = ("openpyxl", "opentelemetry-sdk", "pydantic-ai-slim")
SOFFICE_NAMES = ("soffice", "libreoffice")


def _inside(path: Path, root: Path) -> bool:
    resolved, resolved_root = path.resolve(), root.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def dependency_report(*, data_dir: Path = Path("/data"), out_dir: Path = Path("/out")) -> dict:
    errors = []
    packages = {}
    for package in REQUIRED_PACKAGES:
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
            errors.append(f"missing_package:{package}")

    configured = os.environ.get("SOFFICE")
    soffice = configured if configured and Path(configured).is_file() else None
    if soffice is None:
        soffice = next((found for name in SOFFICE_NAMES if (found := shutil.which(name))), None)
    soffice_version = None
    if soffice:
        try:
            completed = subprocess.run(
                [soffice, "--version"], check=True, capture_output=True, text=True, timeout=10,
            )
            soffice_version = (completed.stdout or completed.stderr).strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError) as error:
            errors.append(f"soffice_unusable:{type(error).__name__}")
    else:
        errors.append("missing_soffice")

    if not data_dir.is_dir():
        errors.append("missing_data_directory")
    if not out_dir.is_dir():
        errors.append("missing_output_directory")
    elif not os.access(out_dir, os.W_OK):
        errors.append("output_directory_not_writable")

    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "packages": packages,
        "soffice": {"path": soffice, "version": soffice_version},
        "filesystem": {
            "data": str(data_dir), "data_readable": os.access(data_dir, os.R_OK),
            "out": str(out_dir), "out_writable": os.access(out_dir, os.W_OK),
        },
    }


def emit_report(report: dict, record: Path | None = None) -> int:
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered, flush=True)
    if record is not None:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "ok" else 2


def preflight_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark container dependencies")
    parser.add_argument("--json", action="store_true", help="retained for an explicit machine-readable command")
    parser.add_argument("--data-dir", default="/data")
    parser.add_argument("--out-dir", default="/out")
    parser.add_argument("--record")
    args = parser.parse_args(argv)
    if args.record and not _inside(Path(args.record), Path(args.out_dir)):
        return emit_report({"status": "error", "errors": ["record_outside_output"]})
    return emit_report(
        dependency_report(data_dir=Path(args.data_dir), out_dir=Path(args.out_dir)),
        Path(args.record) if args.record else None,
    )


def run_experiment(manifest: Path, out_dir: Path) -> int:
    data_root, output_root = Path("/data"), Path("/out")
    if not _inside(manifest, data_root):
        print(json.dumps({"status": "error", "errors": ["manifest_outside_data"]}), file=sys.stderr)
        return 2
    if not _inside(out_dir, output_root):
        print(json.dumps({"status": "error", "errors": ["output_outside_out"]}), file=sys.stderr)
        return 2
    report = dependency_report(data_dir=data_root, out_dir=output_root)
    # ExperimentRunner requires an empty output directory. Validate and print
    # before execution, then persist the same report after the runner prepares it.
    code = emit_report(report)
    if code:
        return code
    if not manifest.is_file():
        print(json.dumps({"status": "error", "errors": ["missing_manifest"]}), file=sys.stderr)
        return 2
    from experiment.cli import main as experiment_main
    sys.argv = ["experiment.cli", "--manifest", str(manifest), "--out-dir", str(out_dir)]
    experiment_main()
    (out_dir / "preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--json", action="store_true")
    preflight.add_argument("--data-dir", default="/data")
    preflight.add_argument("--out-dir", default="/out")
    preflight.add_argument("--record")
    run = subparsers.add_parser("run")
    run.add_argument("--manifest", default="/data/manifest.json")
    run.add_argument("--out-dir", default="/out")
    args = parser.parse_args(argv)
    if args.command == "preflight":
        forwarded = ["--data-dir", args.data_dir, "--out-dir", args.out_dir]
        if args.json: forwarded.append("--json")
        if args.record: forwarded.extend(("--record", args.record))
        return preflight_main(forwarded)
    return run_experiment(Path(args.manifest), Path(args.out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
