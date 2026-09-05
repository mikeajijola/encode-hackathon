# Declarative Fulfilment Architecture

## Research hypothesis

> Explicit executable desired-state specifications combined with test-driven
> reconciliation improve autonomous artifact fulfilment reliability over direct
> instruction-to-action agents.

SpreadsheetBench is the first test environment, not the system boundary. A task is
represented as an intent, an input artifact, and an execution environment. The
system compiles the intent into an executable contract and reconciles observations
of the artifact against that contract. Spreadsheet reading, mutation,
recalculation, and rendering are capabilities registered beneath this generic
layer.

The smallest coherent implementation is one process with typed records and seven
logical components. Logical separation matters for testing; separate services,
models, or agent frameworks do not.

## 1. Minimal components

| Component | Responsibility | Smallest implementation |
|---|---|---|
| Contract compiler | Compile intent and artifact context into a declarative contract and executable eval definitions | One structured model call plus deterministic schema and policy validation |
| Observer | Produce a bounded, canonical snapshot of artifact and environment state | Generic dispatcher plus artifact adapter |
| Evaluator | Execute deterministic, semantic, structural, and rendered evals; return results, never mutate | Eval registry and runner |
| Discrepancy engine | Turn failed evals into typed differences with mutation boundaries | Mostly deterministic comparison; optional model diagnosis |
| Fulfilment agent | Select the smallest useful transition, request actions, and control reconciliation | One bounded state machine |
| Capability broker | Discover, validate, invoke, and audit artifact/environment capabilities | In-process registry with typed request/result envelopes |
| Evidence store | Append observations, contracts, evals, decisions, actions, and provenance | JSONL events plus content-addressed artifact snapshots |

The discrepancy engine can initially live inside the evaluator, and the evidence
store can initially be a directory writer. This yields six runtime modules without
losing the conceptual boundaries above.

The fulfilment agent owns control flow but no artifact-specific operations. It may
reason using only the contract, observations, eval results, discrepancies,
capability manifests, budgets, and prior evidence.

## 2. Declarative contract

The canonical wire format is JSON-compatible YAML. Contracts are versioned,
immutable after acceptance, and identified by a hash. A later contract correction
creates a new revision and records why; it never silently edits the original.

```yaml
schema_version: fulfilment.contract/v1
contract_id: task-51-12/rev-1

intent:
  description: "Count the records matching the user's stated conditions."
  source_ref: "prompt.txt"

artifact:
  kind: spreadsheet
  input_ref: "1_51-12_init.xlsx"
  identity:
    sha256: "..."

desired_state:
  assertions:
    - id: result-present
      subject: {selector: "artifact://sheet/Sheet1/cell/B6"}
      predicate: has_computed_value
      expected: {type: number}
    - id: result-semantics
      subject: {selector: "artifact://sheet/Sheet1/cell/B6"}
      predicate: satisfies
      expected: {spec_ref: "eval://semantic/result-correct"}

constraints:
  - id: mutation-boundary
    rule: mutations_within
    value: ["artifact://sheet/Sheet1/cell/B6"]
  - id: preserve-input-data
    rule: unchanged_outside
    value: ["artifact://sheet/Sheet1/cell/B6"]

invariants:
  - id: artifact-opens
    assertion: {predicate: artifact_valid}
  - id: no-formula-errors
    assertion: {predicate: none_match, selector: "artifact://**/cell", value: "#*"}

evals:
  - id: structure-valid
    assertion_ref: artifact-opens
    evaluator: deterministic.artifact-validator
    severity: required
  - id: result-correct
    assertion_ref: result-semantics
    evaluator: deterministic.oracle-derived-test
    severity: required
  - id: preservation
    assertion_ref: preserve-input-data
    evaluator: deterministic.snapshot-diff
    severity: required
  - id: rendered-sanity
    assertion: {predicate: visually_usable, selector: "artifact://sheet/Sheet1"}
    evaluator: multimodal.render-review
    severity: advisory

completion:
  require:
    - all_required_evals_pass
    - all_constraints_preserved
    - all_invariants_hold
    - final_artifact_valid
    - required_evidence_captured
  budgets:
    max_iterations: 6
    max_actions: 12
    max_wall_seconds: 180
  on_budget_exhaustion: return_unfulfilled_with_evidence

evidence:
  capture:
    - accepted_contract
    - observed_states
    - eval_results
    - discrepancies
    - decisions
    - mutations
    - artifact_hashes
    - capability_provenance
  redaction_policy: secrets-and-unbounded-cell-data
```

### Contract validation

A contract is accepted only if:

1. every required assertion is referenced by at least one executable eval;
2. every eval names an available evaluator or a resolvable evaluator class;
3. selectors resolve or are explicitly allowed to resolve after mutation;
4. mutation constraints are representable by the broker's authorization policy;
5. completion is decidable from eval and evidence records;
6. assertions do not depend on inaccessible golden answers at fulfilment time;
7. ambiguity is either resolved, represented as alternatives with a discriminating
   eval, or returned as a typed `contract_ambiguous` failure.

The benchmark's answer position may be used to scope inspection and scoring when
the benchmark exposes it, but golden workbook values must never enter prompts,
contracts, traces, or fulfilment-time evals. Goldens are reserved for offline
benchmark scoring.

## 3. Fulfilment control loop

The loop is a bounded state machine rather than an unconstrained chat:

```text
contract = specify(intent, artifact_ref, capability_manifests)
validate(contract)
baseline = observe(artifact_ref, contract.relevant_selectors)

repeat until budget exhausted:
    eval_results = evaluate(contract, baseline, observation)
    evidence.append(observation, eval_results)

    if completion_decider(contract, eval_results, evidence):
        return FULFILLED(final_artifact, evidence_bundle)

    discrepancies = derive_discrepancies(contract, observation, eval_results)
    candidates = plan_transitions(discrepancies, capability_manifests, history)
    transition = choose_smallest_expected_discrepancy_reduction(candidates)

    if no safe transition exists:
        return UNFULFILLED(reason, artifact, evidence_bundle)

    result = broker.invoke(transition, contract.constraints)
    evidence.append(decision, action_request, action_result)
    observation = observe(result.artifact_ref, impacted_plus_invariant_scope)

return UNFULFILLED(budget_exhausted, best_valid_artifact, evidence_bundle)
```

`FULFILLED` is emitted only when:

```text
desired_state_satisfied
AND required_evals_pass
AND constraints_preserved
AND invariants_hold
AND artifact_valid
AND required_evidence_captured
```

An action error, unchanged observation, or regression creates a new discrepancy.
The planner does not simply repeat an identical failed transition: retries require
new evidence, changed parameters, a different capability, or an explicit transient
failure classification. Keep the last valid artifact snapshot so a corrupting or
regressive action can be rejected without losing progress.

## 4. Capability interface and broker

Capability and actor are independent. A capability manifest describes what can be
done and how its results can be verified, regardless of whether the actor is code,
an LLM, a remote service, a robot, or a human approval step.

```yaml
schema_version: fulfilment.capability/v1
name: spreadsheet.set_formula
version: "1"
actor: {kind: deterministic_tool, implementation: "adapter-id"}
accepts:
  artifact_kinds: [spreadsheet]
  input_schema: "schema://spreadsheet/set-formula-request/v1"
effects:
  may_change: ["artifact://sheet/{sheet}/cell/{cell}"]
  effect_class: mutation
preconditions: [artifact_writable, selector_resolves]
postconditions: [artifact_serializable]
risk: bounded_mutation
cost: {latency: low, monetary: none}
```

Every invocation uses an artifact-neutral envelope:

```yaml
request:
  invocation_id: inv-008
  capability: spreadsheet.set_formula@1
  artifact_ref: artifact://working/current
  discrepancy_ids: [disc-result-correct]
  parameters: {sheet: Sheet1, cell: B6, formula: "=..."}
  authorized_scope: ["artifact://sheet/Sheet1/cell/B6"]
  expected_effects: ["result-correct becomes pass"]

result:
  status: succeeded
  artifact_ref: artifact://snapshot/sha256:...
  observed_effects: ["artifact://sheet/Sheet1/cell/B6 changed"]
  stdout_digest: "..."
  provenance: {actor: adapter-id, version: "...", duration_ms: 31}
  error: null
```

The broker provides:

- discovery by artifact kind, effect, precondition, and risk;
- schema validation of requests and results;
- authorization by intersecting declared effects with contract mutation scope;
- snapshot-before-mutation and atomic promotion of valid results;
- timeouts, resource budgets, and sandbox boundaries;
- idempotency keys and duplicate-action detection;
- complete invocation provenance.

The planner ranks candidates by expected required-eval improvement, preservation
risk, reversibility, cost, and information gain. In the MVP this can be a simple
ordered score, with one model proposing candidate parameters.

## 5. Observed state and discrepancy

Observations are immutable, partial, and content-addressed. They distinguish facts
from interpretations and record what was not inspected.

```yaml
schema_version: fulfilment.observation/v1
observation_id: obs-004
artifact_ref: artifact://snapshot/sha256:...
artifact_kind: spreadsheet
captured_at: "..."
scope: ["artifact://sheet/Sheet1/range/A1:M7"]
facts:
  - path: "artifact://sheet/Sheet1/cell/B6"
    value: {kind: blank, raw: null, computed: null}
    provenance: spreadsheet.inspect
structure:
  media_type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  valid: true
  summary: {sheets: [Sheet1], formulas: 0, errors: 0}
environment:
  available_capabilities: [spreadsheet.inspect@1, spreadsheet.set_formula@1]
  recalculation_engine: {name: libreoffice, version: "..."}
coverage:
  inspected: ["artifact://sheet/Sheet1/range/A1:M7"]
  omitted: ["artifact://sheet/Sheet2/**"]
warnings: []
```

A discrepancy is the primary work item after contract acceptance:

```yaml
schema_version: fulfilment.discrepancy/v1
discrepancy_id: disc-result-correct
contract_id: task-51-12/rev-1
assertion_id: result-semantics
failed_eval: result-correct
severity: required
expected: {predicate: satisfies, spec_ref: "eval://semantic/result-correct"}
observed: {path: "artifact://sheet/Sheet1/cell/B6", value: null}
delta: {kind: missing_value}
likely_causes:
  - cause: required expression absent
    confidence: 0.96
confidence: 0.96
permissible_mutation_scope: ["artifact://sheet/Sheet1/cell/B6"]
blocked_by: []
regressions_risked: [preservation, artifact-opens]
status: open
```

Discrepancy lifecycle is `open -> targeted -> resolved | superseded | blocked`.
Evaluation—not the planner—marks a discrepancy resolved. New observations may
split one discrepancy into several or identify a dependency between them.

## 6. Eval architecture

Evals are plugins with a common pure interface:

```text
evaluate(contract_assertion, baseline_observation, current_observation,
         artifact_ref, environment) -> EvalResult
```

```yaml
eval_result:
  eval_id: result-correct
  status: pass            # pass | fail | error | not_applicable
  severity: required
  expected: "..."
  observed: "..."
  measurement: {type: exact_or_typed_comparison, value: true}
  confidence: 1.0
  evidence_refs: [event://run/task/eval/17]
  evaluator: {name: deterministic.oracle-derived-test, version: "git:..."}
  duration_ms: 12
```

Use the strongest available evaluator in this order:

1. deterministic structural and typed assertions;
2. executable domain rules and independently computed reference properties;
3. metamorphic/property tests (for example, copied formulas preserve relative
   semantics; totals change predictably after controlled perturbation);
4. isolated semantic review with a rubric and bounded context;
5. rendered/visual comparison for presentation properties.

Semantic evaluators must not see the action model's chain of thought or its claim
of success. They receive the contract, relevant observation, and artifact evidence.
For high-risk assertions, combine independent evaluators with `all`, `quorum`, or
`deterministic_gate_then_semantic` aggregation. An evaluator error never counts as
a pass. Required evals should minimize false positives; advisory evals expose
uncertainty without making completion impossible.

### Spreadsheet MVP eval stack

- package validity: archive/XML integrity and workbook load;
- structural validity: required sheets/ranges/types exist;
- recalculation: open/save headlessly, then inspect cached computed values;
- semantic correctness: derive an independent result from observed source data
  where feasible, without the golden workbook;
- preservation: canonical diff outside authorized selectors;
- formula safety: parse/reference checks and absence of error values;
- rendered sanity: render affected sheet/range and check clipping, unreadable
  output, and formatting regressions when the instruction has visual intent;
- external integration: run the official evaluator only after internal acceptance.

## 7. Evidence and trace model

Use an append-only event stream per task and content-addressed artifact snapshots:

```yaml
event_id: evt-00018
run_id: run-...
task_id: 51-12
sequence: 18
timestamp: "..."
type: eval.completed
parent_ids: [evt-00016]
payload_ref: blob://sha256:...
artifact_before: artifact://sha256:...
artifact_after: artifact://sha256:...
contract_hash: sha256:...
actor: {kind: deterministic_evaluator, id: preservation@1}
provenance:
  code_revision: git:...
  model: null
  capability_invocation: null
redactions: []
```

Minimum event types are `intent.received`, `contract.proposed`,
`contract.accepted`, `observation.captured`, `eval.completed`,
`discrepancy.opened`, `transition.selected`, `capability.invoked`,
`artifact.snapshotted`, and `run.completed`. Model-call details required by the
hackathon are emitted as trace events and projected into the specified
`traces/<id>.jsonl` format. Do not log secrets, hidden benchmark answers, or
unbounded artifact serialization.

The returned evidence bundle contains the final artifact hash, accepted contract,
final observation, all required eval results, mutation diff, capability provenance,
termination decision, and links to the event stream. This makes completion
auditable and replayable without treating an agent statement as evidence.

## 8. Artifact-specific adapters

The generic layer sees selectors, observations, declared effects, and capability
manifests. An adapter translates those abstractions into domain operations.

```text
Fulfilment agent
  -> contract / observations / discrepancies / eval results
  -> capability broker
       -> spreadsheet adapter: inspect, set value/formula, recalc, render, validate
       -> code adapter: inspect AST/tests, patch files, build, run tests
       -> infrastructure adapter: read state/plan, apply scoped change, health check
       -> PDF adapter: extract structure, edit/generate, render pages, validate
       -> website adapter: inspect DOM/network, mutate source/CMS, browser-test
       -> CRM adapter: query records, scoped update, validate business rules
       -> robotics adapter: sense, bounded motion/action, verify physical state
```

An adapter must supply: canonical selectors, observation serializers, mutating and
non-mutating capability manifests, validation hooks, snapshot/rollback semantics,
and optional renderers. It must not own contract completion or reconciliation.

For the hackathon, implement only these spreadsheet capabilities initially:

1. `inspect_workbook` (structure, formulas, values, styles, bounded tables);
2. `write_cells` (values or formulas within explicit selectors);
3. `copy_or_fill_formula` (range-aware relative formula operation);
4. `recalculate` (LibreOffice-backed);
5. `validate_workbook` (loadability, formula errors, structural checks);
6. `render_range` (only when a visual eval is required).

A sandboxed `execute_generated_program` may be added later, but it is broad and
high-risk; the broker must constrain filesystem paths, time, memory, network, and
post-action mutation diff.

## 9. Dependency-aware implementation plan

### Phase 0 — experiment lock (half day)

- Freeze dataset split, task IDs, model/version, temperature, token and action
  budgets, timeout, and retry policy.
- Define run manifest and random seeds where supported.
- Select a stratified development set across cell/sheet tasks and task families;
  keep a held-out set for final comparison.

Exit: identical inputs and budgets can drive every ablation.

### Phase 1 — types and evidence spine (half day)

- Implement versioned records for contract, observation, eval result, discrepancy,
  capability manifest/invocation, and evidence event.
- Add schema validation, hashing, JSONL event writing, and artifact snapshots.

Depends on Phase 0. Exit: fixture records round-trip and invalid records fail.

### Phase 2 — observation and spreadsheet adapter (one day)

- Implement broker registry and the six MVP spreadsheet capabilities.
- Canonicalize workbook observations and mutation diffs.
- Run all mutation code inside the submission container boundary.

Depends on Phase 1. Exit: inspect, mutate a scoped cell, recalculate, validate,
render, and prove nothing outside scope changed.

### Phase 3 — eval engine (one day)

- Implement deterministic gates, preservation checks, recalculated value checks,
  semantic/property evaluator hooks, aggregation, and completion decider.
- Build eval fixtures containing valid, subtly wrong, structurally corrupt, and
  visually broken artifacts.

Depends on Phases 1–2. Exit: each fault is caught by the intended eval modality.

### Phase 4 — specification compiler (one day)

- Compile instruction plus bounded observation into the v1 contract.
- Deterministically validate eval coverage, selectors, mutation scope, and
  completion decidability; retry contract generation only on typed validation
  errors.

Depends on Phases 1–3 because a contract may reference only executable evals.
Exit: development tasks produce accepted contracts without goldens.

### Phase 5 — discrepancy-driven reconciliation (one day)

- Derive discrepancies from failed evals, propose/rank bounded transitions, invoke
  through the broker, re-observe impacted and invariant scopes, and stop via the
  completion decider.
- Add no-progress, repeated-action, regression, and budget-exhaustion handling.

Depends on Phases 1–4. Exit: seeded one-step and multi-step faults converge or
return typed unfulfilled evidence; they never claim unsupported success.

### Phase 6 — benchmark ablations and hardening (one day)

- Run the four treatments below on identical tasks and budgets.
- Inspect failure clusters, improve generic evals/contracts before adding narrow
  task tricks, then freeze and run held-out evaluation.
- Produce required workbook outputs, projected model traces, run log, results, and
  a short demo showing discrepancy reduction over iterations.

Depends on all prior phases. Exit: reproducible metrics and a Docker run matching
the judge interface.

## 10. Benchmark strategy

Use a controlled four-arm ablation:

| Arm | Specification | Internal evals | Reconciliation | Purpose |
|---|---:|---:|---:|---|
| A: direct | No | No | No | Instruction-to-action baseline |
| B: state | Yes | No | No | Isolate explicit desired state |
| C: state + evals | Yes | Yes, one terminal run | No | Isolate executable tests |
| D: full | Yes | Yes, every iteration | Yes | Test iterative discrepancy reduction |

Keep fixed across arms: base model, tool set, initial artifact, task ordering,
context sources, maximum tokens, maximum wall time, and approximately matched
action opportunity. Record actual calls, tokens, time, and cost. Run paired tasks
and report bootstrap confidence intervals over task-level differences; use paired
McNemar tests for pass/fail comparisons. Report results overall, by cell/sheet
level, task family, and number of required mutations.

Primary metric is official all-cells-correct task pass rate after LibreOffice
recalculation. Secondary metrics are cell accuracy, artifact validity rate,
constraint-violation rate, unsupported-success rate, internal-eval precision and
recall against the official outcome, iterations/actions, latency, tokens, and cost.

To measure eval quality without leaking goldens, run fulfilment without goldens,
then join internal completion decisions to official results offline. A false
positive is especially important: the system returned `FULFILLED` but the official
grader failed it. Also measure recovery yield: tasks failing after the first action
that pass after reconciliation.

## 11. Multi-modal implementation eval matrix

Every major task has semantic, inspection, structural, trace, and visual coverage
where visual state is meaningful.

| Implementation task | Semantic correctness | Artifact inspection | Structural validity | Trace evidence | Rendered/visual |
|---|---|---|---|---|---|
| Records and evidence spine | Required assertions and termination are decidable | Snapshot hashes reproduce byte identity | Schema/version/property tests | Event ordering, parents, actor and hashes complete | N/A |
| Spreadsheet observer | Values/formulas/types preserve meaning | Compare observation to independently inspected fixture | Workbook/sheet/range coverage and omission metadata | Scope, adapter version and source hash recorded | Render fixture and correlate selected range |
| Broker and mutations | Declared effect achieves requested local state | Before/after canonical diff equals observed effects | Reject invalid requests and out-of-scope writes | Invocation, authorization, parameters and result linked | Pixel/layout diff for style-affecting mutations |
| Recalculation/validation | Known formulas yield independent expected values | Inspect cached results and formula-error cells | Corrupt packages and missing sheets fail | Engine/version/duration/output digest recorded | Render recalculated affected region when relevant |
| Contract compiler | Human-reviewed intent fixtures map to correct assertions | Selectors resolve against observation | Schema, eval coverage, scope and decidability gates | Prompt/model/input hash/revision/rejection reasons recorded | If intent is visual, contract includes a visual assertion |
| Eval engine | Seeded right/wrong artifacts pass/fail correctly | Results cite exact observed facts/artifact hashes | Evaluator errors cannot pass; aggregation tests | Evaluator/version/measurement/evidence refs complete | Seed clipping/style/layout faults and test detection |
| Discrepancy engine | Expected-observed delta and likely cause fit seeded faults | Discrepancy references exact failed observation/eval | Lifecycle, severity and mutation-scope validation | Open/target/resolve lineage reconstructable | Visual fault localizes to rendered selector |
| Reconciliation loop | Multi-step fixtures converge; impossible tasks do not claim success | Re-observation proves action effects and preservation | Budget, no-progress, rollback and completion tests | Full causal chain from intent to termination | Before/after render reviewed for visual tasks |
| End-to-end submission | Internal completion predicts official success | Output opens and graded selectors contain valid results | Required files and JSONL formats validate | Every model/tool call projected into judge trace | Sampled sheet renders detect presentation regressions |

For visual evals, retain both the canonical render and comparison result as
evidence. Prefer deterministic layout measurements; use a vision model only for
semantic presentation judgments such as readability, and never as the sole gate
for computational correctness.

## 12. Success criteria

The architecture proves the hypothesis only if the full system improves reliability
rather than merely producing richer traces. Pre-register these criteria before the
held-out run:

1. Arm D has a statistically credible positive paired pass-rate difference over
   Arm A on held-out tasks (target: at least +8 percentage points and 95% bootstrap
   confidence interval excluding zero).
2. The ablation trend is directionally monotonic: `D > C >= B >= A` in pass rate;
   deviations must be explained with uncertainty and failure analysis rather than
   hidden.
3. Arm D recovers at least 20% of tasks that fail after its first mutation, proving
   that reconciliation—not only better initial prompting—adds value.
4. Unsupported-success rate is below 5%, and lower than Arm A's implicit success
   rate; required internal evals have at least 90% precision for official passes.
5. Artifact validity is at least 99%, with zero known out-of-scope mutations among
   runs labeled `FULFILLED`.
6. Every completion decision is reproducible from the accepted contract, final
   artifact, eval results, and evidence stream; no completion relies only on an LLM
   self-report.
7. Median cost/latency is reported and the gain remains useful under the fixed
   hackathon budget. Report the Pareto frontier rather than concealing overhead.
8. A second toy adapter (for example, a directory of text files with tests) can use
   the same contract, discrepancy, broker, loop, and evidence modules with only
   adapter/evaluator plugins changed. This is the architectural portability check,
   not a second production integration.

The demo should show one task progressing from accepted contract, through a failed
eval and explicit discrepancy, to a scoped mutation, re-observation, passing evals,
and an evidence-backed `FULFILLED` result. A second task should exhaust its budget
or encounter an unsafe transition and correctly return `UNFULFILLED`; reliable
refusal is part of fulfilment reliability.
