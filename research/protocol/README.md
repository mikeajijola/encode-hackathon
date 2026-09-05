# Controlled experiment protocol

This directory freezes the four-arm comparison before held-out runs and provides dependency-free paired analysis. It does not implement fulfilment or read benchmark goldens during a run.

## Files

- `preregistered_experiment.json` fixes the treatment semantics, common budgets, deviations, metrics, breakdowns, statistical method, and unchanged success thresholds. Replace every `TO_BE_PINNED_BEFORE_RUN` value and hash the manifest before execution; any later change is a new protocol version.
- `ledger.schema.json` is the normative JSON Schema for append-only experiment ledger entries. `ledger.template.json` is a starting record. Provenance binds each claim to code, run manifest, evidence root, and scorer.
- `analysis.py` calculates FFR, recovery yield, completion precision/recall, validity, resource overhead, paired pass-rate effects, seeded paired bootstrap intervals, exact two-sided McNemar tests, breakdowns, and failure counts.
- `selection.py` creates deterministic, stratified, hash-verified task manifests from public metadata without resolving reference-answer files. `development_selection.json` is the seed-20260905, 10-cell/10-sheet development split.
- `offline_report.py` joins terminated internal runs to official evaluator results by exact task ID, then emits JSON statistics and the required four-arm Markdown table. This is the only stage that consumes official outcomes.
- `failure_assignment.schema.json` requires evidence-linked, multi-label failure classifications. `REPORT_TEMPLATE.md` prevents missing reliability, overhead, and validity reporting.

Generate a split without inspecting answers:

```sh
cd research
python -m protocol.selection --dataset-json data/spreadsheetbench_verified_400/dataset.json \
  --out protocol/development_selection.json --cell 10 --sheet 10 --seed 20260905
```

Generate the offline report only after all runs and official scoring have terminated:

```sh
python -m protocol.offline_report --inputs four_arm_inputs.json \
  --selection protocol/development_selection.json --out analysis.json --markdown-out arm_table.md
```

Per-task analysis rows require `task_id`, `official_pass`, `internal_status`, and `artifact_valid`. Cell counts and cost fields are additive. For Arm D, `first_mutation_pass=false` identifies the denominator eligible for reconciliation recovery; a final official pass counts as recovered. FFR is failed official runs among runs internally declared `FULFILLED`.

Run the semantic and structural checks from this directory:

```sh
cd research/protocol
python -m unittest -v test_analysis.py
```

Required breakdown fields are instruction level (cell/sheet), task family, mutation count, formula/value, complexity, initial observation size bucket, and reconciliation iterations. Missing values are reported as `unknown`, never silently discarded.

Multimodal protocol validation is N/A: protocol and ledger JSON have no rendered artifact semantics. This does not waive visual evaluation of benchmark tasks; rendered checks belong to the artifact adapter/eval evidence whenever the intent has visual meaning.

## Interpretation guardrails

Use the same task IDs in each compared arm. Provider failures and departures from pinned conditions are recorded as deviations and included in the primary intent-to-treat result; additionally report the preregistered sensitivity analysis. A zero-denominator metric is `null`, not zero. Evaluator errors cannot be converted into passes. Preserve negative and regressive experiment entries in the ledger.
