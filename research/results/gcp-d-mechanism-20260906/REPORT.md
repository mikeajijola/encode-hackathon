# Arm D uncapped-token mechanism validation

## Policy

This is a new revision. It does not overwrite the prior **fixed-budget development experiment — 16,000 tokens/task**. Arm D has no research token budget; token use is measured cost. A separate 250,000-token operational emergency ceiling is reported independently. The frozen 20-task development selection was used. Held-out data was not used.

## Result

- Official pass rate: 40.0%
- Tasks with >=1 / >=2 / >=3 genuine cycles: 14 / 4 / 1
- Median genuine cycles/task: 1.0
- Median tokens/genuine cycle: 23,384
- Recoverable first-attempt failures: 8
- Successful recoveries: 2
- Recovery yield: 25.0%
- False fulfilment rate: 50.0%
- False unfulfilment rate: 38.9%
- Emergency-ceiling terminations: 1
- Median tokens/task: 47,400.5
- Mean tokens/success: 74,597.5
- Mean tokens/recovery: 70,841
- Mean actions/success: 2.375
- Mean iterations/success: 3.0
- Mean latency/success: 27.668 seconds
- Estimated model cost/success: $0.06123
- Estimated model cost, all 20 tasks: $1.30008

Recovered tasks: 120-24, 37554.

The cost estimate applies Gemini 3.7 Flash introductory paid-tier prices in force on the run date: $0.75 per million input tokens and $3.75 per million output tokens, including thinking. Provider responses reported zero cost, so this is an offline estimate from recorded input/output tokens.

| Arm | Pass rate | Cell accuracy | FFR | False-unfulfilment | Recovery | Valid | Actions | Iterations | Tokens | Latency | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D | 40.0% | 16.74% | 50.0% | 38.9% | 25.0% | 95.0%* | 2.0 median | 2.5 median | 47,400.5 median | 18.978 s median | $1.300 total |

\*One artifact-validity value is unavailable because contract compilation exceeded the operational emergency ceiling before evaluation; all 19 produced/evaluated final artifacts loaded successfully.

## Decision gate

**INVESTIGATE IMPLEMENTATION; do not rerun four arms.** Recovery is non-zero and 19/20 tasks avoided the emergency ceiling, but only four tasks completed two or more genuine cycles, so the requirement that multi-cycle reconciliation operate on most tasks needing it is not met. High false-unfulfilment and false-fulfilment also show evaluator/termination defects.

## Focused defect experiment

Failure inspection found a category error: formula-result contracts compared formula source storage type against the desired result type. A six-task, single-change focused experiment delegated result typing to the independent semantic eval. It changed all six refusals into `FULFILLED` claims and retained four official passes, but also created two false fulfilments. Official success remained 4/6. The change therefore improved completion recall but not artifact reliability, worsened claim precision to 66.7%, and was reverted in commit `fb0ec33`.

## Evidence

`mechanism_analysis_final.json` contains per-task and per-cycle accounting. `focused_analysis.json` contains the focused result. The immutable archive `encode-d-mechanism-evidence-v3.tar.gz` contains all final artifacts, all mutation checkpoints, official scores (including the preserved invalid-path checkpoint scoring attempt), contracts, observations, discrepancies, traces, append-only evidence, hashes, manifests, environment records, and the focused experiment.
