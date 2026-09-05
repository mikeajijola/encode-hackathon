# Four-arm experiment runner

`experiment.runner` fixes the treatment boundaries while injecting all semantic behavior through `Services`:

- A calls `execute_once(task, None, ...)` exactly once. A production service should delegate to the existing one-shot baseline prompt/parser/writer.
- B compiles a contract and calls `execute_once` once; it never evaluates.
- C does the same and calls `evaluate_once` once after execution; it never reconciles.
- D compiles a contract and delegates the iterative observe/evaluate/discrepancy/action loop to `reconcile`.

The runner owns common budget accounting, provider traces, input/output hashes, non-destructive output projection, task event logs, prediction rows, and immutable-per-directory run manifests. Semantic implementations must call `runtime.complete` for every model call and `runtime.action` for every tool/capability action. A registered backend must not expose benchmark golden files.

Run through Docker with a mounted JSON manifest whose `backend` is a Python `module:factory` returning `(services, provider, tasks)` and whose `run_config` matches `RunConfig`:

```sh
docker build -t fulfilment-experiment .
docker run --rm -v "$PWD/run-input:/data:ro" -v "$PWD/run-output:/out" fulfilment-experiment
```

The adapter is responsible for rendered/visual evidence where meaningful. Each task result explicitly records this delegation. Official scoring remains a separate offline command and is intentionally not imported here.
