"""CLI and Docker entrypoint for an injected experiment services factory."""

import argparse
import importlib
import json
from pathlib import Path

from .runner import Arm, ExperimentRunner, RunConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="JSON RunConfig plus backend and tasks")
    parser.add_argument("--out-dir", default="/out")
    args = parser.parse_args()
    manifest_bytes = Path(args.manifest).read_bytes()
    raw = json.loads(manifest_bytes)
    module_name, factory_name = raw["backend"].split(":", 1)
    factory = getattr(importlib.import_module(module_name), factory_name)
    services, provider, tasks = factory(raw)
    fields = {key: value for key, value in raw["run_config"].items() if key != "arm"}
    config = RunConfig(arm=Arm(raw["run_config"]["arm"]), **fields)
    ExperimentRunner(config, services, provider, Path(args.out_dir),
                     source_manifest_bytes=manifest_bytes).run(tasks)


if __name__ == "__main__":
    main()
