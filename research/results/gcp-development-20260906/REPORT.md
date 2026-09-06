# GCP development experiment — 2026-09-06

## Outcome

The frozen 20-task stratified development experiment did **not** validate the
research hypothesis and did not satisfy the gate for a held-out run. All four arms
failed before any artifact mutation. This is a useful falsification result about
the current implementation, not evidence that declarative reconciliation itself is
ineffective.

| Arm | Official pass rate | Cell accuracy | False Fulfilment Rate | Recovery yield | Artifact validity | Actions | Tokens | Latency | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.00% | 7.63% | N/A | N/A | 100.00% | 0.00 | 13,778.05 | 5,898.95 ms | unavailable |
| B | 0.00% | 7.63% | N/A | N/A | 100.00% | 0.00 | 10,136.45 | 4,075.75 ms | unavailable |
| C | 0.00% | 7.63% | N/A | N/A | 100.00% | 0.00 | 10,127.85 | 4,304.45 ms | unavailable |
| D | 0.00% | 7.63% | N/A | N/A | 100.00% | 0.00 | 10,149.90 | 4,531.30 ms | unavailable |

The Gemini OpenAI-compatible response did not report monetary cost, so the stored
numeric zero is “not reported,” not evidence of zero spend. D used 3,628.15 fewer
tokens and 1,367.65 ms less recorded model latency per task than A only because it
failed earlier; these differences are not meaningful reconciliation overhead.

## Failure findings

- A: 16 specification/JSON-shape failures and 4 token-budget failures.
- B, C, and D: 17 specification/JSON-shape failures and 3 token-budget failures
  each.
- All 80 task runs were classified as execution failures and returned unchanged
  artifacts. No task reached a capability action.
- D recoveries: none; no D task produced a first mutation.
- False fulfilments: none observed, but FFR is N/A because no arm declared any task
  fulfilled.
- Evaluator false positives/negatives: none observable because C and D never reached
  terminal evaluation.
- Contract failures: all 20 tasks in B/C/D failed contract compilation or exhausted
  budget during that stage.
- Unauthorized mutations: none; action count was zero and output preservation hashes
  match.
- Budget exhaustion: A=4 tasks; B=3; C=3; D=3.

The dominant defect is that Gemini 3.7 Flash responses were not accepted as exactly
one JSON object by the frozen response parser. Some responses consumed the entire
16,000-token budget. Because this prevented mutation and evaluation, the four-arm
comparison is experimentally inconclusive about the architectural hypothesis and
fails the preregistered primary criterion.

## Canonical-environment findings

- Frozen source: `966587cd00f8c99bd585da9350f27cbfa5aa4545`.
- Canonical image: `sha256:bde7274371934adcbb145217360ef89997f8471695e50e6e9ff99e56265df217`.
- The complete suite passed in the canonical runtime with ephemeral test-only Git
  and pytest tooling: 151 tests plus 22 subtests.
- Judge-style read-only `/data` and writable `/out` preflight passed.
- Direct Gemini connectivity for `gemini-3.7-flash`, provider version
  `3.7-flash-08-2026`, passed inside the image.
- Official scoring completed with zero scorer errors. All 80 output workbook hashes
  were unchanged by scorer-side LibreOffice recalculation.
- The golden-blind fulfilment input contained 20 initial workbooks and zero files
  whose names contained `golden`. Official scoring began only after all arms had
  terminated.

Two outer-orchestration defects were also falsified in the frozen code:

1. The coordinator mounts manifests at `/manifests`, but the canonical entrypoint
   accepts them only beneath `/data`, producing `manifest_outside_data`.
2. The canonical entrypoint writes `/out/preflight.json` before invoking a runner
   that requires an empty `/out`, producing `output directory must be empty`.

The experiment therefore used the same frozen digest-pinned image and treatment
implementation through `experiment.cli` after a separate passing preflight. Scoring
was manually sequenced in fresh containers after all four arms terminated. These
deviations are retained in the ledger and infrastructure logs.

## Infrastructure and retention

- Project/zone: `law-needs-fcfa7`, `europe-west2-b`.
- VM: `e2-standard-4` (4 vCPU, 16 GB), Ubuntu 24.04 image
  `ubuntu-2404-noble-amd64-v20260903`.
- Disk: 80 GB balanced persistent disk, auto-delete; peak observed use was about
  4.1 GB and memory remained well below 1 GB during sampled execution.
- Docker: 29.1.3; Python: 3.13.15; LibreOffice: 7.4.7.2.
- VM created at `2026-09-06T00:08:11Z` and deletion verified at
  `2026-09-06T06:41:12Z`.
- The VM and disk were deleted after 460 retained files passed SHA-256 verification.
- Secret audit found no Gemini key material in retained files.

Raw outputs and evidence are under `evidence/`. The authoritative generated analysis
is `evidence/development-four-arm-v1/analysis.json`; infrastructure configuration is
`evidence/infrastructure/provisioning.json`; the full file checksum manifest is
`evidence-file-sha256.txt`.

## Decision

Do not run the preregistered held-out set. The next experiment should first address
the general provider-response/structured-output boundary and the two canonical
orchestration contradictions, then register a new development run. Any such changes
must be evaluated as a new experiment and must not tune against held-out tasks.
