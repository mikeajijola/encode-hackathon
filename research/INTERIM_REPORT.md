# Interim experimental report

Date: 2026-09-05  
Status: implementation validation complete; registered model experiment not run

## Conclusion

The research hypothesis is **inconclusive**. The repository now implements the four preregistered treatments, generic reconciliation semantics, independent evaluation role, evidence reconstruction, paired statistics, and two artifact adapters. Those facts establish experimental readiness, not a SpreadsheetBench treatment effect.

No official A/B/C/D result is reported because this host has no pinned model credential, Docker CLI, or LibreOffice executable. Inventing values or substituting the deterministic synthetic fixture would invalidate the experiment. The synthetic fixture demonstrates only that the harness detects injected false fulfilment and reconciliation recovery.

## Current evidence

- 129 implementation tests pass and 8 protocol/statistics tests pass.
- The unmodified official scorer hash is verified.
- The official oracle check scored 1.0 on all 400 reference artifacts.
- All 400 initial artifacts resolve their public answer selectors with zero errors or duplicates.
- Arm D delegates control flow to the artifact-neutral `FulfilmentAgent`; the spreadsheet layer supplies protocol implementations and broker capabilities.
- A text/config adapter reuses the contract, observation, discrepancy, broker, evidence, completion, and control-loop semantics unchanged.
- Static container checks pass, but an actual image build and LibreOffice smoke test have not run.
- The semantic evaluator is isolated from action output, but uses the same provider/model actor; this limitation must be retained in interpretation.
- Compact formula fill addresses repeated-formula ranges. Large non-formula transformations above the 400-literal-write bound remain a known capability gap.

## Registered result table

`N/A` means not measured; it does not mean zero.

| Arm | Pass rate | Cell accuracy | FFR | Recovery yield | Valid artifacts | Actions | Tokens | Latency | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| B | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| C | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| D | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## Required next execution

On a Docker host with LibreOffice and a funded, pinned provider credential:

1. Build the sole repository-root Dockerfile and retain its immutable digest and preflight report.
2. Generate the four manifests with exact model/version, provider environment, scorer commit, dataset hash, container digest, LibreOffice version, and cost ceiling.
3. Run the same frozen task selection through A/B/C/D.
4. Terminate all fulfilment runs before exposing reference artifacts to the offline scorer.
5. Produce official results, paired bootstrap intervals, McNemar tests, failure assignments, ablations, overhead tables, and an append-only ledger entry.
6. Apply the preregistered thresholds without revision. Report supported, partially supported, rejected, or inconclusive from those measurements.

The machine-readable current gate is [`protocol/FINAL_READINESS.json`](protocol/FINAL_READINESS.json); the detailed limitations and resolutions are in [`VALIDITY_REVIEW.md`](VALIDITY_REVIEW.md).
