# Adversarial experimental-validity review

Date: 2026-09-05  
Scope: integrated production backend, services, runner, generic core, task selection, offline projection, scorer, and both container definitions.  
Disposition: **registered benchmark runs are blocked** until the blocking findings below are resolved and the invariant suite is updated with evidence of the resolution.

This review does not change the preregistered thresholds or official scorer. Tests that assert a known defect are explicit blocker sentinels: their passing result means the defect is still present, not that production is ready.

## Findings

| ID | Severity | Blocking? | Evidence and consequence |
|---|---|---:|---|
| V-01 | Critical | Resolved with limitation | A production isolated semantic-model evaluator now independently receives intent, accepted contract, bounded source observation, and current target facts without the action response. Malformed, error, and uncertain verdicts cannot pass; blank targets first create an actionable state discrepancy. It uses the same configured provider/model in an isolated role, so actor-level independence remains a disclosed limitation. |
| V-02 | Critical | Partially resolved; still blocking | Every prospective success now passes generic `decide_completion`, and hash-chained evidence contains contract, observation, eval and termination records. However, `SpreadsheetServices.reconcile` still owns the iteration and transition policy instead of invoking the generic `FulfilmentAgent`; generic observation-transition, capability selection, and no-progress semantics therefore are not the semantics under test. Tracked as R-01. |
| V-03 | High | Resolved as controlled deviation | Production control is now explicitly characterized as Arm A v2 in `ARM_A_V2.md`; it is not represented as the legacy baseline and legacy scores cannot be reused. A/B/C/D share its bounded context, action schema, broker, and budgets, leaving the declared treatment components as differences. A legacy-v2 comparison remains a separate harness ablation. |
| V-04 | High | Resolved | The runner now projects `FULFILLED_UNVERIFIED` for successful A/B one-shot claims, `FULFILLED` only for passing C/D terminal evals, and `UNFULFILLED` otherwise, with a typed termination reason. Offline FFR includes both completion-claim labels while preserving their evidentiary distinction. |
| V-05 | High | Resolved | `TaskRuntime.complete` now enforces `model_transport_retries` uniformly across arms, traces every failed and successful attempt, records retry events, and separately reports total versus successful calls. No action retry was added. |
| V-06 | High | No (static resolution; external smoke pending) | Resolved structurally: the repository-root `Dockerfile` is now the sole Dockerfile and contains the LibreOffice, non-root user, healthcheck, locked install, preflight entrypoint, and `/data:ro` to `/out` contract. Root `.dockerignore` and static tests reject duplicate Dockerfiles. Docker is unavailable on this host, so an actual image build and judge-style smoke run remain an explicit external validation blocker; this row does not claim they passed. |
| V-07 | Medium | No, if stratified and disclosed | Initial observation is capped at 400 cells/30,000 characters. Omission is correctly explicit, but action generation cannot recover omitted evidence through an information-gathering capability in the current service path. Report truncation incidence and stratify outcomes; tasks whose needed source is omitted are observation/knowledge failures. |
| V-08 | Medium | No | The model contract proposal contributes only a description. Assertions, eval IDs, selectors, constraints, and invariants are hard-coded from benchmark answer metadata. This is a useful scaffold but weak evidence that natural language was compiled into an executable desired state. Report as construct-validity limitation. |
| V-09 | Medium | No | Compiler prompts receive hard-coded capability names rather than the versioned `Task.capability_manifests`. This weakens capability-availability reasoning and can conceal missing capability versions. |
| V-10 | Medium | No | Evaluator independence is isolation-by-field-filter within the same service/process. `independent_expected` is withheld from model prompts, which is good, but any future computation must be provenance-recorded and tested against tautology. There is no process-level separation. |
| V-11 | Low | No | 275/400 dataset tasks have no `answer_sheet`; active-sheet resolution matches the scorer. Six tasks contain multiple explicit sheet markers and resolve in fixture coverage. Nine contain comma-separated positions. These cases require a pre-run selector-resolution audit over the selected split. |
| V-12 | Low | No | The development selection is reproducible, hash-verified, balanced 10/10, and contains no reference-answer fields. Selection metadata includes answer position/sheet, so that benchmark-specific narrowing must remain identical across arms and be disclosed. |
| R-01 | Critical | Yes | The production D loop is artifact-specific. It lacks the generic agent's transition type validation, knowledge-to-observation rule, capability-manifest planning and repeated-transition/no-progress guard. Completion gating alone does not prove generic reconciliation semantics. |
| R-02 | High | Yes | Generated input manifests contain protocol, selection, dataset, lock, environment and container pins, but `ExperimentRunner._prepare` writes only `RunConfig` to the output manifest. A submitted output directory is insufficient to reconstruct its run without separately preserved input state. |
| R-03 | High | Yes | The production action path accepts only literal `writes`. Although formula-fill, recalculation, validation, rendering and observation capabilities are advertised, the planner cannot select them. The all-400 selector audit found targets as large as 104,110 cells and the development split includes a 6,066-cell target, making literal output incompatible with the fixed token budget for affected tasks. |

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

1. Route D through the generic control semantics, retaining the now-working independent evaluator and evidence completion gate.
2. Preserve the complete validated input manifest (or its content and hash) with each output run so evidence reconstruction is self-contained.
3. Expose advertised capabilities to discrepancy planning, especially bounded observation and formula-fill/recalculation for large ranges.
4. Freeze Arm A v2 prompts, schemas, tools, completion labels, and budgets; treat any legacy comparison as a separate ablation.
5. Resolve the two-Dockerfile ambiguity and complete a real container build/smoke run with LibreOffice.
6. Verify an oracle score of 1.0 offline and pin scorer/container/provider revisions.

## Evaluation coverage

`tests/test_validity_invariants.py` exercises semantic isolation, structural selection/loading/selector behavior, trace/evidence integrity, completion rejection, budget configuration, abstraction boundaries, scorer immutability, and blocker sentinels against production source paths. Rendered evaluation is not meaningful for this audit document; visual semantics remain an adapter responsibility. The container build remains blocked on this host because Docker is unavailable, as already recorded in `DOCKER_VALIDATION.md`.

## Conclusion

The semantic evaluator, generic completion gate, explicit completion claims, retry enforcement, and reproducible input-manifest generator materially improve validity. Registered execution remains blocked: D still runs artifact-specific rather than generic reconciliation semantics; output evidence drops the outer reproducibility manifest; large-range tasks cannot select the advertised non-literal capabilities; and Docker packaging remains ambiguous. Synthetic results validate orchestration arithmetic only and do not mitigate these blockers.

## Final sweep evidence

The machine-readable decision is `protocol/FINAL_READINESS.json`. Using dataset metadata hash `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`, all 400 initial artifacts resolved their answer selectors with zero errors and zero duplicate selectors. The largest expansion was 104,110 cells. No reference workbook was opened by that audit.

Standard CLI construction creates a fresh `SpreadsheetServices` instance per run and the runner rejects duplicate task IDs, so sessions are isolated for the supported lifecycle. Reusing one service instance across separate runners with the same task IDs is unsupported and would reuse cached sessions; do not do this in registered execution.

The synthetic test now writes only beneath a `TemporaryDirectory` via `--out-dir`, so running tests does not rewrite committed synthetic evidence. The official scorer remains byte-identical at SHA-256 `8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b`.

Environment evidence is also absent on this host: `OPENROUTER_API_KEY`, Docker CLI, and `soffice` are unavailable. Even after code blockers are fixed, a registered run remains blocked until a pinned API/model configuration and successful hardened-container/LibreOffice preflight are captured.
