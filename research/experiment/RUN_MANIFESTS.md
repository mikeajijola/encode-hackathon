# Reproducible SpreadsheetBench run manifests

Generate all four development-arm manifests only after pinning the model release,
container, scorer revision, LibreOffice version, dataset metadata, environment, and
monetary ceiling. The model has no default: pass both flags or set
`EXPERIMENT_MODEL` and `EXPERIMENT_MODEL_VERSION`.

```sh
cd research
python -m experiment.manifests \
  --manifest-dir ../run-input/manifests \
  --run-root ../run-output/development-four-arm-v1 \
  --experiment-id development-four-arm-v1 \
  --model 'PROVIDER/EXACT-MODEL-ID' \
  --model-version 'PROVIDER-REPORTED-IMMUTABLE-VERSION' \
  --container-digest 'sha256:<64 hex characters>' \
  --soffice-version 'LibreOffice <exact version>' \
  --scorer-commit '<full 40-character git commit>' \
  --dataset-metadata-sha256 bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7 \
  --dataset-json ../run-input/dataset/dataset.json \
  --environment 'linux-amd64-python3.13' \
  --max-cost 25.00
```

`TODO`, `latest`, placeholders, malformed hashes, selection/source mismatches, and
reused output paths are rejected. The generator takes temperature, token/action/
wall-clock budgets, and retry policy from the frozen preregistration. Context limits
are fixed at 400 cells/30,000 characters and provider timeout at 120 seconds unless
an explicitly recorded new experiment changes them. Use `--deviation '<reason>'`
for infrastructure deviations; never silently edit one arm.

The generator uses the committed golden-blind development selection at
`protocol/development_selection.json`. Each manifest records its content hash, its
canonical selection hash, the source dataset metadata hash, `uv.lock` hash, protocol
hash, backend factory, container digest, environment, and LibreOffice version.
Rendered/multimodal evaluation remains explicitly delegated to the adapter when the
intent has visual semantics.

Run each arm with the identical image and read-only input mount. Copy the generated
manifests under `run-input/manifests` before mounting:

```sh
IMAGE='fulfilment-experiment@sha256:<same digest recorded above>'
for ARM in A B C D; do
  docker run --rm \
    -e OPENROUTER_API_KEY \
    -v "$PWD/run-input:/data:ro" \
    -v "$PWD/run-output/development-four-arm-v1/$ARM:/out" \
    "$IMAGE" run --manifest "/data/manifests/$ARM.json" --out-dir /out
done
```

Every arm directory is created empty. The experiment runner additionally refuses a
non-empty directory. Score outputs only after all fulfilment runs finish; goldens
must not be present in manifests, prompts, contracts, or fulfilment-time evals.
