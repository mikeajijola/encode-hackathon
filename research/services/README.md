# Spreadsheet experiment services

`SpreadsheetServices` connects the artifact-neutral four-arm experiment runner to generic contract/discrepancy records, the capability broker, and the XLSX adapter. It preserves the runner's treatment boundaries: A acts directly; B compiles then acts once; C additionally evaluates once; D evaluates and iterates over typed discrepancies.

Runtime context accepts benchmark answer location metadata (`answer_sheet`, `answer_position`) and optional non-golden evaluation metadata such as an expected type. Answer ranges are expanded into explicit cell selectors. Golden-like keys are rejected. A trusted `independent_expected` fixture/source-computation value remains available for deterministic tests and is deliberately removed from compiler and action-model prompts.

Production semantic evaluation uses a separate model call with purpose `independent_evaluation`. It receives only the accepted contract, bounded source observation, and current target facts—not the action response or hidden reasoning. Its strict verdict is `pass`, `fail`, or `uncertain`, with expected state, rationale, and confidence. Malformed output and provider errors become `uncertain` and can never pass. A missing target is an actionable state discrepancy, so D attempts the first bounded mutation before paying for semantic evaluation; C evaluates once after its sole action and never repairs.

Internal checks cover workbook loading, preservation outside authorized cells, nonblank answers, declared types, formula-error values, independent semantics, and rendering for visual intent. Rendering absence is non-passing. Every adapter action passes through broker authorization, hashes, provenance, and evidence; experiment events retain observations, evals, discrepancies, and linked capability effects.

Arm D has no spreadsheet-specific control loop or fulfilment gate. `SpreadsheetServices.reconcile` constructs the generic `FulfilmentAgent`; spreadsheet observer, evaluator, planner, lifecycle, and capability wrappers sit beneath its protocols. The generic agent owns knowledge-driven observation, discrepancy lifecycle, transition validation, broker invocation, re-observation, repeated-transition/no-progress detection, `decide_completion`, and termination. The hash-chained evidence store records the accepted contract, observations, eval results, transitions, capability effects, and final artifact selection. Missing evidence, evaluator errors, or uncertainty therefore remain unfulfilled even when other checks pass.

This is an MVP isolated judge, not a claim that model judgment equals deterministic correctness. Its precision and recall must be measured against offline official outcomes, and uncertain cases remain reliable refusals.

```sh
cd research
PYTHONPATH=. python -m unittest -v tests.test_spreadsheet_services
```
