# Preservation causal trace

## `47766`

1. Initial hash: `bc56a9f...`; preservation PASS.
2. `inspect_workbook`; no mutation; preservation PASS.
3. `write_cells` changed only `Total (2)!K40`; preservation PASS.
4. `recalculate` changed the artifact hash and was reported as changing only
   `K40`.
5. The next independent observation/evaluation found changes in 32 source date
   cells in column F; preservation FAIL. Later inspect/validate calls had no
   mutation and could not remove the discrepancy.
6. Prior counterpart: step 4 exited 77 and no converted artifact was committed;
   preservation therefore remained true.
7. Focused rerun: the recalculation either failed before commit or was rejected;
   final preservation PASS and official PASS.

Earliest causal divergence: step 4, not contract compilation, completion-state
handling, recovery planning, or the earlier write.

## `50971`

1. Initial hash: `0a36c549...`; preservation PASS.
2. In-scope write to `G3`, then in-scope fill through `G13`; preservation PASS.
3. `recalculate` committed a converted workbook and was reported as changing
   only `G3:G13`.
4. The next evaluation observed `F3:F13` changed; `F4:F13` were `#NAME?`.
   Preservation FAIL and workbook validation later reported formula errors.
5. Prior counterpart: recalculation exited 77 and did not commit a conversion.
6. Focused rerun: no out-of-scope conversion survived; preservation PASS. The
   official output still failed because the chosen formula was not compatible
   with the official recalculation path, an independent state-production issue.

Earliest causal divergence: step 3. The two original cases therefore share the
same causal mechanism even though one change was a date coercion and the other
was semantic corruption.

## Evidence locations

The checksum-verified archive contains, per task, the accepted contract, all
observations/evals/discrepancies, transition decisions, broker requests/results,
mutation checkpoints, artifact hashes, model traces, terminal decision, final
artifact, official score, and checkpoint scores. See
`encode-preservation-evidence.tar.gz` and `evidence_verification.json`.
