# Serialization case analysis

Earliest divergence in both cases is mutation-01: ordinary write_cells followed
by openpyxl save. The prior recalculation firewall has not yet been invoked.
Accepted contracts authorize Here!J2:J6 for 58147 and output!A2:G15 for 61-4.

| Case | Intended changed cells | Unintended scalar changes | Mechanism |
|---|---:|---|---|
| 58147 | 5 formulas in J2:J6 | 134 empty strings at Here!I7:I140 become absent values | shared-string/empty-value normalization during save |
| 61-4 | 42 values, output rows 7–12 | input!H2, H9, H19 change at floating-point precision | numeric serialization round trip |

61-4 exact input changes:

- H2: -1.1999999999999957 → -1.199999999999996
- H9: 0.10000000000000142 → 0.1000000000000014
- H19: -0.10000000000000142 → -0.1000000000000014

There is additional package drift beyond these scalar changes. Ordinary save
changes/removes 17 ZIP entries in 58147 and 21 in 61-4. Some entries are ZIP
directory records with no workbook meaning. Others include shared-string storage,
styles, relationships and workbook metadata. In 61-4, comment/VML parts move and
printer settings disappear; in 58147 custom properties disappear. These cannot
all be dismissed as semantically irrelevant serialization. Full per-entry and
XML diffs are retained in strategy_comparison.json.

The runtime's original preservation evaluator sees scalar differences, so these
two cases fail that gate. The official scorer directly checks only answer cells,
with its own value normalization, after LibreOffice recalculation. An indirect
effect must be tested rather than inferred from those comparison rules.

The fixed-transition replay applies each candidate's approved state to the exact
same initial artifact. Original-file reconstruction with openpyxl reproduces all
134 and 3 external scalar changes. Raw XML reconstruction preserves every one,
as well as untouched metadata and relationships. This is causal evidence about
the serializer, independent of model variability or final benchmark pass rate.

The nearby 47766 and 50971 first mutations remain scalar-preserving under raw
reconstruction. Their prior recalculation regression tests remain active. Full
retained action/evaluation histories are embedded in the offline comparison and
the parent evidence archive remains unchanged.

Failed development trials are preserved: offline/ contains a partial local
recalculation attempt that failed; offline-cached/ contains the first raw-patch
trial where a self-closing XML cell bug removed Here!A6:A7. The differential
oracle detected it. offline-cached-v2/ contains the corrected replay. Cached-only
scores are not reported as canonical official outcomes.

## Canonical verification and final run

All four valid raw reconstructions have zero evaluator-visible differences from
their retained candidate after official recalculation. The retained 58147 and
47766 candidate states pass; 61-4 and 50971 fail. Ordinary and raw candidates
have identical rendered pixels on all nine pages for 58147 and 61-4, as well as
identical extracted text. Metadata drift is therefore not visibly consequential
in these rendered cases, but is still prevented by reconstruction.

In the fresh 20-task Arm D run, all four named cases remain preservation-safe,
and the independent audit finds zero violations across the complete task set.
The overall gate nevertheless fails: official success falls to 6/20. The lost
tasks and their distinct pre-action, authorization and evaluator-driven
regression mechanisms are documented in PRESERVATION_GATE.md. They are not
reclassified as serialization failures.
