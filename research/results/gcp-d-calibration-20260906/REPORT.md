# Arm D completion-calibration rerun

## Conclusion

The focused policy improved completion recognition while state-production success
remained stable. `FULFILLED` precision increased from 50% to 100%, FFR fell from
50% to 0%, and explicit false-unfulfilment fell from 38.9% to 21.4%. The official
pass rate remained 40%. This supports the completion-calibration hypothesis on
this development sample, but does not establish generalization.

The full A/B/C/D rerun is **not authorized by the decision gate**: two runs had
detected preservation violations versus one previously. Neither violating run was
declared fulfilled, and no artifact corruption occurred, but the literal
no-increase condition was not met. Provider nondeterminism also caused three
official gains and three losses despite unchanged aggregate pass rate.

## Separate capability metrics

| Capability | Prior uncapped D | Calibrated D | Interpretation |
|---|---:|---:|---|
| State production: official pass | 40.0% (8/20) | 40.0% (8/20) | stable aggregate; task identities drifted |
| State production: cell accuracy | 16.74% | 16.02% | -0.72 percentage points |
| Recognition: FULFILLED precision | 50.0% (1/2) | 100% (2/2) | material improvement |
| Recognition: FULFILLED recall | 12.5% (1/8) | 25.0% (2/8) | improved |
| Recognition: FFR | 50.0% | 0% | observed false claim eliminated |
| Recognition: false-unfulfilment | 38.9% (7/18) | 21.4% (3/14) | unsupported negatives reduced |
| Recognition: UNKNOWN | unavailable | 20.0% (4/20) | 3 external PASS, 1 external FAIL |
| Reconciliation: recovery yield | 25.0% (2/8) | 33.3% (2/6) | remains non-zero |

The two trustworthy `FULFILLED` claims were tasks `50526` and `59794`; both
passed official evaluation. There were no false fulfilments. The UNKNOWN cases
were `105-24` (external PASS), `31011` (PASS), `49237` (PASS), and `45738`
(FAIL). This is the intended epistemic behavior: the status does not assert the
external outcome.

## Paired state-production drift

- Newly passing: `49237`, `50526`, `58147`.
- Newly failing: `168-17`, `35742`, `37554`.
- Passing in both: `105-24`, `120-24`, `31011`, `47766`, `59794`.

Because the policy does not change actions or planning, these symmetric task
swaps are evidence of provider/run variance, not a demonstrated production effect.

## Resources

| Measure | Prior | Current | Change |
|---|---:|---:|---:|
| Actions | 34 | 36 | +5.9% |
| Iterations | 45 | 45 | 0% |
| Tokens | 1,607,987 | 1,743,803 | +8.4% |
| Runtime latency | 436.6 s | 495.0 s | +13.4% |
| Estimated model cost | $1.3001 | $1.3975 | +7.5% |

Current means were 87,190 tokens, 1.8 actions, 2.25 iterations, 24.75 seconds,
and $0.0699 per task. One task hit the operational emergency ceiling.

## Failure diagnosis

Dominant failures remain upstream of completion recognition: seven no-progress
terminations, four contract-schema/procedural rejections, two no-safe-transition
negatives, one missing-sheet execution error, one malformed capability request,
and one emergency-ceiling event. Two preservation violations were detected and
correctly prevented from becoming fulfilment claims.

The bottleneck is therefore a combination:

1. **Evaluation/observation** was the dominant recognition bottleneck and was
   materially improved by coverage-aware three-valued completion.
2. **Contract specification and state production** now dominate remaining task
   failures; the rerun had four contract rejections and only 40% external success.
3. **Reconciliation** still works (two recoveries) but no-progress remains common.

Machine-readable task pairing is in `paired_analysis.json`; full artifacts,
contracts, traces, checkpoints, grader results, aborted pilot evidence, and
infrastructure records are in the checksum-verified archive.
