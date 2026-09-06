# Preservation case analysis

## Result

The two preservation violations observed at commit `9892ff1` shared one root
cause: a successful LibreOffice recalculation rewrote cells outside the contract's
authorized answer selectors while the adapter incorrectly reported the requested
scope as the actual scope. The completion policy did not cause either violation.

| Task | Authorized scope | Earliest violating transition | Observed external effect | Classification |
|---|---|---|---|---|
| `47766` | `Total (2)!K40` | successful `recalculate` after an in-scope write | 32 populated cells in `F8:F65` changed from Excel serial numbers with `General` formatting to date values with `m/d/yyyy` formatting | capability effect/scope-reporting failure; recalculation side effect |
| `50971` | `Sheet1!G3:G13` | successful `recalculate` after in-scope write/fill | `F3:F13` dynamic-array/unique results were corrupted; `F4:F13` became `#NAME?` | capability effect/scope-reporting failure; unsupported-function recalculation corruption |

Both cases passed preservation immediately after their write/fill actions and
failed it immediately after recalculation. The broker evidence claimed only the
authorized cells changed because `_recalculate` returned the requested scopes,
not observed scopes. WorkbookSnapshots independently exposed the wider change.

## Counterfactual comparisons

- In the prior uncapped counterparts, the same recalculation process exited 77
  and copied no converted workbook, so preservation passed. This was accidental
  safety from operational failure, not correct scope enforcement.
- Nearby calibrated recalculation cases `31011`, `50526`, and `58147` completed
  without preservation failures in the `9892ff1` run. Thus recalculation was not
  intrinsically unsafe for every workbook; the defect was failure to inspect and
  authorize its actual effect.
- The accepted contracts explicitly required preservation outside `K40` and
  `G3:G13`. Neither contract authorized source-column mutation.
- Neither task had visual intent, so rendered comparison was not applicable.
  Structured cell values/types/formats, hashes, action traces, evaluator outputs,
  and official results provide the relevant multimodal evidence channels.

## Focused rerun outcome

The intervention eliminated both target violations: `47766` and `50971` ended
with preservation passing. `47766` remained an official PASS and `50971` remained
an official FAIL, matching their prior external outcomes.

The aggregate preservation gate nevertheless failed with two different cases:

- `58147`: an ordinary `write_cells` save normalized 134 pre-existing empty
  strings in `Here!I7:I140` to empty cells. This happened before recalculation and
  is outside the focused recalculation intervention.
- `61-4`: an ordinary `write_cells` save changed three input floats at machine
  precision (`H2`, `H9`, `H19`). This is the previously observed baseline
  serialization class, although stochastic action selection meant it was absent
  from the immediately preceding calibrated run.

These new cases show a second mechanism: openpyxl serialization can change
out-of-scope representations during any workbook save. They do not refute the
causal explanation or efficacy for the two targeted cases, but they prevent the
global decision gate from passing.
