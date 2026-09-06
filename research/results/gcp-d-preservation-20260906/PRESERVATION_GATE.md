# Preservation decision gate

## Decision: FAIL — stop

The full A/B/C/D experiment was not run.

| Gate | Result | Evidence |
|---|---|---|
| Preservation violations <= 1 | **FAIL** | 2 (`58147`, `61-4`) |
| FFR remains 0% | PASS | 0/1 FULFILLED claims failed |
| FULFILLED precision remains 100% | PASS | 1/1 |
| Official artifact validity remains 100% | PASS | 20/20 graded, no scorer errors |
| Official pass rate does not materially regress | PASS | 45% vs 40% (+5 pp) |
| Causal support rather than aggregate movement | PASS for targeted mechanism | both original failures arose immediately after successful recalculation and both were removed |

Completion calibration was preserved exactly, but stochastic trajectories
reduced FULFILLED recall from 25% to 11.1% (1/9 official passes). UNKNOWN remained
20% (4/20), with three official passes and one failure. False-unfulfilment rose
from 21.4% to 33.3% (5/15). These recognition changes cannot be attributed to the
adapter-only intervention because action/model trajectories also changed.

State production improved from 8/20 to 9/20 and cell accuracy from 16.02% to
16.75%. Recovery fell from 2/6 to 1/7. Resource usage rose from 36 to 39 actions,
1,743,803 to 1,787,729 tokens, 495.0 s to 513.2 s, and estimated $1.3975 to
$1.4647. One task again reached the operational emergency ceiling.

The remaining uncertainty is whether preservation should require exact
representation identity or semantic state identity. The next experiment must
answer that and test a capability-independent transactional scope firewall. No
broader intervention is included in this experiment.
