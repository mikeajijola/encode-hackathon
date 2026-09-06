# Completion-error case analysis

## False fulfilment

Task `45738` was the sole false `FULFILLED`. Every required internal gate passed.
The decisive semantic evaluator inspected formula strings and asserted semantic
correctness at confidence 1.0. Runtime-legal coverage evidence showed only 177
serialized cells and 915 omitted non-empty source cells. No independent formula
execution or expected-value derivation established the computed property.

Diagnosis: evaluator false positive caused by inadequate observation coverage and
partially coupled semantic evidence. Artifact validity, preservation, nonblank,
type, shape, and absence of new formula errors could not detect the semantic
defect. The generic missing capability is coverage-attested independent semantic
evaluation, not access to benchmark answers.

## False unfulfilments

Seven official passes were labelled `UNFULFILLED`:

| Task | Blocking gates | Epistemic diagnosis |
|---|---|---|
| 105-24 | type, semantic | truncated observation; correctness not established either way |
| 120-24 | nonblank, type, semantic | gates treated contract-permitted/conditional blanks as unconditional failure |
| 168-17 | nonblank, type, semantic | same over-strict target-wide checks |
| 31011 | type | formula source compared with required numeric result; source coverage truncated |
| 35742 | type | formula source compared with required numeric result; source coverage truncated |
| 37554 | type | formula source compared with required numeric result |
| 47766 | type | formula source compared with required numeric result; source coverage truncated |

Five of seven therefore have a directly identifiable epistemic blocker under the
selected policy and become `UNKNOWN`, not `FULFILLED`. The two nonblank/semantic
cases remain negative because the current evidence explicitly reports required
target-state failures. They need a better contract-sensitive evaluator, not a
looser completion rule.

The earlier six-task type-gate loosening experiment is contrary evidence against
permissiveness: it created two false fulfilments, improved no artifact, and was
reverted. The focused change therefore changes the meaning of uncertainty without
accepting formula/source disagreement as success.
