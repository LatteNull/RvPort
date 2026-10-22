"""P2 schema/version tests, separate from solver and integration behavior."""

from copy import deepcopy
import json

import jsonschema
import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity, validate
from memory_order_analyzer.effect_contracts import (
    KINDS, ROOT, effect_document, expected_analysis_protocol, read_effect_document,
    validate_effect_document,
)


def origin():
    return {"artifact_key": "a" * 64, "module_hash": "b" * 64, "facts_hash": "c" * 64,
            "extractor_version": "0.2.0", "llvm_version": "21.1.8", "profile": "source-preserving"}


def samples():
    budgets = expected_analysis_protocol()["budgets"]
    root = {"artifact_key": "a" * 64, "function_id": "f", "arguments": []}
    counts = {"planned": 0, "complete": 0, "partial": 0, "failed": 0, "not_run": 0, "complete_ratio": None}
    evaluation = effect_document("LocalEvaluationRequest", scope_id="d" * 64, context_id="context",
        function={"artifact_key": "a" * 64, "function_id": None, "id": "f"}, invocation_id="root-instance",
        invocations=[dict(id="root-instance", context_id="context", function={"artifact_key": "a" * 64, "function_id": None, "id": "f"},
                          parent_id=None, callsite=None, cardinality="single", reason=None)],
        origins=[origin()], arguments=[], adoptions=[], dependencies=[], call_bindings=[],
        local_dependencies=[dict(artifact_key="a" * 64, digest="b" * 64)], budgets=budgets)
    return {
        "LocalEvaluationRequest": evaluation,
        "LocalEvaluationResult": effect_document("LocalEvaluationResult", request=evaluation, request_hash=identity(evaluation),
            scope_id=evaluation["scope_id"], context_id="context", budgets=budgets, values=[], blocks=[], call_requests=[],
            effects=[], order=[], returns=[], escape=[], resolutions=[], frontier=[], diagnostics=[], status="not_run", steps=0),
        "EffectAnalysisRequest": effect_document("EffectAnalysisRequest", scope="scope.json",
            mode="roots", roots=[root], budgets=budgets),
        "LocalAnalysisFacts": effect_document("LocalAnalysisFacts", origin=origin(), budgets=budgets,
            functions=[], calls=[], objects=[], ir_nodes=[], analysis_evidence=[], resolutions=[], diagnostics=[], status="not_run"),
        "EffectSummary": effect_document("EffectSummary", scope_id="d" * 64, context_id="context",
            root_invocation_id="root-instance", invocations=[{
                "id": "root-instance", "context_id": "context", "function": {
                    "artifact_key": "a" * 64, "function_id": None, "id": "f"},
                "parent_id": None, "callsite": None, "cardinality": "single", "reason": None}],
            root=root, origins=[origin()], budgets=budgets, effects=[], order=[], returns=[], escape=[],
            adoptions=[], dependencies=[], local_dependencies=[], resolutions=[], diagnostics=[], status="not_run"),
        "EffectAnalysisReport": effect_document("EffectAnalysisReport", request_hash=None, scope_id=None,
            budgets=budgets, input_integrity="not_run", raw_fact_extraction="not_run", local_analysis="not_run",
            interprocedural_analysis="not_run", source_mapping="not_run", members=[], roots=[], contexts=[],
            member_counts=counts, root_counts=counts, context_counts=counts, frontier=[], summaries=[],
            resolutions=[], diagnostics=[], local_dependencies=[], assumptions=[], safety="not_evaluated", findings=None, exit_code=1),
    }


@pytest.mark.parametrize("kind", KINDS)
def test_schema_roundtrip_and_old_consumer_rejection(kind, tmp_path):
    value = samples()[kind]
    path = tmp_path / "derived.json"
    path.write_text(canonical(value))
    assert read_effect_document(path, kind) == value
    assert validate_effect_document(value, kind) is value
    with pytest.raises(AnalysisError, match="Unknown contract"):
        validate(value, kind)
    for field in value:
        invalid = deepcopy(value)
        del invalid[field]
        with pytest.raises(AnalysisError):
            validate_effect_document(invalid, kind)
    for field, replacement in [("schema_version", 2), ("schema_version", True), ("kind", "Unknown"),
                               ("extra", []), ("analysis_version", "0.2.0"), ("policy_id", "future")]:
        with pytest.raises(AnalysisError):
            validate_effect_document({**value, field: replacement}, kind)
    for invalid in [None, [], True]:
        with pytest.raises(AnalysisError):
            validate_effect_document(invalid, kind)


def test_all_schemas_are_valid_and_protocol_is_pinned():
    schema = json.loads((ROOT / "schemas/effects.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    protocol = expected_analysis_protocol()
    assert protocol["kinds"] == dict.fromkeys(KINDS, 1)
    assert protocol["analysis_version"] == "0.1.0" and protocol["llvm_version"] == "21.1.8"
    assert protocol["policy_id"] == "scoped-effects-v1"
    assert protocol["budgets"] == {
        "local_steps": 100000, "condition_states": 32, "value_candidates": 8,
        "contexts_per_function": 32, "contexts_per_request": 4096, "scc_iterations": 16,
        "effect_items": 10000, "worker_seconds": 60, "worker_output_bytes": 16777216,
        "request_seconds": 300, "request_output_bytes": 67108864,
    }


def test_protocol_and_disk_errors(tmp_path):
    path = tmp_path / "protocol.json"
    with pytest.raises(AnalysisError):
        expected_analysis_protocol(path)
    for contents in ["broken", "null", "{}", canonical({**expected_analysis_protocol(), "protocol_version": True})]:
        path.write_text(contents)
        with pytest.raises(AnalysisError, match="protocols/analysis-protocol.json"):
            expected_analysis_protocol(path)
    path.write_text(canonical(expected_analysis_protocol()))
    assert expected_analysis_protocol(path) == expected_analysis_protocol()
    for source in [tmp_path / "absent", path]:
        if source == path:
            source.write_text("invalid JSON")
        with pytest.raises(AnalysisError) as caught:
            read_effect_document(source, "EffectSummary")
        assert caught.value.code == "input_invalid"
    with pytest.raises(AnalysisError, match="Unknown effect"):
        validate_effect_document({}, "Future")


def test_request_modes_budgets_and_values():
    request = samples()["EffectAnalysisRequest"]
    assert validate_effect_document({**request, "mode": "all-defined", "roots": []}, "EffectAnalysisRequest")
    for patch in [{"roots": []}, {"mode": "all-defined"}, {"roots": request["roots"] * 2}]:
        with pytest.raises(AnalysisError):
            validate_effect_document({**request, **patch}, "EffectAnalysisRequest")
    for name, maximum in request["budgets"].items():
        for bad in [0, -1, True, maximum + 1, "1"]:
            with pytest.raises(AnalysisError):
                validate_effect_document({**request, "budgets": {**request["budgets"], name: bad}}, "EffectAnalysisRequest")
        validate_effect_document({**request, "budgets": {**request["budgets"], name: 1}}, "EffectAnalysisRequest")
    values = [
        {"kind": "integer", "bits": 128, "hex": "10000000000000001"},
        {"kind": "object", "source": {"artifact_key": "a" * 64, "function_id": None, "id": "x"}, "offset": "-4", "address_space": 0, "allocation": None},
        {"kind": "parameter", "source": {"artifact_key": "a" * 64, "function_id": "f", "id": "arg"}, "invocation_id": None},
        {"kind": "null", "address_space": 0},
        *[{"kind": kind, "reason": "not-a-known-value"} for kind in ("unknown", "undef", "poison", "freeze")],
        {"kind": "expression", "source": {"artifact_key": "a" * 64, "function_id": "f", "id": "add"}, "operands": [], "invocation_id": None},
    ]
    for value in values:
        changed = deepcopy(request)
        changed["roots"][0]["arguments"] = [value]
        validate_effect_document(changed, "EffectAnalysisRequest")
        value["unsupported_field"] = 1
        with pytest.raises(AnalysisError):
            validate_effect_document(changed, "EffectAnalysisRequest")


def test_local_evaluation_stays_separate_from_module_facts_and_public_roots():
    """Resolved gap: independent kinds do not widen the module/public-root shape."""
    local = samples()["LocalAnalysisFacts"]
    local["evaluation"] = {"context_id": "c", "invocation_id": "i", "bindings": [], "values": []}
    with pytest.raises(AnalysisError, match="evaluation"):
        validate_effect_document(local, "LocalAnalysisFacts")
    request = samples()["EffectAnalysisRequest"]
    request["roots"][0]["arguments"] = [{"kind": "candidates", "values": [
        {"kind": "integer", "bits": 32, "hex": "1"}, {"kind": "integer", "bits": 32, "hex": "2"}]}]
    with pytest.raises(AnalysisError):
        validate_effect_document(request, "EffectAnalysisRequest")


@pytest.mark.parametrize("definition,entry", [
    ("Invocation", {"id": "i", "context_id": "c", "function": {"artifact_key": "a" * 64, "function_id": None, "id": "f"},
                    "parent_id": None, "callsite": None, "cardinality": "single", "reason": None}),
    ("Allocation", {"invocation_id": "i", "cardinality": "merged", "reason": "loop"}),
    ("Guard", {"invocation_id": "i", "source": {"artifact_key": "a" * 64, "function_id": "f", "id": "br"}, "edge": 0, "multiplicity": "single"}),
])
def test_instance_schema_required_fields_and_unknown_fields(definition, entry):
    schema = json.loads((ROOT / "schemas/effects.json").read_text())
    validator = jsonschema.Draft202012Validator({"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]})
    validator.validate(entry)
    for field in entry:
        invalid = deepcopy(entry)
        del invalid[field]
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)
    for invalid in [{**entry, "future": True}, {**entry, "invocation_id": False}]:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)
