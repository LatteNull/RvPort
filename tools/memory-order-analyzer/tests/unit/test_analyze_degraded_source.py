from copy import deepcopy
import json

import pytest

import memory_order_analyzer.analyze_degraded_source as degraded_module
from memory_order_analyzer.analyze_degraded_source import analyze_degraded_source, failed_degraded_report
from memory_order_analyzer.contracts import AnalysisError, canonical, document, identity
from memory_order_analyzer.degraded_contracts import (
    degraded_document, dependency, expected_degraded_protocol, failure_record, input_hash,
)
from memory_order_analyzer.protocol import expected_protocol
from memory_order_analyzer.source_contracts import (
    counts, expected_source_protocol, semantic_digest as source_digest, source_document,
)
from memory_order_analyzer.source_profile import build_profile


def setup_request(tmp_path, *, include_ir=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "unit.c"
    source.write_text("_Atomic int flag;\n", encoding="utf-8")
    profile = build_profile(
        {"directory": str(tmp_path), "file": "unit.c",
         "arguments": ["clang", "-std=c17", "-c", "unit.c"]},
        compiler_version="21.1.8")
    physical = "a" * 64
    source_request = source_document(
        "SourceSemanticRequest", profile=profile, physical_tu_id=physical,
        source_path=str(source), budgets=expected_source_protocol()["budgets"])
    source_path = tmp_path / "source-request.json"
    source_path.write_text(canonical(source_request), encoding="utf-8")
    ir_refs = []
    ir_request = None
    if include_ir:
        bitcode = tmp_path / "unit.bc"; bitcode.write_bytes(b"bitcode")
        from memory_order_analyzer.contracts import file_hash
        ir_request = source_document(
            "LLVMSourceBindingRequest", artifact_key="b" * 64, profile_id=profile["profile_id"],
            physical_tu_id=physical, bitcode={"path": str(bitcode), "sha256": file_hash(bitcode)},
            budgets=expected_source_protocol()["budgets"])
        ir_path = tmp_path / "ir-request.json"; ir_path.write_text(canonical(ir_request), encoding="utf-8")
        ir_refs = [input_hash(ir_path)]
    request = degraded_document(
        "DegradedSourceAnalysisRequest", scope_id="scope", source_requests=[input_hash(source_path)],
        ir_requests=ir_refs, module_facts=[], declared_failures=[],
        products={"thread_graph": None, "publication_graph": None, "publication_report": None},
        budgets=expected_degraded_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request), encoding="utf-8")
    return request_path, source_request, ir_request


def source_facts(source_request):
    physical = source_request["physical_tu_id"]
    expression = {"id": "expr", "kind": "atomic-expression", "name": "", "qualified_name": "",
                  "usr": None, "mangled_name": None, "canonical_decl": "expr", "definition": False,
                  "definition_kind": "declaration", "linkage": "none", "language_linkage": "none",
                  "storage": "none", "visibility": "unknown", "tls": False,
                  "canonical_type": "expression", "abi": {}, "source": {}, "macro_stack": [], "attributes": []}
    relation = {"id": "relation", "kind": "atomic", "from": "expr", "to": None,
                "source": {}, "status": "candidate", "reason": None}
    return source_document(
        "SourceSemanticFacts", profile_id=source_request["profile"]["profile_id"],
        physical_tu_id=physical, source_digest=source_request["profile"]["source"]["sha256"],
        status="complete", nodes=[expression], relations=[relation],
        counts={"nodes": counts(1), "relations": counts(1)}, diagnostics=[], frontier=[], semantic_digest=None)


def ir_facts(ir_request):
    return source_document(
        "LLVMSourceBindingFacts", artifact_key=ir_request["artifact_key"],
        profile_id=ir_request["profile_id"], physical_tu_id=ir_request["physical_tu_id"],
        bitcode_digest=ir_request["bitcode"]["sha256"], target="x86_64-pc-linux-gnu",
        data_layout="e-p:64:64", status="complete", symbols=[],
        counts={"symbols": counts(0)}, diagnostics=[], frontier=[], semantic_digest=None)


def test_orchestration_ast_only_keeps_source_candidate_and_never_exits_risk(tmp_path):
    request_path, source_request, _ = setup_request(tmp_path)
    artifact_store = tmp_path / "artifacts"; artifact_store.mkdir()
    output = tmp_path / "output"
    report = analyze_degraded_source(
        request_path, artifact_store, output, "source-worker", "ir-worker",
        source_runner=lambda request, worker, directory: source_facts(source_request))
    assert report["mode"] == "ast-only" and report["status"] == "partial" and report["exit_code"] == 2
    assert len(report["source_candidates"]) == 1 and report["formal_assessments"] == []
    assert (output / "availability" / f"{'a' * 64}.json").is_file()
    assert json.loads((output / "report.json").read_text())["semantic_digest"] == report["semantic_digest"]
    cached = analyze_degraded_source(
        request_path, artifact_store, tmp_path / "cached", "source-worker", "ir-worker",
        source_runner=lambda request, worker, directory: (_ for _ in ()).throw(AssertionError("cache miss")))
    assert cached["semantic_digest"] == report["semantic_digest"] and cached["cache"]["hits"] > 0


def test_orchestration_ir_only_survives_source_failure_and_cache_is_stable(tmp_path):
    request_path, _, ir_request = setup_request(tmp_path, include_ir=True)
    artifact_store = tmp_path / "artifacts"; artifact_store.mkdir()
    def fail_source(request, worker, directory):
        raise AnalysisError("syntax_error", "bad source")
    report = analyze_degraded_source(
        request_path, artifact_store, tmp_path / "first", "source-worker", "ir-worker",
        source_runner=fail_source, ir_runner=lambda request, worker, directory: ir_facts(ir_request))
    assert report["mode"] == "ir-only" and report["exit_code"] == 2
    assert report["stages"]["source"]["failed"] == 1
    second = analyze_degraded_source(
        request_path, artifact_store, tmp_path / "second", "source-worker", "ir-worker",
        source_runner=fail_source, ir_runner=lambda request, worker, directory: ir_facts(ir_request))
    assert second["semantic_digest"] == report["semantic_digest"]
    assert second["cache"]["hits"] > report["cache"]["hits"]


def test_orchestration_failed_output_rules_and_failure_report(tmp_path):
    request_path, _, _ = setup_request(tmp_path)
    artifact_store = tmp_path / "artifacts"; artifact_store.mkdir()
    def fail_source(request, worker, directory):
        raise AnalysisError("missing_include", "generated.h")
    report = analyze_degraded_source(
        request_path, artifact_store, tmp_path / "output", "source-worker", "ir-worker",
        source_runner=fail_source)
    assert report["mode"] == "failed" and report["exit_code"] == 1
    with pytest.raises(AnalysisError, match="fresh"):
        analyze_degraded_source(request_path, artifact_store, tmp_path / "output",
                                "source-worker", "ir-worker", source_runner=fail_source)
    failure = failed_degraded_report("bad", "坏请求", "Bad request")
    assert failure["exit_code"] == 1 and failure["safety"] == "not-established"


def test_request_dependency_replacement_is_rejected_before_worker(tmp_path):
    request_path, _, _ = setup_request(tmp_path)
    request = json.loads(request_path.read_text())
    source_path = request["source_requests"][0]["path"]
    with open(source_path, "w", encoding="utf-8") as stream:
        stream.write("{}")
    with pytest.raises(AnalysisError, match="changed"):
        analyze_degraded_source(request_path, tmp_path / "artifacts", tmp_path / "output",
                                "source-worker", "ir-worker")


def test_ir_failure_ast_ir_module_mapping_and_candidate_budget(tmp_path):
    request_path, source_request, ir_request = setup_request(tmp_path, include_ir=True)
    artifact_store = tmp_path / "artifacts"; (artifact_store / "facts").mkdir(parents=True)
    module = document(
        "ModuleFacts", artifact_key=ir_request["artifact_key"], module_hash="c" * 64,
        target="x86_64-pc-linux-gnu", layout="e-p:64:64", producer=[], functions=[], globals=[],
        events=[], calls=[], capabilities={}, source_mapping="unavailable", values=[],
        protocol=expected_protocol(), extraction={"status": "complete", "roots": 0, "nodes": 0,
        "references": 0, "unknown": 0, "diagnostics": []})
    (artifact_store / "facts" / f"{ir_request['artifact_key']}.json").write_text(canonical(module), encoding="utf-8")
    request = json.loads(request_path.read_text())
    request["module_facts"] = [dependency("ModuleFacts", ir_request["artifact_key"], module)]
    request["budgets"]["source_candidates"] = 1
    request = degraded_document(**{key: value for key, value in request.items()
                                   if key not in {"schema_version", "kind", "analysis_version", "policy_id"}},
                                kind="DegradedSourceAnalysisRequest")
    request_path.write_text(canonical(request), encoding="utf-8")
    value = source_facts(source_request)
    second = deepcopy(value["relations"][0]); second["id"] = "relation-2"; second["kind"] = "read"
    value["relations"].append(second); value["relations"].sort(key=lambda item: item["id"])
    value["semantic_digest"] = source_digest(value)
    report = analyze_degraded_source(
        request_path, artifact_store, tmp_path / "output", "source-worker", "ir-worker",
        source_runner=lambda *args: value, ir_runner=lambda *args: ir_facts(ir_request))
    assert report["mode"] == "ast-ir" and report["exit_code"] == 2
    assert report["stages"]["source_candidates"]["budget"] == 1
    availability = json.loads(next((tmp_path / "output" / "availability").glob("*.json")).read_text())
    assert {item["stage"]: item["status"] for item in availability["products"]}["p1"] == "complete"

    request_path2, source_request2, ir_request2 = setup_request(tmp_path / "other", include_ir=True)
    store2 = tmp_path / "other-store"; store2.mkdir()
    failed = analyze_degraded_source(
        request_path2, store2, tmp_path / "other-output", "source-worker", "ir-worker",
        source_runner=lambda *args: source_facts(source_request2),
        ir_runner=lambda *args: (_ for _ in ()).throw(OSError("worker crashed")))
    assert failed["mode"] == "ast-only" and failed["stages"]["bc"]["failed"] == 1


def test_formal_product_checks_and_dependency_adoption(monkeypatch, tmp_path):
    real_read_hashed = degraded_module._read_hashed
    request = {"products": {"thread_graph": {"path": "thread", "sha256": "a" * 64},
                            "publication_graph": {"path": "graph", "sha256": "b" * 64},
                            "publication_report": {"path": "report", "sha256": "c" * 64}}}
    graph = {"assessments": []}
    report = {"graph": {"digest": identity(graph)}}
    values = iter([{"diagnostics": [], "frontier": []}, graph, report])
    monkeypatch.setattr(degraded_module, "_read_hashed", lambda *args: next(values))
    thread, read_graph, read_report = degraded_module._formal_products("request", request)
    assert thread is not None and read_graph == graph and read_report == report
    bad_values = iter([{}, graph, {"graph": None}])
    monkeypatch.setattr(degraded_module, "_read_hashed", lambda *args: next(bad_values))
    with pytest.raises(AnalysisError, match="do not match"):
        degraded_module._formal_products("request", request)

    request_path, source_request, _ = setup_request(tmp_path / "run")
    monkeypatch.setattr(degraded_module, "_read_hashed", real_read_hashed)
    monkeypatch.setattr(degraded_module, "_formal_products", lambda *args: (
        {"diagnostics": [], "frontier": []}, {"assessments": []}, {}))
    result = analyze_degraded_source(
        request_path, tmp_path / "run-store", tmp_path / "run-output", "source", "ir",
        source_runner=lambda *args: source_facts(source_request))
    kinds = {item["kind"] for item in result["dependencies"]}
    assert {"ThreadContextGraph", "SinglePublicationProtocolGraph"} <= kinds


def test_request_timeout_output_limit_failed_fact_and_io_classification(monkeypatch, tmp_path):
    real_monotonic = degraded_module.monotonic
    request_path, source_request, _ = setup_request(tmp_path / "failed-fact")
    unusable = source_facts(source_request); unusable["status"] = "failed"; unusable["semantic_digest"] = source_digest(unusable)
    report = analyze_degraded_source(
        request_path, tmp_path / "store1", tmp_path / "out1", "source", "ir",
        source_runner=lambda *args: unusable)
    assert report["exit_code"] == 1

    request_path, source_request, _ = setup_request(tmp_path / "io")
    report = analyze_degraded_source(
        request_path, tmp_path / "store2", tmp_path / "out2", "source", "ir",
        source_runner=lambda *args: (_ for _ in ()).throw(OSError("I/O")))
    assert report["exit_code"] == 1 and report["diagnostics"]

    request_path, source_request, _ = setup_request(tmp_path / "timeout")
    ticks = iter([0, 4001])
    monkeypatch.setattr(degraded_module, "monotonic", lambda: next(ticks))
    with pytest.raises(AnalysisError, match="request budget"):
        analyze_degraded_source(request_path, tmp_path / "store3", tmp_path / "out3", "source", "ir",
                                source_runner=lambda *args: source_facts(source_request))

    monkeypatch.setattr(degraded_module, "monotonic", real_monotonic)
    request_path, source_request, _ = setup_request(tmp_path / "output-limit")
    request = json.loads(request_path.read_text())
    request["budgets"]["request_output_bytes"] = 4096
    request["declared_failures"] = sorted([
        failure_record("a" * 64, "p2", f"failure-{index}", "x" * 300)
        for index in range(30)], key=lambda item: item["id"])
    request = degraded_document(**{key: value for key, value in request.items()
                                   if key not in {"schema_version", "kind", "analysis_version", "policy_id"}},
                                kind="DegradedSourceAnalysisRequest")
    request_path.write_text(canonical(request), encoding="utf-8")
    with pytest.raises(AnalysisError, match="output budget"):
        analyze_degraded_source(request_path, tmp_path / "store4", tmp_path / "out4", "source", "ir",
                                source_runner=lambda *args: source_facts(source_request))
