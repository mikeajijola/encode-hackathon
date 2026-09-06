# Four-arm fulfilment experiment

## Provisional conclusion

**REJECTED — preregistered primary effect threshold not met**

This report is generated after all fulfilment runs terminate and official scoring completes. It does not expose reference answers to fulfilment.

## Results

| Arm | Pass rate | Cell accuracy | FFR | Recovery yield | Valid artifacts | Actions | Tokens | Latency | Cost |
|---|---|---|---|---|---|---|---|---|---|
| A | 0.0000 | 0.0763 | N/A | N/A | 1.0000 | 0.0000 | 13778.0500 | 5898.9500 | 0.0000 |
| B | 0.0000 | 0.0763 | N/A | N/A | 1.0000 | 0.0000 | 10136.4500 | 4075.7500 | 0.0000 |
| C | 0.0000 | 0.0763 | N/A | N/A | 1.0000 | 0.0000 | 10127.8500 | 4304.4500 | 0.0000 |
| D | 0.0000 | 0.0763 | N/A | N/A | 1.0000 | 0.0000 | 10149.9000 | 4531.3000 | 0.0000 |

## Paired inference

- B_minus_A: effect=0.0000, 95% CI [0.0000, 0.0000], McNemar p=1.0000
- C_minus_B: effect=0.0000, 95% CI [0.0000, 0.0000], McNemar p=1.0000
- D_minus_C: effect=0.0000, 95% CI [0.0000, 0.0000], McNemar p=1.0000
- D_minus_A: effect=0.0000, 95% CI [0.0000, 0.0000], McNemar p=1.0000

## Preregistered criteria

- [ ] `D_minus_A_at_least_8_points`
- [ ] `D_minus_A_95_ci_excludes_zero`
- [ ] `ordering_D_gt_C_gte_B_gte_A`
- [ ] `D_recovery_yield_at_least_20_percent`
- [ ] `D_false_fulfilment_below_5_percent`
- [ ] `D_completion_precision_at_least_90_percent`
- [x] `D_artifact_validity_at_least_99_percent`
- [x] `D_no_known_constraint_violation`
- [x] `overhead_reported`

## Remaining review gates

- Evidence reconstruction: pass
- Cost defensibility: requires_reported_judgment

See `analysis.json` for breakdowns, overhead distributions, failure counts, and exact statistics; see `failure_assignments.json` for evidence-linked examples. Failed criteria must not be waived post hoc.
