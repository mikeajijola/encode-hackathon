# Evaluator-independence classification

| Evaluator | Class | What it establishes | Limitation |
|---|---|---|---|
| artifact-valid | structurally independent | artifact loads | not semantic correctness |
| preservation | independent deterministic | out-of-scope state unchanged | authorized-scope errors invisible |
| nonblank | structurally independent | target cells populated | may be stricter than conditional contracts |
| type | structurally independent | stored representation type | formula source is not computed-result type |
| output-shape | structurally independent | target cardinality | not target values |
| formula-errors | structurally independent | no newly visible error values | does not independently compute all formulas |
| semantic | independent semantic / partially coupled | isolated model interpretation | formula-text inspection can self-confirm the action |
| visual | independent semantic | rendered presentation | only present for visual intent |

An isolated evaluator model is an independent actor but not automatically an
independent method. For formula transitions, independence requires a separate
calculation path or metamorphic execution, not agreement that the generated
formula looks plausible. Evaluator metadata now records both independence class
and evidence adequacy.
