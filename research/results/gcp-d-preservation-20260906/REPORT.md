# Focused preservation experiment

The focused intervention removed both preservation violations diagnosed in the
`9892ff1` calibration run, while official pass rate increased from 40% to 45%,
FFR stayed 0%, FULFILLED precision stayed 100%, and all official artifacts stayed
valid. However, the decision gate failed because two different save-time
serialization violations appeared. Therefore no full A/B/C/D rerun was run.

| Metric | `9892ff1` | Treatment |
|---|---:|---:|
| Official pass rate | 40.0% | 45.0% |
| Cell accuracy | 16.02% | 16.75% |
| FULFILLED precision | 100% | 100% |
| FULFILLED recall | 25.0% | 11.1% |
| False Fulfilment Rate | 0% | 0% |
| False-unfulfilment | 21.4% | 33.3% |
| UNKNOWN rate | 20% | 20% |
| Recovery yield | 33.3% | 14.3% |
| Preservation violations | 2 | 2 |
| Valid official artifacts | 100% | 100% |
| Actions | 36 | 39 |
| Tokens | 1,743,803 | 1,787,729 |
| Latency | 495.0 s | 513.2 s |
| Estimated cost | $1.3975 | $1.4647 |

State production improved by one task, recognition remained truthful but less
recallful under stochastic trajectories, and recovery remained non-zero. The
specific recalculation scope defect was fixed; generic save-time scope enforcement
is the next unresolved preservation capability.

See the four `PRESERVATION_*.md` reports for causal detail, the JSON comparison
and ledger for machine-readable results, and the checksum-verified archive for
contracts, workbooks, checkpoints, traces, evaluator outputs, timings, and costs.
