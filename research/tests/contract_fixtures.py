import json
from dataclasses import asdict

from adapters.spreadsheet import manifests


def capability_records():
    rows = []
    for manifest in manifests():
        value = asdict(manifest)
        value["effect"] = manifest.effect.value
        value["possible_mutation_scope"] = [scope.resource for scope in manifest.possible_mutation_scope]
        rows.append(value)
    return tuple(rows)


def contract_reply(description="target contains the computed result", *, property="computed_value",
                   output_type="number", shape="scalar", uncertainty_allowed=False,
                   evaluator="semantic-independent", capability="write_cells",
                   extra=None):
    value = {
        "schema_version": "2.0.0",
        "desired_state": {"assertions": [{
            "id": "answer-state", "property": property, "description": description,
            "output": {"type": output_type, "shape": shape,
                       "uncertainty_allowed": uncertainty_allowed},
        }]},
        "constraints": ["unselected cells retain their prior state"],
        "invariants": ["workbook remains loadable and formulas remain valid"],
        "evaluator_intents": [{"id": "semantic-check", "assertion_id": "answer-state",
                              "evaluator": evaluator, "purpose": "independently verify the requested result"}],
        "required_capabilities": [{"name": capability, "version": "1.0.0"}],
    }
    if extra: value.update(extra)
    return json.dumps(value)
