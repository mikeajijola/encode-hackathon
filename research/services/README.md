# Spreadsheet experiment services

`SpreadsheetServices` connects the artifact-neutral four-arm experiment runner to generic contract/discrepancy records, the capability broker, and the XLSX adapter. It preserves the runner's treatment boundaries: A acts directly; B compiles then acts once; C additionally evaluates once; D evaluates and iterates over typed discrepancies.

Runtime context accepts benchmark answer location metadata (`answer_sheet`, `answer_position`) and optional non-golden evaluation metadata such as an expected type. Answer ranges are expanded into explicit cell selectors. Golden-like keys are rejected. A trusted `independent_expected` fixture/source-computation value can enable an independent semantic assertion, but it is deliberately removed from compiler and action-model prompts. Without such an independent result, the required semantic eval is `uncertain`, so the service returns unfulfilled even if structural checks pass.

Internal checks cover workbook loading, preservation outside authorized cells, nonblank answers, declared types, formula-error values, independent semantics, and rendering for visual intent. Rendering absence is non-passing. Every adapter action passes through broker authorization, hashes, provenance, and evidence; experiment events retain observations, evals, discrepancies, and linked capability effects.

This is an MVP service, not a claim that answer metadata supplies semantic correctness. Real benchmark runs need defensible independent computations/evaluators per task family; otherwise reliable refusal is expected.

```sh
cd research
PYTHONPATH=. python -m unittest -v tests.test_spreadsheet_services
```
