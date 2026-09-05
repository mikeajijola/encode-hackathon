"""SpreadsheetBench service wiring; golden workbooks are never accepted or read."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from adapters.spreadsheet import KIND, VERSION, WorkbookSnapshots, parse_selector, register_spreadsheet_capabilities, scope_for
from experiment.runner import EvaluationResult, ExecutionResult, Task, TaskRuntime
from sb import answer_cells
from fulfilment import (
    Broker, CapabilityRequest, Contract, ContractValidator, DesiredAssertion,
    Discrepancy, EvalResult, EvalSpec, EvalStatus, EvidenceStore, Observation,
    Scope, derive_discrepancies,
)


@dataclass
class _Session:
    contract: Contract
    broker: Broker
    snapshots: WorkbookSnapshots
    evidence: EvidenceStore
    initial_cells: dict[str, Any]
    discrepancies: tuple[Discrepancy, ...] = ()


class SpreadsheetServices:
    """Implements runner Services while delegating all XLSX effects to the adapter."""

    FORBIDDEN_CONTEXT_KEYS = {"golden", "golden_xlsx", "answer", "expected_answer"}

    def __init__(self):
        self._sessions: dict[str, _Session] = {}

    def compile_contract(self, task: Task, runtime: TaskRuntime) -> Mapping[str, Any]:
        forbidden = self.FORBIDDEN_CONTEXT_KEYS & set(task.context)
        if forbidden:
            raise ValueError(f"runtime context contains forbidden golden-like keys: {sorted(forbidden)}")
        selectors = _answer_selectors(task.context, task.artifact)
        reply = runtime.complete(
            "Compile a declarative state-only contract. Do not provide steps.\n"
            + json.dumps({"intent": task.intent, "observed_context": _model_context(task.context),
                          "capabilities": ["inspect", "write", "formula_fill", "validate", "render"]}, default=str),
            purpose="contract",
        )
        proposal = _json_reply(reply.text)
        description = str(proposal.get("description") or f"answer selectors satisfy the requested intent: {task.intent}")
        if description.lower().lstrip().startswith(("first ", "then ", "step ", "click ", "open ")):
            raise ValueError("procedural contract proposal rejected")
        assertion = DesiredAssertion("answer-state", description, tuple(scope_for(s) for s in selectors))
        evals = [
            EvalSpec("artifact-valid", "answer-state", "artifact-valid"),
            EvalSpec("preservation", "answer-state", "preservation"),
            EvalSpec("nonblank", "answer-state", "nonblank"),
            EvalSpec("type", "answer-state", "type"),
            EvalSpec("formula-errors", "answer-state", "formula-errors"),
            EvalSpec("semantic", "answer-state", "semantic-independent"),
        ]
        if task.context.get("visual_intent"):
            evals.append(EvalSpec("visual", "answer-state", "render"))
        contract = Contract(
            f"contract-{task.id}", 1, task.intent, (assertion,),
            ("preserve cells outside authorized answer selectors",), ("workbook remains structurally valid",),
            tuple(evals), tuple(scope_for(s) for s in selectors),
        )
        ContractValidator().validate(contract)
        return _contract_mapping(contract, task.context)

    def execute_once(self, task: Task, contract: Mapping[str, Any] | None, destination: Path,
                     runtime: TaskRuntime) -> ExecutionResult:
        shutil.copy2(task.artifact, destination)
        session = self._session(task, contract or self._direct_contract(task), destination, runtime,
                                inspect=contract is not None)
        proposal = self._action_proposal(task, contract, runtime, discrepancies=())
        result = self._apply_proposal(task, destination, runtime, session, proposal, ())
        return ExecutionResult(destination, "ok" if result else "action_failed", {"broker_evidence": str(session.evidence.path)})

    def evaluate_once(self, task: Task, contract: Mapping[str, Any], artifact: Path,
                      runtime: TaskRuntime) -> EvaluationResult:
        session = self._session(task, contract, artifact, runtime, inspect=True)
        results, discrepancies = self._evaluate(task, artifact, session, runtime)
        session.discrepancies = discrepancies
        passed = all(result.status is EvalStatus.PASS for result in results)
        status = "pass" if passed else ("uncertain" if any(r.status is EvalStatus.UNCERTAIN for r in results) else "fail")
        return EvaluationResult(passed, status, {"evals": [_eval_mapping(r) for r in results],
                                                  "discrepancies": [_discrepancy_mapping(d) for d in discrepancies]})

    def reconcile(self, task: Task, contract: Mapping[str, Any], destination: Path,
                  runtime: TaskRuntime) -> tuple[ExecutionResult, EvaluationResult]:
        shutil.copy2(task.artifact, destination)
        session = self._session(task, contract, destination, runtime, inspect=True)
        evaluation = None
        for iteration in range(1, runtime.config.max_actions + 1):
            results, discrepancies = self._evaluate(task, destination, session, runtime)
            session.discrepancies = discrepancies
            if all(result.status is EvalStatus.PASS for result in results):
                evaluation = EvaluationResult(True, "pass", {"iteration": iteration,
                    "evals": [_eval_mapping(r) for r in results], "discrepancies": []})
                runtime.event("terminal_evaluation", asdict(evaluation))
                return ExecutionResult(destination, "fulfilled", {"iterations": iteration,
                    "broker_evidence": str(session.evidence.path)}), evaluation
            if any(d.kind.value == "evaluation_uncertainty" for d in discrepancies):
                evaluation = EvaluationResult(False, "uncertain", {"iteration": iteration,
                    "evals": [_eval_mapping(r) for r in results],
                    "discrepancies": [_discrepancy_mapping(d) for d in discrepancies]})
                runtime.event("terminal_evaluation", asdict(evaluation))
                return ExecutionResult(destination, "unfulfilled:evaluation_uncertain", {},), evaluation
            proposal = self._action_proposal(task, contract, runtime, discrepancies)
            if not self._apply_proposal(task, destination, runtime, session, proposal, discrepancies):
                evaluation = EvaluationResult(False, "capability_failure", {"iteration": iteration})
                return ExecutionResult(destination, "unfulfilled:capability_failure", {}), evaluation
        evaluation = EvaluationResult(False, "budget_exhausted", {"discrepancies": [_discrepancy_mapping(d) for d in session.discrepancies]})
        return ExecutionResult(destination, "unfulfilled:budget_exhausted", {}), evaluation

    def _session(self, task, contract_mapping, artifact, runtime, *, inspect=False):
        if task.id in self._sessions:
            return self._sessions[task.id]
        contract = _contract_from_mapping(contract_mapping)
        evidence_path = runtime.event_path.with_name(f"{task.id}.broker.jsonl")
        evidence = EvidenceStore(evidence_path)
        snapshots = WorkbookSnapshots()
        broker = Broker(evidence, snapshots)
        register_spreadsheet_capabilities(broker)
        session = _Session(contract, broker, snapshots, evidence, _all_cells(artifact))
        self._sessions[task.id] = session
        if inspect:
            selectors = _answer_selectors(task.context, artifact)
            runtime.action("inspect_workbook", {"selectors": selectors})
            request = CapabilityRequest(str(uuid4()), "inspect_workbook", VERSION, str(artifact), KIND,
                                        {"selectors": selectors}, (), ())
            observed = broker.invoke(contract, request)
            runtime.event("bounded_observation", dict(observed.output["observation"]))
        return session

    def _direct_contract(self, task):
        selectors = _answer_selectors(task.context, task.artifact)
        return {"id": f"direct-{task.id}", "version": 1, "intent": task.intent,
                "description": "direct action boundary", "selectors": [scope_for(s).resource for s in selectors],
                "expected_type": task.context.get("expected_type"), "visual_intent": False,
                "independent_expected": None}

    def _action_proposal(self, task, contract, runtime, discrepancies):
        prompt = {"intent": task.intent, "answer_selectors": _answer_selectors(task.context, task.artifact),
                  "observed_context": _model_context(task.context), "contract": contract,
                  "discrepancies": [_discrepancy_mapping(d) for d in discrepancies]}
        return _json_reply(runtime.complete(json.dumps(prompt, default=str), purpose="action_generation").text)

    def _apply_proposal(self, task, destination, runtime, session, proposal, discrepancies):
        writes = proposal.get("writes")
        if not isinstance(writes, list):
            return False
        allowed = {scope.resource for scope in session.contract.authorized_mutation_scopes}
        requested = tuple(scope_for(item["selector"]) for item in writes)
        if any(scope.resource not in allowed for scope in requested):
            runtime.event("scope_violation_rejected", {"requested": [s.resource for s in requested]})
            return False
        discrepancy_ids = tuple(d.id for d in discrepancies) or (f"initial-{task.id}",)
        runtime.action("write_cells", {"discrepancy_ids": discrepancy_ids})
        request = CapabilityRequest(str(uuid4()), "write_cells", VERSION, str(destination), KIND,
                                    {"writes": writes}, requested, discrepancy_ids)
        result = session.broker.invoke(session.contract, request)
        runtime.event("capability_result", {"succeeded": result.succeeded,
                      "actual_scope": [s.resource for s in result.actual_mutation_scope],
                      "discrepancy_ids": discrepancy_ids})
        return result.succeeded

    def _evaluate(self, task, artifact, session, runtime):
        selectors = _answer_selectors(task.context, artifact)
        facts = _selected_cells(artifact, selectors)
        observation = Observation(str(uuid4()), str(artifact), KIND, _file_hash(artifact),
            {"cells": facts}, {}, tuple(scope_for(s) for s in selectors), (scope_for("__omitted__!A1"),))
        results = []
        valid, structural_error = _valid(artifact)
        results.append(_eval("artifact-valid", observation, valid, structural_error or "workbook loads",
                             kind="artifact_invalid"))
        current = _all_cells(artifact)
        allowed = {s.resource for s in session.contract.authorized_mutation_scopes}
        changed_outside = sorted(k for k in session.initial_cells.keys() | current.keys()
                                 if k not in allowed and session.initial_cells.get(k) != current.get(k))
        results.append(_eval("preservation", observation, not changed_outside, "outside scope preserved",
                             observed=changed_outside, kind="constraint_violation"))
        values = [item["value"] for item in facts]
        results.append(_eval("nonblank", observation, all(v not in (None, "") for v in values), "answers nonblank", observed=values))
        expected_type = task.context.get("expected_type")
        type_ok = expected_type is None or all(_type_name(v) == expected_type for v in values)
        results.append(_eval("type", observation, type_ok, "answer types", expected=expected_type,
                             observed=[_type_name(v) for v in values]))
        initial_errors = {key for key, value in session.initial_cells.items()
                          if isinstance(value, str) and value.startswith("#")}
        new_errors = sorted(key for key, value in current.items()
                            if isinstance(value, str) and value.startswith("#") and key not in initial_errors)
        results.append(_eval("formula-errors", observation, not new_errors, "no new formula errors", observed=new_errors))
        if "independent_expected" in task.context:
            expected = task.context["independent_expected"]
            actual = values[0] if len(values) == 1 else values
            results.append(_eval("semantic", observation, actual == expected, "independent computation", expected=expected, observed=actual))
        else:
            results.append(EvalResult("semantic", observation.id, EvalStatus.UNCERTAIN,
                "no independent semantic oracle; structural success is not fulfilment",
                details={"knowledge_gap": True, "confidence": 1.0}))
        if task.context.get("visual_intent"):
            request = CapabilityRequest(str(uuid4()), "render_range", VERSION, str(artifact), KIND,
                {"selector": selectors[0], "output_dir": str(artifact.parent / "renders")}, (), ())
            rendered = session.broker.invoke(session.contract, request)
            results.append(_eval("visual", observation, rendered.succeeded, rendered.error or "render captured",
                                 kind="evaluation_uncertainty"))
        for result in results:
            runtime.event("eval_result", _eval_mapping(result))
        discrepancies = derive_discrepancies(session.contract, results, session.discrepancies)
        for discrepancy in discrepancies:
            runtime.event("discrepancy", _discrepancy_mapping(discrepancy))
        return tuple(results), discrepancies


def _eval(eval_id, observation, passed, message, **details):
    return EvalResult(eval_id, observation.id, EvalStatus.PASS if passed else EvalStatus.FAIL, message, details=details)


def _answer_selectors(context, artifact=None):
    sheet, position = context.get("answer_sheet"), context.get("answer_position")
    if not isinstance(sheet, str) or not isinstance(position, str):
        raise ValueError("answer_sheet and answer_position metadata are required")
    if artifact is None:
        return [f"{sheet}!{position}"]
    wb = load_workbook(artifact, read_only=True)
    synthetic = {"answer_sheet": sheet, "answer_position": position}
    selectors = [f"{resolved_sheet}!{cell}" for resolved_sheet, cell in answer_cells(synthetic, wb)]
    wb.close()
    return selectors


def _contract_mapping(contract, context):
    return {"id": contract.id, "version": contract.version, "intent": contract.intent,
            "description": contract.assertions[0].description,
            "selectors": [s.resource for s in contract.assertions[0].target_scope],
            "expected_type": context.get("expected_type"), "visual_intent": bool(context.get("visual_intent")),
            "has_independent_expected": "independent_expected" in context}


def _contract_from_mapping(value):
    scopes = tuple(Scope(resource) for resource in value["selectors"])
    assertion = DesiredAssertion("answer-state", value.get("description", "answer state holds"), scopes)
    ids = ["artifact-valid", "preservation", "nonblank", "type", "formula-errors", "semantic"]
    if value.get("visual_intent"): ids.append("visual")
    return Contract(value["id"], int(value.get("version", 1)), value["intent"], (assertion,),
                    ("preserve outside scope",), ("valid workbook",),
                    tuple(EvalSpec(i, "answer-state", i) for i in ids), scopes)


def _json_reply(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start: raise ValueError("model reply has no JSON object")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict): raise ValueError("model reply must be object")
    return value


def _model_context(context):
    """Keep independent evaluator inputs isolated from contract/action generation."""
    return {key: value for key, value in context.items() if key != "independent_expected"}


def _selected_cells(path, selectors):
    wb = load_workbook(path, data_only=False); rows = []
    for selector in selectors:
        sheet, coordinates = parse_selector(selector)
        min_col, min_row, max_col, max_row = range_boundaries(coordinates)
        for row in wb[sheet].iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row: rows.append({"selector": f"{sheet}!{cell.coordinate}", "value": cell.value})
    wb.close(); return rows


def _all_cells(path):
    wb = load_workbook(path, data_only=False); result = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None: result[f"workbook/{ws.title}/{cell.coordinate}"] = cell.value
    wb.close(); return result


def _valid(path):
    try:
        wb = load_workbook(path); wb.close(); return True, None
    except Exception as error: return False, f"{type(error).__name__}:{error}"


def _type_name(value):
    if isinstance(value, bool): return "boolean"
    if isinstance(value, (int, float)): return "number"
    if isinstance(value, str) and value.startswith("="): return "formula"
    if isinstance(value, str): return "text"
    if value is None: return "blank"
    return "other"


def _file_hash(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _eval_mapping(result):
    return {"eval_id": result.eval_id, "status": result.status.value, "message": result.message,
            "details": dict(result.details)}


def _discrepancy_mapping(item):
    return {"id": item.id, "kind": item.kind.value, "failed_eval": item.failed_eval_id,
            "expected": item.expected, "observed": item.observed,
            "permissible_mutation_scope": [s.resource for s in item.permissible_mutation_scope]}
