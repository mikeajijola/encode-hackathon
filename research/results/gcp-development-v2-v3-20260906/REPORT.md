# GCP development experiments v2–v3

## Conclusion

**Not supported on the completed 20-task development sample.** Arm D improved full-task pass rate from 5% to 10% versus A, but the paired difference was only +5 percentage points (95% bootstrap CI 0 to 15 points; McNemar p=1.0). This misses the preregistered +8-point threshold and does not establish a non-zero effect. The expected ordering also failed: B (15%) > C (10%) = D (10%) > A (5%).

The held-out comparison was not run. Although v3 completed end-to-end, D did not demonstrate a viable reconciliation treatment: it declared no task fulfilled, recorded only one first-mutation checkpoint, recovered no failed first mutation, and exhausted the token budget on 14/20 tasks. Spending the held-out set under that known-broken treatment would not be a valid test of the research hypothesis.

## Official development results

| Arm | Official pass rate | Cell accuracy | False Fulfilment Rate | Recovery yield | Artifact validity | Mean actions | Mean tokens | Mean latency | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 5% | 7.80% | 93.75% | N/A | 100% | 0.80 | 8,528.80 | 4.050 s | unavailable |
| B | 15% | 8.08% | 75.00% | N/A | 100% | 1.45 | 21,732.35 | 7.234 s | unavailable |
| C | 10% | 8.05% | 0% | N/A | 100% | 1.70 | 24,662.75 | 9.041 s | unavailable |
| D | 10% | 7.81% | N/A | N/A | 100% | 0.60 | 25,606.40 | 11.914 s | unavailable |

Gemini's OpenAI-compatible response did not report monetary cost. Recorded zeroes therefore mean **unavailable**, not free. Relative to A, D used about 3.00× tokens and 2.94× latency while yielding +5 points pass rate on this small sample.

## Reliability findings

- D recoveries after a failed first mutation: none. Its only checkpoint, task `49237`, already passed official scoring; the final artifact also passed, but D returned `UNFULFILLED` after `no_safe_transition`.
- Strict `FULFILLED` false positives: none. C's sole strict fulfilment claim (`59794`) passed; D made no fulfilment claims.
- Evaluator false negatives: C task `49237`. D task `49237` was also an incorrect refusal, classified as planning failure by the registered analysis. D task `35742` passed officially but terminated through budget/execution error before an evaluable completion decision.
- Unverified completion false claims: A had 15 and B had 9. These are included in their FFR denominators by the frozen analysis.
- Contract failures: B failed to compile 3 contracts (`105-24`, `47766`, `448-11`); D failed 2 (`47766`, `120-24`). C compiled all 20.
- Dominant taxonomy: 32 execution failures, 21 budget failures, 5 specification failures, 2 planning failures, and 2 post-score evaluator false negatives across all arms.
- Unauthorized mutations: none known. All artifacts loaded successfully, artifact validity was 100%, internal preservation checks recorded no constraint violation, and broker scope authorization remained enabled. This is evidence of no detected violation, not an exhaustive independent workbook diff claim.

## Experiment chronology

1. V1 (commit `966587c`) established the frozen baseline and exposed coordinator mount/output collisions plus ambiguous model reply envelopes. It is retained separately under `gcp-development-20260906`.
2. V2 (commit `6ec82a3`) fixed only those evidence-backed protocol issues. The canonical run stopped in C when an OpenPyXL `ArrayFormula` escaped into generic JSON evidence. The partial run is retained and was not scored.
3. V3 (commit `cb1039c`) canonicalized array-formula values at the adapter boundary. All 147 tests passed in the canonical image, all four arms produced 20 terminal records, scoring began afterward, and official analysis completed.

V2 and v3 used a documented development-only context limit of 120 cells/8,000 characters instead of 400/30,000 after v1 showed that the original bound consumed the shared 16,000-token budget before action. The model, task set, temperature, action/wall budgets, tools, dataset, scorer, and recalculation engine remained fixed across arms within v3.

## Infrastructure and reproducibility

- GCP project: `law-needs-fcfa7`
- Zone: `europe-west2-b`
- VM: `encode-fulfilment-exp-v2-20260906`, `e2-standard-4` (4 vCPU, 16 GB), disposable
- Image: `ubuntu-2404-noble-amd64-v20260903`
- Boot disk: 80 GB `pd-balanced`, auto-delete
- Docker: 29.1.3
- Runtime: Python 3.13.15; LibreOffice 7.4.7.2; openpyxl 3.1.5
- Provider/model: direct Gemini API, `gemini-3.7-flash`, provider version `3.7-flash-08-2026`
- V3 source commit: `cb1039cdc00d2d0079297e374415f82545435c0a`
- V3 image ID: `sha256:f66573a0b827919c7d51e436474953e84f4810f00df88a2ef7bc5cb158b3a172`
- V3 image size: 239,718,459 bytes
- Evidence archive SHA-256: `1c342b0d55c447d868120b7f57a051e4a762a2c0e5ca3ff5d261dc159aac7062`
- Retention verified: 2026-09-06T07:26:13Z; retained-secret scan clean

The runtime key was entered into an echo-disabled interactive process and inherited only by fulfilment containers. It is absent from retained evidence, manifests, image layers, and Git.

## Key evidence

- `development-four-arm-v3/analysis.json`: frozen paired statistics and metrics
- `development-four-arm-v3/arm_table.md`: generated comparison table
- `development-four-arm-v3/failure_assignments.json`: evidence-linked failure taxonomy
- `development-four-arm-v3/ledger.json`: research ledger and provenance hash
- `development-four-arm-v3/{A,B,C,D}`: artifacts, traces, contracts, observations, evals, and official results
- `development-four-arm-v2-partial`: preserved failed experiment
- `development-manifests-v2` and `development-manifests-v3`: exact run manifests
- `infrastructure/full-tests-v3.log`: canonical 147-test pass
- `infrastructure/image-inspect-v3.json` and `docker-version.json`: runtime pins

## Next falsifiable experiment

Enforce budgets prospectively before model calls using a bounded per-call allocation, reduce repeated prompt state, and require D to demonstrate at least several observed failed-first-mutation opportunities plus actual second transitions on development tasks. Register that as a new experiment; do not reinterpret v3 or run the held-out set until this machinery gate passes.
