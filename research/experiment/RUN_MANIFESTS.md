# Reproducible SpreadsheetBench run manifests

Generate all four development-arm manifests only after pinning the model release,
container, scorer revision, LibreOffice version, dataset metadata, environment, and
monetary ceiling. The model has no default: pass both flags or set
The default direct-Gemini pins are `gemini-3.7-flash` and provider-reported version
`3.7-flash-08-2026`. Override them with `EXPERIMENT_MODEL` and
`EXPERIMENT_MODEL_VERSION` only when registering a separate experiment.

```sh
cd research
python -m experiment.manifests \
  --manifest-dir ../run-input/manifests \
  --run-root ../run-output/development-four-arm-v1 \
  --experiment-id development-four-arm-v1 \
  --model 'PROVIDER/EXACT-MODEL-ID' \
  --model-version '3.7-flash-08-2026' \
  --container-digest 'sha256:<64 hex characters>' \
  --soffice-version 'LibreOffice <exact version>' \
  --scorer-commit '<full 40-character git commit>' \
  --dataset-metadata-sha256 bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7 \
  --dataset-json ../run-input/dataset/dataset.json \
  --selection protocol/heldout_selection.json \
  --environment 'linux-amd64-python3.13' \
  --max-cost 25.00
```

`TODO`, `latest`, placeholders, malformed hashes, selection/source mismatches, and
reused output paths are rejected. The generator takes temperature, token/action/
wall-clock budgets, and retry policy from the frozen preregistration. Context limits
are fixed at 400 cells/30,000 characters and provider timeout at 120 seconds unless
an explicitly recorded new experiment changes them. Use `--deviation '<reason>'`
for infrastructure deviations; never silently edit one arm.

The generator defaults to the committed golden-blind development selection. Pass
`--selection protocol/heldout_selection.json` for the preregistered 380-task
experiment or `--selection protocol/all_tasks_selection.json` for a subsequent
all-400 submission run. The chosen selection is embedded into every manifest and
bound by its canonical and file hashes. The registered experiment ID rejects any
selection other than the preregistered held-out complement. Each manifest also
records the source dataset metadata hash, `uv.lock` hash, protocol hash, backend
factory, container digest, environment, and LibreOffice version.
Rendered/multimodal evaluation remains explicitly delegated to the adapter when the
intent has visual semantics.

Run each arm with the identical image and read-only input mount. Copy the generated
manifests under `run-input/manifests` before mounting:

```sh
IMAGE='fulfilment-experiment@sha256:<same digest recorded above>'
for ARM in A B C D; do
  docker run --rm \
    -e GEMINI_API_KEY \
    -v "$PWD/run-input:/data:ro" \
    -v "$PWD/run-output/development-four-arm-v1/$ARM:/out" \
    "$IMAGE" run --manifest "/data/manifests/$ARM.json" --out-dir /out
done
```

Every arm directory is created empty. The experiment runner additionally refuses a
non-empty directory. Score outputs only after all fulfilment runs finish; goldens
must not be present in manifests, prompts, contracts, or fulfilment-time evals.

The preferred orchestration command enforces that chronology, checks the exact
image and dataset pins, stages a fulfilment-only dataset containing no golden
workbooks, runs every arm to a complete terminal output set, and only then mounts
the original dataset into fresh scorer containers. Arm D's first mutation is saved
and scored separately, making recovery yield an observed benchmark quantity rather
than an inference from the final artifact. The coordinator writes `analysis.json`,
`arm_table.md`, evidence-linked `failure_assignments.json`, and a provisional
append-only `ledger.json`:

```sh
cd research
python -m protocol.registered_run \
  --manifest-dir ../run-input/manifests \
  --run-root ../run-output/development-four-arm-v1 \
  --dataset-dir ../run-input/dataset \
  --image 'fulfilment-experiment@sha256:<same digest recorded above>'
```

Use `--preflight-only` before spending model budget. The orchestrator passes the
host numeric user into the non-root container and assigns a disposable tmpfs home,
so bind-mounted results remain writable without broadening artifact access. A
failed or incomplete arm prevents all official scoring. The generated ledger is
deliberately `inconclusive` until a researcher applies the frozen thresholds,
reviews cost defensibility, and attaches evidence-backed failure assignments.
