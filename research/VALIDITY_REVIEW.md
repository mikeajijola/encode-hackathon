# Adversarial experimental-validity review

Date: 2026-09-05  
Scope: integrated production backend, services, runner, generic core, task selection, offline projection, scorer, and both container definitions.  
Disposition: **registered benchmark runs are blocked** until the blocking findings below are resolved and the invariant suite is updated with evidence of the resolution.

This review does not change the preregistered thresholds or official scorer. Tests that assert a known defect are explicit blocker sentinels: their passing result means the defect is still present, not that production is ready.

## Findings

| ID | Severity | Blocking? | Evidence and consequence |
|---|---|---:|---|
| V-01 | Critical | Yes | The production loader never supplies `independent_expected` and no independent domain computation exists. `SpreadsheetServices._evaluate` therefore emits `UNCERTAIN` for the required semantic eval on every real task. Arm D stops before its first mutation on the initial uncertainty; Arm C can never pass its internal completion eval. The proposed treatment is not being tested. |
| V-02 | Critical | Resolved | `SpreadsheetServices.reconcile` now delegates every prospective success to generic `decide_completion`; no local eval-list check may emit `fulfilled`. The hash-chained broker evidence contains the accepted contract, observations, eval results, and termination decision with artifact hash. `test_missing_required_evidence_prevents_fulfilled`, uncertainty/error coverage, and the repair trace prove that missing evidence or non-passing evals block completion and a successful decision is reconstructable. Spreadsheet-specific mechanics remain outside `fulfilment/`. |
| V-03 | High | Yes | Production Arm A is not the audited baseline. The audited baseline has a fixed system prompt/output schema requesting answer-cell values. The production service instead requests an undocumented `writes` action object through a different prompt and broker. A-versus-D would confound architecture with prompt/schema/harness changes. |
| V-04 | High | Yes | `task_results/*.json` has no `internal_status`. Offline analysis infers FULFILLED only from a terminal passing eval, making FFR structurally N/A for A and B and silently redefining their completion behavior. This cannot answer whether the architecture reduces false completion claims across all treatments. A single pre-run completion-status projection rule must be frozen. |
| V-05 | High | Yes | The preregistration fixes one model transport retry, but `retry_policy` is only serialized; `TaskRuntime.complete` performs no retry. Registered conditions and execution differ. Either implement the pinned policy uniformly or record a new preregistered deviation before any run. |
| V-06 | High | Yes | Two root candidates named `Dockerfile` have materially different behavior. `docker build .` selects the repository-root file, which lacks LibreOffice, non-root execution, healthcheck, and the hardened preflight; documentation validates `docker build research`. A submission/judge can build the wrong image. Keep one canonical root build contract or make the root delegate unambiguously to the hardened image. |
| V-07 | Medium | No, if stratified and disclosed | Initial observation is capped at 400 cells/30,000 characters. Omission is correctly explicit, but action generation cannot recover omitted evidence through an information-gathering capability in the current service path. Report truncation incidence and stratify outcomes; tasks whose needed source is omitted are observation/knowledge failures. |
| V-08 | Medium | No | The model contract proposal contributes only a description. Assertions, eval IDs, selectors, constraints, and invariants are hard-coded from benchmark answer metadata. This is a useful scaffold but weak evidence that natural language was compiled into an executable desired state. Report as construct-validity limitation. |
| V-09 | Medium | No | Compiler prompts receive hard-coded capability names rather than the versioned `Task.capability_manifests`. This weakens capability-availability reasoning and can conceal missing capability versions. |
| V-10 | Medium | No | Evaluator independence is isolation-by-field-filter within the same service/process. `independent_expected` is withheld from model prompts, which is good, but any future computation must be provenance-recorded and tested against tautology. There is no process-level separation. |
| V-11 | Low | No | 275/400 dataset tasks have no `answer_sheet`; active-sheet resolution matches the scorer. Six tasks contain multiple explicit sheet markers and resolve in fixture coverage. Nine contain comma-separated positions. These cases require a pre-run selector-resolution audit over the selected split. |
| V-12 | Low | No | The development selection is reproducible, hash-verified, balanced 10/10, and contains no reference-answer fields. Selection metadata includes answer position/sheet, so that benchmark-specific narrowing must remain identical across arms and be disclosed. |

## Invariants verified

- Runtime task loading projects only instruction, initial artifact, bounded observation, answer metadata, and public task metadata; a deliberately invalid reference file is not opened.
- The committed development selection hash validates and is balanced by cell/sheet instruction level.
- Observation truncation reports limits, serialized count, omitted count, and omitted scope.
- Active-sheet and explicit multi-sheet selectors resolve deterministically in production code.
- `independent_expected` is removed from both contract and action model context.
- Generic `fulfilment/` modules import neither OpenPyXL nor spreadsheet adapters/services.
- The generic completion gate rejects evaluator errors and missing evidence.
- Hash-chained core evidence detects mutation.
- Common preregistered token/action/time budgets remain unchanged.
- Official scorer SHA-256 remains `8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b`.

## Required pre-run resolution order

1. Supply a defensible golden-blind semantic evaluator or explicitly narrow the experiment to tasks with independent derivations; prove D can act after a state discrepancy and can reliably refuse a true knowledge gap.
2. Route D through one generic, evidence-gated completion path. Require a reproducible termination decision and verify required evidence before projecting FULFILLED.
3. Make production A behavior equivalent to the characterized baseline, then freeze prompts, schemas, tools, and budgets per arm.
4. Define and emit `internal_status` for every arm before offline scoring; specify denominators for FFR and completion precision without post-hoc inference.
5. Enforce or preregister the actual retry policy.
6. Resolve the two-Dockerfile ambiguity and complete a real container build/smoke run with LibreOffice.
7. Run selector and truncation audits on the exact hashed task manifest, verify an oracle score of 1.0 offline, and pin scorer/container/provider revisions.

## Evaluation coverage

`tests/test_validity_invariants.py` exercises semantic isolation, structural selection/loading/selector behavior, trace/evidence integrity, completion rejection, budget configuration, abstraction boundaries, scorer immutability, and blocker sentinels against production source paths. Rendered evaluation is not meaningful for this audit document; visual semantics remain an adapter responsibility. The container build remains blocked on this host because Docker is unavailable, as already recorded in `DOCKER_VALIDATION.md`.

## Conclusion

The repository is a coherent research scaffold, but the current production path cannot run the registered hypothesis test validly. In particular, D deterministically refuses for lack of a semantic oracle, and if that oracle were added its spreadsheet-local completion path would still bypass the generic evidence gate. Synthetic results validate orchestration arithmetic only and do not mitigate these blockers.
