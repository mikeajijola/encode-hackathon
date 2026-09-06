# Focused experiment: coverage-aware three-valued completion

Hypothesis: false completion claims and unsupported negative claims arise because
the binary gate collapses insufficient evidence into failure while permitting a
high-confidence semantic pass over incomplete observations to establish success.

The selected change is intentionally narrow:

- introduce `FULFILLED`, `UNFULFILLED`, and `UNKNOWN` aggregation;
- mark a semantic pass over a truncated source observation as epistemically
  uncertain rather than passing;
- mark formula-source versus computed-result type ambiguity as uncertain rather
  than either passing or failing;
- retain every structural safety gate and every reconciliation/mutation rule.

Offline result on the frozen evidence corpus: FULFILLED precision 100% (1/1),
recall 12.5% (1/8 official passes), FFR 0%, false-unfulfilment 33.3% among explicit
`UNFULFILLED` decisions, and UNKNOWN 65%. Thirteen UNKNOWN decisions split into
seven external passes and six external failures. This is deliberately conservative
and the sample is too small to claim generalization.

Rejected alternatives:

- required-eval quorum captured five of eight passes but accepted three failures
  (62.5% precision, 37.5% FFR);
- semantic-primary achieved only 50% precision;
- strict three-valued aggregation retained the original false fulfilment because
  it ignored evidence coverage.

No official label, mismatch, golden value, or task ID is consulted by runtime
logic. The next valid test is a paired Arm D-only rerun under the frozen protocol.
