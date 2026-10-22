"""Frozen P1 behavior: adding P2 must not reinterpret these contracts."""

from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity, validate
from memory_order_analyzer.protocol import expected_protocol
from memory_order_analyzer.report import make_report
from memory_order_analyzer.scope import index_scope
from test_scope_report import add_graph, scope, symbol


def test_frozen_p1_protocol():
    assert expected_protocol() == {
        "protocol_version": 1, "extractor_version": "0.2.0", "llvm_version": "21.1.8",
        "facts_version": 2, "report_version": 2,
        "policy": {"version": 1, "max_nodes": 100000, "max_references": 500000,
                   "max_constant_depth": 64, "max_output_bytes": 16777216},
    }


def test_frozen_p1_scope_and_partial_report(fixture_module, fixture_artifact):
    key = fixture_artifact["artifact_key"]
    module = fixture_module
    module["functions"] = [symbol("local", key, "internal"),
                           symbol("helper", key, "linkonce", comdat=True)]
    module["calls"] = [{"id": "call", "kind": "direct", "target": "helper",
                        "source": {"inline_chain": []}}]
    add_graph(module)
    module["calls"][0].update(attributes="i32 noundef", attribute_status="unknown", status="unknown")
    module["extraction"].update(status="partial", unknown=1, diagnostics=[
        {"id": "call", "reason": "uninterpreted_abi_attributes"}])
    before = deepcopy(module)
    validate(module, "ModuleFacts")
    index = index_scope(scope([key]), {key: fixture_artifact}, {key: module})
    assert index["schema_version"] == 1
    assert index["bindings"] == []
    assert index["unknown"] == [{
        "reference": {"id": "call", "symbol": "helper", "kind": "call"},
        "reason": "ambiguous_or_interposable",
        "candidates": [{"artifact_key": key, "symbol_id": key + ":symbol:helper",
                        "linkage": "linkonce", "comdat": True}],
    }]
    assert index["capabilities"] == {"direct_symbols": True, "points_to": False,
        "effect_propagation": False, "callsite_specialization": False,
        "threads": False, "memory_model": False}
    report = make_report("index", planned=1, artifacts=[fixture_artifact], facts=[module], scope=index)
    assert report["schema_version"] == 2
    assert report["semantic_analysis"] == report["stages"]["semantic_analysis"] == "not_run"
    assert report["safety"] == "not_evaluated" and report["findings"] is None
    assert report["fact_extraction"] == {
        "status": "partial", "planned": 1, "complete": 0, "partial": 1,
        "failed": 0, "complete_ratio": 0.0,
        "diagnostics": [{"artifact_key": key, "id": "call", "reason": "uninterpreted_abi_attributes"}],
    }
    assert report["exit_code"] == 2 and report["scope_status"] == "partial"
    assert module == before
    assert index == index_scope(scope([key]), {key: fixture_artifact}, {key: module})
    assert fixture_artifact["profile"] == "source-preserving"


@pytest.mark.parametrize("kind", ["ModuleFacts", "RunReport"])
def test_frozen_v2_contract_rejects_derived_fields(kind, fixture_module):
    value = fixture_module if kind == "ModuleFacts" else make_report("doctor", ready=True)
    frozen = identity(value)
    for version in (1, 3):
        with pytest.raises(AnalysisError):
            validate({**value, "schema_version": version}, kind)
    with pytest.raises(AnalysisError):
        validate({**value, "effect_summaries": []}, kind)
    assert identity(value) == frozen
