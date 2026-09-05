"""Executable adversarial checks for registered-experiment validity."""

import json
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook

RESEARCH = Path(__file__).resolve().parents[1]
REPO = RESEARCH.parent
sys.path.insert(0, str(RESEARCH))

from backends.spreadsheetbench import bounded_workbook_context, load_runtime_tasks
from fulfilment.completion import decide_completion
from fulfilment.evidence import EvidenceIntegrityError, EvidenceStore
from fulfilment.models import (
    CompletionConditions, Contract, DesiredAssertion, EvalResult, EvalSpec,
    EvalStatus, EvidenceRequirements, Scope,
)
from protocol.selection import validate_manifest
from protocol.readiness import build_report, selector_audit
from services.spreadsheet import _answer_selectors, _model_context


OFFICIAL_SCORER_SHA256 = "8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b"


class LeakageAndSelectionInvariants(unittest.TestCase):
    def test_committed_selection_is_hash_valid_stratified_and_has_no_reference_fields(self):
        value = json.loads((RESEARCH / "protocol" / "development_selection.json").read_text())
        validate_manifest(value)
        counts = {}
        for task in value["tasks"]:
            counts[task["instruction_type"]] = counts.get(task["instruction_type"], 0) + 1
            self.assertFalse(any("golden" in key.lower() or "expected_answer" in key.lower() for key in task))
        self.assertEqual(counts, {"Cell-Level Manipulation": 10, "Sheet-Level Manipulation": 10})

    def test_production_loader_drops_reference_fields_and_never_selects_reference_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); folder = root / "spreadsheet" / "x"; folder.mkdir(parents=True)
            init = folder / "initial.xlsx"; reference = folder / "golden.xlsx"
            wb = Workbook(); wb.active["A1"] = 1; wb.save(init); wb.close()
            reference.write_bytes(b"not a workbook and must not be opened")
            (root / "dataset.json").write_text(json.dumps([{
                "id": "x", "instruction": "set B1", "spreadsheet_path": "spreadsheet/x",
                "instruction_type": "Cell-Level Manipulation", "answer_sheet": None,
                "answer_position": "B1", "golden_xlsx": str(reference), "expected_answer": 9,
            }]))
            task = load_runtime_tasks(root, selected_ids={"x"}, max_cells=10, max_chars=1000)[0]
            serialized = json.dumps(task.context, default=str).lower()
            self.assertNotIn("golden", serialized); self.assertNotIn("expected_answer", serialized)
            self.assertEqual(task.artifact, init)


class ProductionPathInvariants(unittest.TestCase):
    def test_all_available_dataset_selectors_resolve_without_duplicates(self):
        dataset = RESEARCH / "data" / "spreadsheetbench_verified_400"
        if not (dataset / "dataset.json").is_file():
            self.skipTest("dataset not installed; run data/download.py for the all-400 audit")
        audit = selector_audit(dataset)
        self.assertEqual((audit["status"], audit["records"], audit["resolved"]), ("pass", 400, 400))
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["duplicate_selector_tasks"], [])
    def test_truncation_is_explicit_and_counts_omissions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.xlsx"; wb = Workbook()
            for row in range(1, 7): wb.active.cell(row, 1).value = row
            wb.save(path); wb.close()
            observed = bounded_workbook_context(path, max_cells=2, max_chars=1000)
            self.assertTrue(observed["truncation"]["truncated"])
            self.assertEqual(observed["truncation"]["serialized_cells"], 2)
            self.assertEqual(observed["truncation"]["omitted_nonempty_cells"], 4)
            self.assertTrue(observed["omitted_scope"])

    def test_active_sheet_and_explicit_multi_sheet_selectors_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.xlsx"; wb = Workbook(); wb.active.title = "Active"
            wb.create_sheet("Other"); wb.save(path); wb.close()
            self.assertEqual(_answer_selectors({"answer_sheet": None, "answer_position": "B2"}, path), ["Active!B2"])
            selectors = _answer_selectors({"answer_sheet": None, "answer_position": "Active!A1,Other!C3"}, path)
            self.assertEqual(selectors, ["Active!A1", "Other!C3"])

    def test_evaluator_secret_is_isolated_from_both_model_prompts(self):
        context = {"workbook_observation": {"facts": {}}, "independent_expected": 42}
        self.assertNotIn("independent_expected", _model_context(context))
        self.assertNotIn("42", json.dumps(_model_context(context)))

    def test_generic_layer_has_no_spreadsheet_dependency(self):
        for path in (RESEARCH / "fulfilment").glob("*.py"):
            source = path.read_text().lower()
            self.assertNotIn("openpyxl", source, path.name)
            self.assertNotIn("from adapters.spreadsheet", source, path.name)
            self.assertNotIn("from services.spreadsheet", source, path.name)


class CompletionEvidenceAndBudgetInvariants(unittest.TestCase):
    def test_completion_rejects_missing_evidence_and_eval_error(self):
        scope = Scope("artifact/x")
        contract = Contract("c", 1, "intent", (DesiredAssertion("a", "state", (scope,)),), (), (),
                            (EvalSpec("e", "a", "independent"),), (scope,),
                            CompletionConditions(), EvidenceRequirements())
        result = EvalResult("e", "o", EvalStatus.ERROR, "evaluator crashed")
        decision = decide_completion(contract, [result], [], desired_state_satisfied=True,
                                     constraints_preserved=True, invariants_hold=True, artifact_valid=True)
        self.assertFalse(decision.fulfilled)
        self.assertIn("required_evals_not_passed", decision.failed_conditions)
        self.assertIn("required_evidence_missing", decision.failed_conditions)

    def test_hash_chained_evidence_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.jsonl"; store = EvidenceStore(path)
            store.append("observation", {"artifact_hash": "a"})
            original = path.read_text(); path.write_text(original.replace('"a"', '"b"'))
            with self.assertRaises(EvidenceIntegrityError): store.verify()

    def test_preregistered_budgets_and_retry_are_enforced_by_shared_runtime(self):
        protocol = json.loads((RESEARCH / "protocol" / "preregistered_experiment.json").read_text())
        fixed = protocol["fixed_conditions"]
        self.assertEqual((fixed["token_budget"], fixed["action_budget"], fixed["wall_clock_seconds"]), (16000, 12, 300))
        runner_source = (RESEARCH / "experiment" / "runner.py").read_text()
        self.assertIn("retry_policy", runner_source)
        self.assertIn("config.retry_policy", runner_source)
        self.assertIn("model_transport_retry", runner_source)


class RegisteredRunBlockerSentinels(unittest.TestCase):
    """These pass when known blockers remain, preventing accidental overclaiming."""

    def test_production_backend_has_no_independent_semantic_input(self):
        source = (RESEARCH / "backends" / "spreadsheetbench.py").read_text()
        context_projection = source.split("context = {key: record[key]", 1)[1].split("tasks.append", 1)[0]
        self.assertNotIn("independent_expected", context_projection)

    def test_isolated_semantic_evaluator_replaces_missing_fixture_oracle(self):
        source = (RESEARCH / "services" / "spreadsheet.py").read_text()
        self.assertIn("def _semantic_model_eval", source)
        self.assertIn('purpose="independent_evaluation"', source)
        self.assertIn("current_target_facts", source)

    def test_spreadsheet_reconciler_uses_evidence_completion_gate(self):
        source = (RESEARCH / "services" / "spreadsheet.py").read_text()
        reconcile = source.split("def reconcile", 1)[1].split("def _session", 1)[0]
        self.assertIn("decide_completion", reconcile)
        self.assertIn("session.evidence.records()", reconcile)
        self.assertIn('session.evidence.append("termination_decision"', reconcile)
        self.assertIn('ExecutionResult(destination, "fulfilled"', reconcile)

    def test_custom_reconcile_still_does_not_use_generic_agent_semantics(self):
        source = (RESEARCH / "services" / "spreadsheet.py").read_text()
        reconcile = source.split("def reconcile", 1)[1].split("def _completion_decision", 1)[0]
        self.assertIn("for iteration in range", reconcile)
        self.assertNotIn("FulfilmentAgent", source)
        self.assertNotIn("no_progress", reconcile)

    def test_output_manifest_preserves_outer_reproducibility_envelope(self):
        runner = (RESEARCH / "experiment" / "runner.py").read_text()
        prepare = runner.split("def _prepare", 1)[1].split("def run", 1)[0]
        self.assertIn('manifest["source_manifest"]', prepare)
        self.assertIn('"input_manifest.json"', prepare)

    def test_internal_status_and_termination_reason_are_projected_by_runner(self):
        source = (RESEARCH / "experiment" / "runner.py").read_text()
        result_projection = source.split('result = {', 1)[1].split('runtime.event("task_finished"', 1)[0]
        self.assertIn('"internal_status"', result_projection)
        self.assertIn('"termination_reason"', result_projection)

    def test_root_dockerfile_is_canonical_and_hardened(self):
        candidates = sorted(REPO.rglob("Dockerfile"))
        self.assertEqual(candidates, [REPO / "Dockerfile"])
        root = candidates[0].read_text()
        self.assertIn("libreoffice-calc", root)
        self.assertIn("USER runner", root)
        self.assertIn("container_preflight", root)

    def test_official_scorer_is_immutable_at_audited_hash(self):
        digest = sha256((RESEARCH / "evaluate.py").read_bytes()).hexdigest()
        self.assertEqual(digest, OFFICIAL_SCORER_SHA256)

    def test_machine_readiness_stays_blocked_with_named_code_and_environment_gaps(self):
        report = build_report()
        self.assertFalse(report["registered_run_ready"])
        self.assertEqual(report["decision"], "BLOCKED")
        self.assertTrue({"R-01", "R-03"} <= {item["id"] for item in report["blockers"]})
        self.assertNotIn("R-02", {item["id"] for item in report["blockers"]})
        self.assertEqual(
            report["original_finding_status"]["V-06"]["status"],
            "resolved_static_external_smoke_pending",
        )

    def test_factory_provides_fresh_session_container_per_run(self):
        from backends.spreadsheetbench import factory
        # Object construction requires no dataset when freshness is checked at
        # the service type boundary; the factory itself returns SpreadsheetServices().
        source = (RESEARCH / "backends" / "spreadsheetbench.py").read_text()
        self.assertIn("return SpreadsheetServices(), provider, tasks", source)


if __name__ == "__main__": unittest.main()
