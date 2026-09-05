# Adversarial experimental-validity review

Date: 2026-09-05  
Scope: integrated production backend, services, runner, generic core, task selection, offline projection, scorer, and both container definitions.  
Disposition: **registered benchmark runs are blocked** until the blocking findings below are resolved and the invariant suite is updated with evidence of the resolution.

This review does not change the preregistered thresholds or official scorer. Tests that assert a known defect are explicit blocker sentinels: their passing result means the defect is still present, not that production is ready.

## Findings

| ID | Severity | Blocking? | Evidence and consequence |
|---|---|---:|---|
| V-01 | Critical | Resolved with limitation | A production isolated semantic-model evaluator now independently receives intent, accepted contract, bounded source observation, and current target facts without the action response. Malformed, error, and uncertain verdicts cannot pass; blank targets first create an actionable state discrepancy. It uses the same configured provider/model in an isolated role, so actor-level independence remains a disclosed limitation. |
| V-02 | Critical | Resolved | Production Arm D now constructs the generic `FulfilmentAgent`; its artifact-neutral loop exclusively owns observation transitions, eval execution, discrepancy lifecycle, broker invocation, repetition/no-progress detection, completion, and termination evidence. Spreadsheet-specific observer, evaluator, planner, lifecycle, and capability handlers implement only the generic interfaces. Production fixture tests cover repair, knowledge observation, scope rejection, no-progress, uncertainty, and reconstructable evidence. |
| V-03 | High | Resolved as controlled deviation | Production control is now explicitly characterized as Arm A v2 in `ARM_A_V2.md`; it is not represented as the legacy baseline and legacy scores cannot be reused. A/B/C/D share its bounded context, action schema, broker, and budgets, leaving the declared treatment components as differences. A legacy-v2 comparison remains a separate harness ablation. |
| V-04 | High | Resolved | The runner now projects `FULFILLED_UNVERIFIED` for successful A/B one-shot claims, `FULFILLED` only for passing C/D terminal evals, and `UNFULFILLED` otherwise, with a typed termination reason. Offline FFR includes both completion-claim labels while preserving their evidentiary distinction. |
| V-05 | High | Resolved | `TaskRuntime.complete` now enforces `model_transport_retries` uniformly across arms, traces every failed and successful attempt, records retry events, and separately reports total versus successful calls. No action retry was added. |
| V-06 | High | No (static resolution; external smoke pending) | Resolved structurally: the repository-root `Dockerfile` is now the sole Dockerfile and contains the LibreOffice, non-root user, healthcheck, locked install, preflight entrypoint, and `/data:ro` to `/out` contract. Root `.dockerignore` and static tests reject duplicate Dockerfiles. Docker is unavailable on this host, so an actual image build and judge-style smoke run remain an explicit external validation blocker; this row does not claim they passed. |
| V-07 | Medium | No, if stratified and disclosed | Initial observation is capped at 400 cells/30,000 characters. Omission is correctly explicit, but action generation cannot recover omitted evidence through an information-gathering capability in the current service path. Report truncation incidence and stratify outcomes; tasks whose needed source is omitted are observation/knowledge failures. |
| V-08 | Medium | Resolved with limitation | Contract proposals now pass a strict state-only v2 schema: assertion property/description, output type/shape/uncertainty, constraints, invariants, evaluator intents, and required capabilities. Unknown, empty, malformed, procedural, selector-inconsistent, and unavailable references fail closed. Safety evals and authorized selectors remain deterministically policy-bound, while accepted model state fields enter action and semantic-eval context. This establishes construct plumbing, not that model-authored specifications are accurate; V-01 still blocks benchmark claims. |
| V-09 | Medium | Resolved | Compiler prompts now contain the exact versioned `Task.capability_manifests`; proposals must cite available name/version pairs and include the required write capability. Tests compare the prompt payload exactly and reject absent/mismatched capabilities. |
| V-10 | Medium | No | Evaluator independence is isolation-by-field-filter within the same service/process. `independent_expected` is withheld from model prompts, which is good, but any future computation must be provenance-recorded and tested against tautology. There is no process-level separation. |
| V-11 | Low | No | 275/400 dataset tasks have no `answer_sheet`; active-sheet resolution matches the scorer. Six tasks contain multiple explicit sheet markers and resolve in fixture coverage. Nine contain comma-separated positions. These cases require a pre-run selector-resolution audit over the selected split. |
| V-12 | Low | No | The development selection is reproducible, hash-verified, balanced 10/10, and contains no reference-answer fields. Selection metadata includes answer position/sheet, so that benchmark-specific narrowing must remain identical across arms and be disclosed. |
| R-01 | Critical | Resolved | `SpreadsheetServices.reconcile` delegates to `FulfilmentAgent` with spreadsheet protocol implementations beneath its interfaces. Source assertions and production tests demonstrate generic knowledge-to-observation routing, capability transition authorization, re-observation/evaluation, repeated-transition `no_progress`, evidence-gated completion, and typed refusal. No spreadsheet import was added to `fulfilment/`. |
| R-02 | High | Resolved | Registered CLI runs now retain byte-equivalent input manifest bytes, their SHA-256, and complete embedded content in the runtime manifest. Runtime config equality is checked before execution, task-start events bind the source hash, and reconstruction detects byte or embedded-content tampering. |
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

1. Expose advertised capabilities to discrepancy planning, especially bounded observation and formula-fill/recalculation for large ranges.
2. Freeze Arm A v2 prompts, schemas, tools, completion labels, and budgets; treat any legacy comparison as a separate ablation.
3. Complete a real canonical-container build/smoke run with LibreOffice.
4. Verify an oracle score of 1.0 offline and pin scorer/container/provider revisions.

## Evaluation coverage

`tests/test_validity_invariants.py` exercises semantic isolation, structural selection/loading/selector behavior, trace/evidence integrity, completion rejection, budget configuration, abstraction boundaries, scorer immutability, and blocker sentinels against production source paths. Rendered evaluation is not meaningful for this audit document; visual semantics remain an adapter responsibility. The container build remains blocked on this host because Docker is unavailable, as already recorded in `DOCKER_VALIDATION.md`.

## Conclusion

The semantic evaluator, generic completion gate, explicit completion claims, retry enforcement, and self-contained run-manifest provenance materially improve validity. Registered execution remains blocked: D still runs artifact-specific rather than generic reconciliation semantics, large-range tasks cannot select the advertised non-literal capabilities, and the canonical Docker image has not been externally built or smoke-tested. Synthetic results validate orchestration arithmetic only and do not mitigate these blockers.

## Final sweep evidence

The machine-readable decision is `protocol/FINAL_READINESS.json`. Using dataset metadata hash `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`, all 400 initial artifacts resolved their answer selectors with zero errors and zero duplicate selectors. The largest expansion was 104,110 cells. No reference workbook was opened by that audit.

Standard CLI construction creates a fresh `SpreadsheetServices` instance per run and the runner rejects duplicate task IDs, so sessions are isolated for the supported lifecycle. Reusing one service instance across separate runners with the same task IDs is unsupported and would reuse cached sessions; do not do this in registered execution.

The synthetic test now writes only beneath a `TemporaryDirectory` via `--out-dir`, so running tests does not rewrite committed synthetic evidence. The official scorer remains byte-identical at SHA-256 `8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b`.

Environment evidence is also absent on this host: `OPENROUTER_API_KEY`, Docker CLI, and `soffice` are unavailable. Even after code blockers are fixed, a registered run remains blocked until a pinned API/model configuration and successful hardened-container/LibreOffice preflight are captured.
