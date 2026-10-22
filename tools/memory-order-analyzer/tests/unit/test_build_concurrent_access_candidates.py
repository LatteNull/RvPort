from copy import deepcopy
import importlib
import json

import pytest

from memory_order_analyzer import build_concurrent_access_candidates as builder
from memory_order_analyzer import cli
from memory_order_analyzer.concurrent_access_contracts import (
    concurrent_access_document, expected_concurrent_access_protocol, semantic_digest,
)
from memory_order_analyzer.contracts import AnalysisError, identity


A, B, C = "a" * 64, "b" * 64, "c" * 64


def artifacts():
    plan = {
        "kind": "RootDrivenAnalysisPlan", "scope_id": "scope", "status": "complete",
        "semantic_digest": A, "contexts": [{"id": "ctx", "entry": {"artifact_key": B,
                                                                        "function_id": "worker"}}],
        "demands": [{"id": "d", "root_id": "worker", "context_id": "ctx",
                     "entry": {"artifact_key": B, "function_id": "worker"},
                     "physical_tu_id": "tu"}],
        "reachable_functions": [{"id": "r", "root_id": "worker",
                                  "entry": {"artifact_key": B, "function_id": "worker"}}],
        "frontier": [],
    }
    overlay = {
        "kind": "ThreadEntryRootOverlay", "scope_id": "scope", "status": "complete",
        "semantic_digest": B,
        "roots": [{"id": "worker", "kind": "c11-thrd", "context_id": "ctx",
                   "creation_site_id": "site", "source_site_id": "site", "cardinality": "single",
                   "entry": {"artifact_key": B, "function_id": "worker"}}],
        "contexts": [{"id": "ctx", "entry": {"artifact_key": B, "function_id": "worker"}}],
        "demands": [{"id": "d2", "root_id": "worker", "context_id": "ctx",
                     "entry": {"artifact_key": B, "function_id": "worker"},
                     "physical_tu_id": "tu"}], "frontier": [],
    }
    summary = {
        "kind": "EffectSummary", "scope_id": "scope", "context_id": "ctx", "status": "complete",
        "semantic_digest": C, "root": {"artifact_key": B, "function_id": "worker"},
        "effects": [{"id": "write", "kind": "write", "source": {"id": "store"},
                     "address": {"domain_id": "shared"}, "size_bytes": "4", "atomic": False,
                     "volatile": False, "ordering": None, "failure_ordering": None,
                     "guards": [], "multiplicity": "single", "proof": []}],
    }
    provenance = {
        "kind": "BoundedObjectProvenanceGraph", "scope_id": "scope", "status": "complete",
        "semantic_digest": identity({"p": 1}), "domains": [{"id": "shared", "domain": {
            "state": "must", "reason": None, "candidates": [{"guards": [], "proof": [],
                "opposed": [], "object": {"id": "shared-object", "storage": {"id": "global",
                "kind": "global"}, "path": [], "byte_range": {"offset": 0, "size": 4},
                "address_space": 0}}]}}], "frontier": [],
    }
    return {"plan": plan, "overlay": overlay, "summary": summary, "provenance": provenance}


def request(values=None, **budget_updates):
    values = values or artifacts()
    producers = {"plan": "execution-root-driven-analysis-v1", "overlay": "thread-entry-discovery-v1",
                 "summary": "scoped-effects-v1", "provenance": "bounded-object-provenance-v1"}
    evidence = []
    for key, value in values.items():
        evidence.append({"kind": value["kind"], "id": key, "digest": identity(value),
                         "path": f"{key}.json", "schema_version": 1,
                         "producer": producers[key]})
    evidence.sort(key=lambda item: (item["kind"], item["id"]))
    budgets = deepcopy(expected_concurrent_access_protocol()["budgets"]); budgets.update(budget_updates)
    return concurrent_access_document(
        "ConcurrentAccessCandidateRequest", scope_id="scope", closed_scope=True,
        target="x86_64-linux-gnu", data_layout="e-p:64:64", abi="itanium",
        members=[{"physical_tu_id": "tu", "profile_id": A, "language": "c", "standard": "c11",
                  "source_digest": A, "bc_digest": B, "source_ir_binding_digest": C}],
        evidence=evidence, budgets=budgets, semantic_digest=None)


def test_orchestrator_cold_warm_outputs_are_deterministic(tmp_path, monkeypatch):
    values = artifacts(); req = request(values)
    monkeypatch.setattr(builder, "read_concurrent_access_document", lambda path, kind: req)
    monkeypatch.setattr(builder, "_resolve_dependency", lambda store, ref: values[ref["id"]])
    store = tmp_path / "store"; store.mkdir()
    cold = builder.build_concurrent_access_candidates("request.json", store, tmp_path / "cold")
    warm = builder.build_concurrent_access_candidates("request.json", store, tmp_path / "warm")
    assert cold["status"] == warm["status"] == "complete"
    assert cold["cache"] == {"hits": 0, "misses": 4}
    assert warm["cache"] == {"hits": 4, "misses": 0}
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert cold["safety"] == "not_evaluated" and cold["findings"] is None
    names = {path.relative_to(tmp_path / "cold").as_posix()
             for path in (tmp_path / "cold").rglob("*.json")}
    assert names >= {"request.json", "execution-instance-binding.json", "access-protection.json",
                     "candidate-graph.json", "report.json"}
    assert len([name for name in names if name.startswith("projection/")]) == 1
    with pytest.raises(AnalysisError, match="fresh output"):
        builder.build_concurrent_access_candidates("request.json", store, tmp_path / "cold")


def test_dependency_resolution_enforces_store_schema_producer_and_digest(tmp_path):
    value = concurrent_access_document(
        "ConcurrentAccessProjectionFacts", scope_id="scope", request_hash=A, status="complete",
        accesses=[], observed_not_demanded=[], counts={}, dependencies=[], diagnostics=[], frontier=[],
        semantic_digest=None)
    path = tmp_path / "projection.json"; path.write_text(json.dumps(value), encoding="utf-8")
    ref = {"kind": value["kind"], "id": "scope", "digest": identity(value), "path": path.name,
           "schema_version": 1, "producer": "concurrent-access-candidate-graph-v1"}
    assert builder._resolve_dependency(tmp_path, ref) == value
    for field, changed, message in (("schema_version", 2, "schema"),
                                    ("producer", "old", "producer"),
                                    ("digest", A, "digest")):
        broken = {**ref, field: changed}
        with pytest.raises(AnalysisError, match=message):
            builder._resolve_dependency(tmp_path, broken)
    with pytest.raises(AnalysisError, match="escapes"):
        builder._resolve_dependency(tmp_path, {**ref, "path": "../projection.json"})
    with pytest.raises(AnalysisError, match="missing"):
        builder._resolve_dependency(tmp_path, {**ref, "path": "absent.json"})


def test_reader_dispatch_required_selection_and_downgrade(monkeypatch, tmp_path):
    marker = {"marker": True}
    monkeypatch.setattr(builder, "read_concurrent_access_document", lambda path, kind: (kind, marker))
    groups = {
        "memory_order_analyzer.root_contracts": ("read_root_document", ("RootDrivenAnalysisPlan", "ExecutionRootIndex")),
        "memory_order_analyzer.thread_entry_contracts": ("read_thread_entry_document", ("ThreadEntryRootOverlay", "ThreadEntrySiteIndex")),
        "memory_order_analyzer.effect_contracts": ("read_effect_document", ("EffectSummary",)),
        "memory_order_analyzer.thread_contracts": ("read_thread_document", ("ThreadContextGraph",)),
        "memory_order_analyzer.cpp_thread_contracts": ("read_cpp_thread_document", ("CppThreadLifecycleGraph",)),
        "memory_order_analyzer.cpp_raii_contracts": ("read_cpp_raii_document", ("CppRaiiSynchronizationGraph",)),
        "memory_order_analyzer.provenance_contracts": ("read_provenance_document", ("BoundedObjectProvenanceGraph",)),
    }
    for module_name, (reader_name, kinds) in groups.items():
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, reader_name, lambda path, kind: (kind, marker))
        for kind in kinds:
            assert builder._read_kind(tmp_path / "x", kind) == (kind, marker)
    assert builder._read_kind(tmp_path / "x", "ConcurrentAccessProjectionFacts")[0] == \
        "ConcurrentAccessProjectionFacts"
    with pytest.raises(AnalysisError, match="Unsupported"):
        builder._read_kind(tmp_path / "x", "Unknown")
    resolved = {("EffectSummary", "one"): marker}
    assert builder._only(resolved, "EffectSummary", required=True) is marker
    with pytest.raises(AnalysisError, match="exactly one"):
        builder._only({}, "EffectSummary", required=True)
    partial = builder._downgrade(concurrent_access_document(
        "ConcurrentAccessProjectionFacts", scope_id="scope", request_hash=A, status="complete",
        accesses=[], observed_not_demanded=[], counts={}, dependencies=[], diagnostics=[], frontier=[],
        semantic_digest=None),
        builder.diagnostic("budget", "预算", "budget"))
    assert partial["status"] == "partial" and partial["frontier"][0]["code"] == "budget"


def test_orchestrator_time_output_and_partial_cache_paths(tmp_path, monkeypatch):
    values = artifacts(); req = request(values, request_seconds=1)
    monkeypatch.setattr(builder, "read_concurrent_access_document", lambda path, kind: req)
    monkeypatch.setattr(builder, "_resolve_dependency", lambda store, ref: values[ref["id"]])
    times = iter((0, 2))
    report = builder.build_concurrent_access_candidates(
        "request.json", tmp_path / "store-time", tmp_path / "time", clock=lambda: next(times))
    assert report["status"] == "partial" and report["exit_code"] == 2
    assert any(item["code"] == "request-time-budget-exhausted" for item in report["frontier"])

    open_request = deepcopy(request(values)); open_request["closed_scope"] = False
    open_request["semantic_digest"] = semantic_digest(open_request)
    monkeypatch.setattr(builder, "read_concurrent_access_document", lambda path, kind: open_request)
    report = builder.build_concurrent_access_candidates(
        "request.json", tmp_path / "store-open", tmp_path / "open")
    assert report["status"] == "partial"
    cache_files = list((tmp_path / "store-open/derived/concurrent-access-candidate-graph-v1").rglob("*.json"))
    assert not cache_files

    tiny = request(values, request_output_bytes=1024)
    monkeypatch.setattr(builder, "read_concurrent_access_document", lambda path, kind: tiny)
    report = builder.build_concurrent_access_candidates(
        "request.json", tmp_path / "store-small", tmp_path / "small")
    assert report["status"] == "partial" and any(
        item["code"] == "request-output-budget-exhausted" for item in report["frontier"])


def test_cli_dispatch_and_failed_exit_codes(tmp_path, monkeypatch, capsys):
    report = {"status": "partial", "exit_code": 2, "safety": "not_evaluated", "findings": None}
    monkeypatch.setattr(cli, "build_concurrent_access_candidates", lambda *args: report)
    argv = ["build-concurrent-access-candidates", "--request", "request.json",
            "--artifact-store", str(tmp_path), "--output", str(tmp_path / "output")]
    assert cli.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["safety"] == "not_evaluated"
    assert cli.main(["build-concurrent-access-candidates"]) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["status"] == "failed" and failed["diagnostics"][0]["detail_en"]
