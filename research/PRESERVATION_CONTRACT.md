# Preservation contract

Status: definition recorded before remote experiment. The initial uncommitted
draft normalized empty strings and used a 1e-12 numeric tolerance. Review rejected
that draft before any new model run: neither rule proves dependency equivalence.

## Semantic preservation — operative safety contract

For every element outside the authorized mutation scope, the post-mutation
artifact must retain equivalent workbook meaning and state. Equivalence is typed:

- blank cells: absent and empty-string cells are not universally equivalent.
  Dependent formulas can distinguish them. Preserve their original state unless
  equivalence is independently demonstrated for the relevant dependency scope;
- numbers: a tiny round-trip difference is a serialization-drift candidate,
  not proof of semantic equivalence. Preserve the original value exactly when
  dependency-sensitive equivalence is unknown;
- dates/times: Excel serials and typed date/time values are equivalent only when
  they denote the same instant/value; formatting is compared separately;
- formulas: formula text, array/shared range, and formula role must remain equal;
- styles and layout: style properties, dimensions, merges, hidden state, and
  relevant print/view state must remain equal;
- workbook structure: sheet identity/order/visibility and defined names must
  remain equal;
- metadata: workbook/core/custom properties must remain equal, except explicitly
  classified volatile producer timestamps when the mutation engine necessarily
  rewrites them and no contract requires their preservation.

An out-of-scope semantic difference is a preservation violation. Uncertainty or
unsupported inspection is not a pass.

## Representation-level preservation — diagnostic contract

Representation preservation means untouched OOXML package parts, XML nodes, ZIP
members, relationships, and binary payloads remain byte-identical. It is measured
for every mutation but is not the operative benchmark contract unless either:

1. the user/contract explicitly requires representation identity; or
2. a representation change alters semantic state, rendering, interoperability,
   validity, or evaluator-visible output.

Package drift alone is recorded, not silently treated as semantic failure.

## Evaluator-visible preservation — benchmark integration contract

The official evaluator recalculates the submitted workbook with LibreOffice,
loads it with `data_only=True`, and compares only task-declared answer cells. It:

- treats `None` and `""` as equal;
- rounds numeric values to two decimal places;
- converts datetimes to Excel serial-day values;
- does not compare untouched cells, styles, merges, metadata, or package bytes.

The scorer does not directly inspect `58147`'s unrelated empty strings or
`61-4`'s input floats. Indirect propagation into answer cells must be checked by
offline recalculation before claiming these changes are evaluator-invisible.
Representation identity is not required by the current benchmark. This does not authorize semantic corruption
outside answer cells: internal preservation remains broader than official scoring.

## Enforcement decision

The transactional firewall must authorize using semantic scope, record package
scope independently, and report evaluator-visible scope as a third projection.
It must commit only when all semantic changes are authorized and the artifact is
valid. The existing strict preservation/completion evaluator remains unchanged.
For current value/formula mutators, scoped reconstruction retains untouched
representations as a conservative implementation of semantic preservation.
This is not a new byte-equality requirement imposed by the benchmark.

## Inspection limits

The structured oracle covers cells, resolved styles, merges, dimensions, sheet
order/visibility, selected core properties and defined names. It is not a complete
OOXML semantic interpreter. Package diffs therefore remain mandatory evidence.
The chosen raw patch retains every non-target XML byte and every other package
member, covering unsupported metadata, drawings, validations and relationships
by preservation rather than by claiming to understand them. Shared-formula
groups and changed target styles are unsupported reconstruction cases and fail
closed. Cached-value diffs are explicitly provisional until offline recalculation.
