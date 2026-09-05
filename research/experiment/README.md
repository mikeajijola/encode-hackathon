# Four-arm experiment runner

`experiment.runner` fixes the treatment boundaries while injecting all semantic behavior through `Services`:

- A calls `execute_once(task, None, ...)` exactly once. The spreadsheet production implementation is the explicitly characterized controlled Arm A v2, not the legacy baseline.
- B compiles a contract and calls `execute_once` once; it never evaluates.
- C does the same and calls `evaluate_once` once after execution; it never reconciles.
- D compiles a contract and delegates the iterative observe/evaluate/discrepancy/action loop to `reconcile`.

The runner owns common budget accounting, provider traces, input/output hashes, non-destructive output projection, task event logs, prediction rows, and immutable-per-directory run manifests. Semantic implementations must call `runtime.complete` for every model call and `runtime.action` for every tool/capability action. A registered backend must not expose benchmark golden files.

From the repository root, run through the one canonical root `Dockerfile` with a mounted JSON manifest whose `backend` is a Python `module:factory` returning `(services, provider, tasks)` and whose `run_config` matches `RunConfig`. Place it at `run-input/manifest.json`; paths inside it must resolve beneath the mounted `/data` tree:

```sh
docker build --pull -t fulfilment-experiment -f Dockerfile .
docker run --rm --env GEMINI_API_KEY \
  --mount type=bind,src="$PWD/run-input",dst=/data,readonly \
  --mount type=bind,src="$PWD/run-output",dst=/out \
  fulfilment-experiment
```

The image runs as an unprivileged user, installs LibreOffice Calc for headless
recalculation, and installs the exact Python resolution in `uv.lock`. Its entrypoint
only accepts a manifest beneath `/data` and output beneath `/out`; mount `/data`
read-only as shown above. Every run writes `/out/preflight.json` with Python,
dependency, and `soffice` versions before starting the experiment.

Run the same dependency check without an experiment:

```sh
docker run --rm --mount type=bind,src="$PWD/run-input",dst=/data,readonly \
  --mount type=bind,src="$PWD/run-output",dst=/out \
  fulfilment-experiment preflight --json
```

The preflight exits `2` with typed errors such as `missing_soffice`,
`missing_package:<name>`, or `output_directory_not_writable`; it does not silently
disable recalculation.

The adapter is responsible for rendered/visual evidence where meaningful. Each task result explicitly records this delegation. Official scoring remains a separate offline command and is intentionally not imported here.

Successful A/B attempts emit `FULFILLED_UNVERIFIED`; C/D emit `FULFILLED` only after a passing terminal internal evaluation. Both fulfilment labels are completion claims in offline FFR calculations, but only the latter is evidence-gated. Every provider transport attempt is separately traced. `retry_policy.model_transport_retries` is the number of additional attempts and applies at the shared runtime boundary; action retries remain disabled.
