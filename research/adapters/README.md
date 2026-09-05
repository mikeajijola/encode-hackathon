# Artifact adapters

Adapters implement artifact mechanics beneath the generic capability broker. The spreadsheet adapter exports six versioned capabilities: inspect, bounded cell writes, relative formula fill, recalculation, validation, and range-associated rendering.

Selectors are explicit `Sheet!A1` or `Sheet!A1:B2` values and translate to generic `workbook/<sheet>/<coordinates>` scopes. Mutation handlers independently check that every resolved selector exactly matches the request scope. `WorkbookSnapshots` supplies broker before/after hashes and translates actual value/formula changes into cell-level generic scope diffs.

Inspection returns a canonical observation envelope with direct facts separate from interpretations, exact inspected scopes, and workbook wildcard scopes marking unobserved content. It does not infer desired state.

`recalculate` and `render_range` use `soffice`/LibreOffice when installed. Absence is a typed, non-passing `capability_missing` result. Rendering currently produces a PDF workbook view associated with the requested range; it does not claim range cropping. Environments without LibreOffice retain deterministic failure coverage, while visual semantics remain blocked until a renderer is installed.

Run adapter and broker integration tests:

```sh
cd research
PYTHONPATH=. python -m unittest -v tests.test_spreadsheet_adapter tests.test_fulfilment_core
```
