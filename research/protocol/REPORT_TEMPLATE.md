# Four-arm fulfilment experiment

Protocol version: <!-- immutable preregistration -->
Run commits and manifest hashes: <!-- one per arm -->
Dataset selection hash: <!-- development or held-out manifest -->

## Result

Conclusion: **SUPPORTED / PARTIALLY SUPPORTED / REJECTED / INCONCLUSIVE**

<!-- Paste the generated Arm table here. Keep N/A distinct from zero. -->

## Paired inference

Report paired pass-rate differences, 95% paired-bootstrap intervals, exact two-sided McNemar results, and discordant-pair counts for B−A, C−A, and D−A. State whether D−A reaches +8 percentage points and its interval excludes zero.

## Reliability and recovery

Report false fulfilment numerator/denominator, completion precision/recall, first-mutation failures and recovered count, artifact validity, and unauthorized mutations. Never infer FULFILLED from action success.

## Breakdown and overhead

Report every preregistered breakdown, actions, tokens, latency, monetary cost, and arm-specific environment deviations. Explain missing values.

## Failure taxonomy

Attach evidence-backed assignments using `failure_assignment.schema.json`; include representative task IDs without copying golden values into runtime evidence. Preserve multi-label counts and failed experiments.

## Validity threats

Cover model/provider nondeterminism, incomplete pairing, evaluator independence, observation truncation, benchmark metadata exposure, missing renders, and any budget/environment deviation.

## Decision and next experiment

Compare evidence with unchanged preregistered criteria. Record regressions and competing explanations. Any post-hoc rule change becomes a new experiment.

Multimodal analysis status: N/A for tabular analysis records. Link adapter-produced render evidence for visually meaningful tasks.
