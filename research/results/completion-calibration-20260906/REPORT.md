# Completion calibration: offline development analysis

This analysis was performed on retained runtime evidence. `runtime_features.jsonl`
contains no official labels or grader mismatches. `external_labels.jsonl` contains
only candidate IDs and post-run PASS/FAIL labels. The join occurs offline.

## Candidate-policy comparison

| Policy | Precision | Recall | FFR | False-unfulfilment | UNKNOWN | Passes captured | Failures accepted |
|---|---:|---:|---:|---:|---:|---:|---:|
| legacy_strict_binary | 50.0% | 12.5% | 50.0% | 38.9% | 0.0% | 1 | 1 |
| strict_three_valued | 50.0% | 12.5% | 50.0% | 53.8% | 25.0% | 1 | 1 |
| coverage_aware_three_valued | 100.0% | 12.5% | 0.0% | 33.3% | 65.0% | 1 | 0 |
| independent_semantic_primary | 50.0% | 25.0% | 50.0% | 33.3% | 50.0% | 2 | 2 |
| required_eval_quorum | 62.5% | 62.5% | 37.5% | 0.0% | 55.0% | 5 | 3 |

## Selected hypothesis

Use three-valued aggregation and require adequate observed-source coverage before
an independent-semantic PASS can authorize `FULFILLED`. Missing, truncated, or
uncertain evidence yields `UNKNOWN`; proven semantic/safety failure yields
`UNFULFILLED`. This is generic, gold-free, and does not loosen a failing gate.

The corpus is only 20 tasks, so policy selection is evidence-directed rather than
an optimization claim. The policy specifically tests the observed failure mode:
high-confidence semantic judgment over incomplete evidence.
