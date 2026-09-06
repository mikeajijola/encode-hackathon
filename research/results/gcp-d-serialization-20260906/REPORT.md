# Serialization preservation experiment

The scoped reconstruction eliminates the observed preservation failure class,
but the programme gate fails on overall task success. Stop before A/B/C/D.

| Metric | Parent c70e0b5 | Transactional firewall |
|---|---:|---:|
| Official task pass rate | 45.0% (9/20) | 30.0% (6/20) |
| Cell accuracy | 16.75% | 15.45% |
| Preservation violations | 2 | 0 |
| Valid official artifacts | 100% | 100% |
| FULFILLED precision | 100% (1/1) | 100% (1/1) |
| FFR | 0% | 0% |
| FULFILLED recall | 11.1% | 16.7% |
| False-unfulfilment rate | 33.3% | 18.75% |
| UNKNOWN rate | 20% | 15% |
| Final recovery yield | 14.3% (1/7) | 0% (0/6) |
| Mean actions/task | 1.95 | 1.85 |
| Mean iterations/task | 2.55 | 2.40 |
| Mean tokens/task | 89,386 | 84,232 |
| Mean latency/task | 25.66 s | 25.36 s |
| Estimated model cost/task | $0.07324 | $0.06724 |

The number of correctly recognized successful artifacts stays at one. Higher
recall and lower false-unfulfilment rate therefore do not demonstrate improved
recognition: fewer correct artifacts were produced. Recognition remains
conservative and observed FULFILLED claims remain correct, with very low sample
size. The pure three-valued completion implementation and official evaluator are
byte-unchanged from the parent.

## Preservation and strategy evidence

An ordinary save changes 134 unrelated empty strings in 58147 and three input
floats in 61-4. Rebuilding from the original with openpyxl reproduces the drift.
OOXML tree transplantation preserves those cells but produces an invalid style
reference in 47766. The selected raw XML value reconstruction preserves all
out-of-scope cells across the four fixed case replays, and changes only one
worksheet package member per replay. It retains original styles, metadata,
relationships, merges and untouched cell representations.

After official recalculation, all valid strategies produce identical scored
values to the retained candidate in each case. 58147 and 47766 pass; 61-4 and
50971 fail. The byte/package identity requirement is therefore unnecessary for
the current official scorer. Representation preservation is used conservatively
to preserve workbook meaning; empty strings and tiny numeric changes are not
universally declared semantically equivalent.

Nine rendered pages across 58147 and 61-4 are pixel-identical between ordinary
and reconstructed candidates at 1600-pixel maximum dimension. Extracted full
text and page counts also match. Rendering verifies these retained states only;
it does not prove every future workbook feature is supported.

The final 20-artifact audit independently finds zero out-of-scope semantic
changes. Original 47766 and 50971 recalculation regressions remain fixed. All
mutation checkpoint hashes match their events. The actual live recalculation
probe succeeds through the generic broker and reconstruction path.

## Production, recovery and remaining uncertainty

The paired pass difference is -15 points, 95% bootstrap CI [-35, +5], exact
McNemar p=0.375. Two lost passes are pre-action schema failures under identical
compiler prompts. One is a rejected out-of-scope proposal. The remaining loss,
120-24, reaches correct intermediate states and then regresses after generic
blank/type gates and a deferred semantic check produce misleading discrepancies.
See PRESERVATION_GATE.md and causal_comparison.json for the causal evidence.

There are 12 tasks with >=1 genuine cycle, five with >=2, and three with >=3.
Median cycles/task is one and median tokens/cycle is 27,220. One task reaches the
250,000-token operational emergency ceiling; it is reported separately from the
research resource policy, which has no fixed task token ceiling for D.

## Resource accounting

The valid run uses 1,684,637 tokens, 37 actions, 48 iterations and 507.224 seconds
of summed task latency. Estimated model cost is $1.34475 using the frozen pricing
constants, not an independently verified billing total. Amortized across all six
successful artifacts, this is 280,773 tokens and $0.22412 per success, versus
198,637 tokens and $0.16275 in the parent. The original mechanism report also
includes conditional averages over successful tasks; these are distinct metrics.

The excluded default-home setup trial retains three completed task records and
17 completed model calls: 259,903 input and 7,901 output tokens (estimated $0.22456).
Two connectivity probes add only eight tokens in total. VM provisioning, test
setup and scoring overhead is retained separately; actual GCP billing is not
available. No task outcomes from the excluded trial informed the intervention.

## Conclusion

Evidence supports the narrow transactional preservation mechanism. It does not
support proceeding to a full four-arm comparison. The remaining bottleneck is
a combination of contract compilation/authorization, evaluator applicability,
and reconciliation that can regress a correct state. The architecture is not
disproved by this experiment, and the observed production decline must not be
hidden behind the improved preservation metric. No further intervention was
implemented after the gate failed.
