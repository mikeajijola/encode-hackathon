# Controlled Arm A v2 characterization

Arm A v2 is the direct control used by `experiment.runner` with `SpreadsheetServices`. It is deliberately named v2 because it is **not identical** to the legacy `baseline/llm_predict.py` implementation or its published reference numbers.

## Frozen behavior

Arm A v2 receives the same natural-language instruction, bounded initial workbook observation, answer range metadata, capability availability, model/version, temperature, budgets, retry policy, and environment used by the other experimental arms. It makes one action-generation decision and permits one bounded brokered mutation. It does not compile a declarative contract, run internal evals, or reconcile.

A successful one-shot mutation is projected as `FULFILLED_UNVERIFIED`, termination reason `one_shot_completed_unverified`. This is an explicit completion claim and therefore belongs in the false-fulfilment denominator. Errors and failed actions are `UNFULFILLED`. `FULFILLED_UNVERIFIED` must never be presented as evidence-gated fulfilment.

## Differences from the legacy baseline

| Dimension | Legacy baseline | Controlled Arm A v2 |
|---|---|---|
| Workbook context | Value-only tabular serialization, 120x30 per sheet | Bounded canonical cells including formula text, type and number format |
| Model output | Typed answer-cell value list | `writes` action proposal |
| Mutation | Direct OpenPyXL target-cell writes | Scope-authorized capability broker write |
| Trace/budgets | One trace; no shared enforcement | Shared provider-attempt trace, token/action/time/cost enforcement |
| Failure claim | Prediction status `ok` or error | Explicit `FULFILLED_UNVERIFIED` or `UNFULFILLED` |

Legacy scores are context only and cannot serve as Arm A v2 observations. Comparing v2 against B/C/D is defensible only after freezing the shared action schema and context; the extra contract/eval/reconciliation operations are then the intended treatment differences. Any comparison with the legacy baseline must be reported as a separate harness ablation.
