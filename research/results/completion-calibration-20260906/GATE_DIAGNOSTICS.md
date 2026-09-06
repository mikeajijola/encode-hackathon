# Evaluator and completion-gate diagnostics

Corpus: 20 final Arm D states from the uncapped development run. Official labels
were joined only after each offline policy emitted its decision. Four tasks had no
terminal eval set because execution ended before terminal evaluation; these are
reported as not applicable, never as passes.

| Rank | Gate | Pass / fail / error / N/A | P(external PASS \| gate PASS) | P(external FAIL \| gate FAIL) | FP contribution | FN contribution | Independence |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | preservation | 15 / 1 / 0 / 4 | 53.3% | 100.0% | 7 | 0 | independent deterministic |
| 2 | artifact-valid | 16 / 0 / 0 / 4 | 50.0% | n/a | 8 | 0 | structurally independent |
| 3 | formula-errors | 16 / 0 / 0 / 4 | 50.0% | n/a | 8 | 0 | structurally independent |
| 4 | output-shape | 16 / 0 / 0 / 4 | 50.0% | n/a | 8 | 0 | structurally independent |
| 5 | nonblank | 10 / 6 / 0 / 4 | 60.0% | 66.7% | 4 | 2 | structurally independent |
| 6 | semantic | 8 / 7 / 0 / 5 | 62.5% | 57.1% | 3 | 3 | independent actor; evidence may be partially coupled |
| 7 | type | 6 / 10 / 0 / 4 | 16.7% | 30.0% | 5 | 7 | structural; semantically misapplied to formula results |

Ranking uses discriminatory direction and coverage, not raw pass rate. Structural
validity gates are necessary safety conditions but are weak evidence of semantic
success. The `type` gate is anti-discriminatory in this corpus: seven official
passes failed it, primarily because a formula source was compared with the type
of its computed result.

The semantic gate is not tautological by actor identity—it runs in an isolated
model call—but independence of actor is insufficient. For formula-writing tasks,
it inspected the produced formula text without independently computing its result.
That makes those instances partially coupled. The sole false fulfilment also had
915 omitted non-empty source cells, yet received confidence 1.0.

Machine-readable counts and confidence samples are in
`evaluator_diagnostics.json`.
