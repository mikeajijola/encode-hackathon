# Preservation intervention

## Hypothesis

If spreadsheet recalculation independently derives its actual cell-level effect
and transactionally restores the original artifact whenever that effect exceeds
the requested scope, the two observed recalculation preservation violations will
disappear without changing three-valued completion calibration.

## Single change

Commit `a63b5b1` changed only the spreadsheet adapter's recalculation boundary:

1. retain the exact pre-action workbook bytes;
2. snapshot canonical cell values before and after LibreOffice conversion;
3. derive actual changed-cell scopes from that diff;
4. compare actual scopes with requested scopes;
5. restore the exact original bytes and return a typed scope violation on any
   unauthorized effect;
6. report observed scopes rather than echoing requested scopes.

No completion aggregation, evaluator threshold, contract compiler, planner,
prompt, model, official evaluator, evidence schema, or reconciliation rule was
changed.

## Tests

Regression tests reproduce both causal shapes: out-of-scope date coercion and an
out-of-scope `#NAME?` formula error. Both assert byte-identical rollback and
evidence of the attempted external scope. A representative requested-only
recalculation asserts that safe effects still commit. The complete suite passed:
169 tests plus 24 subtests locally; the canonical unittest path also passed.

## Finding

The intervention worked for the two pre-specified targets, but the rerun exposed
the same trust-boundary flaw in `write_cells`: saving through openpyxl normalized
unrelated empty strings and floating-point representations. Broadening the patch
after seeing the result would violate the focused protocol, so it was not done.

The next discriminating experiment should move observed-scope verification and
byte rollback to the generic post-mutation broker/snapshot boundary for *all*
mutating capabilities. Before doing that, it should pre-register whether
semantic equivalence (`""` versus empty; numerically equal floats within a
serialization tolerance) counts as preservation or whether byte/representation
identity is required. This separates real unauthorized state changes from an
over-sensitive preservation evaluator.
