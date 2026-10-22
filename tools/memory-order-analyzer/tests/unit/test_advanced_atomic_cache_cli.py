import json
from pathlib import Path

import pytest

from memory_order_analyzer.advanced_atomic_analysis import build_communication_graph, build_overlay
from memory_order_analyzer.advanced_atomic_cache import AdvancedAtomicCache, analysis_key
from memory_order_analyzer.advanced_atomic_contracts import (
    MODEL_ID,
    advanced_atomic_document,
    diagnostic,
    expected_advanced_atomic_protocol,
)
from memory_order_analyzer.cli import main
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash
from memory_order_analyzer.model_fence_rmw_publication import model_fence_rmw_publication


def budgets():
    return dict(expected_advanced_atomic_protocol()["budgets"])


def local(status="complete", frontier=None):
    return advanced_atomic_document(
        "AdvancedAtomicLocalFacts", scope_id="scope", language_standard="c11", dependencies=[],
        events=[], local_order=[], status=status, frontier=frontier or [], diagnostics=[])


def test_cache_reuses_complete_and_rejects_partial_or_corrupt(tmp_path):
    cache = AdvancedAtomicCache(tmp_path / "cache")
    graph = build_communication_graph(local(), scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=True)
    overlay = build_overlay(graph)
    key = analysis_key({"standard": "c11", "budget": budgets()})
    cache.publish("graph", key, graph)
    assert cache.load("graph", key, "BoundedAtomicCommunicationGraph") == graph
    partial_local = local("partial", [diagnostic("open", "未闭合", "Open")])
    partial = build_communication_graph(partial_local, scope_id="scope", language_standard="c11",
                                        budgets=budgets(), closed_scope=True)
    with pytest.raises(AnalysisError, match="complete"):
        cache.publish("graph", "partial", partial)
    path = cache._path("overlay", key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid"):
        cache.load("overlay", key, "AdvancedPublicationProtocolOverlay")
    assert overlay["status"] == "complete"


def test_cache_rejects_escape_partial_entries_collisions_and_publish_races(tmp_path, monkeypatch):
    cache = AdvancedAtomicCache(tmp_path / "cache")
    graph = build_communication_graph(local(), scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=True)
    key = analysis_key({"case": "collision"})
    assert cache.load("graph", "missing", "BoundedAtomicCommunicationGraph") is None
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../escape", key)

    path = cache.publish("graph", key, graph)
    assert cache.publish("graph", key, graph) == path
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("graph", key, graph)

    partial = build_communication_graph(
        local("partial", [diagnostic("open", "未闭合", "Open")]), scope_id="scope",
        language_standard="c11", budgets=budgets(), closed_scope=True)
    partial_path = cache._path("graph", "partial-entry")
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path.write_text(canonical(partial), encoding="utf-8")
    with pytest.raises(AnalysisError, match="partial/failed"):
        cache.load("graph", "partial-entry", "BoundedAtomicCommunicationGraph")

    import memory_order_analyzer.advanced_atomic_cache as cache_module
    race_key = analysis_key({"case": "race"})
    race_path = cache._path("graph", race_key)

    def lose_race(_temporary, target):
        Path(target).write_text("conflict", encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr(cache_module.os, "link", lose_race)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("graph", race_key, graph)
    assert race_path.read_text(encoding="utf-8") == "conflict"


def _module():
    return {"schema_version": 2, "kind": "ModuleFacts", "artifact_key": "a" * 64,
            "module_hash": "b" * 64, "target": "x86_64", "layout": "e-p:64:64",
            "producer": [], "functions": [], "globals": [], "events": [], "calls": [],
            "capabilities": {}, "source_mapping": "unavailable", "values": [], "protocol": {},
            "extraction": {"status": "complete", "roots": 0, "nodes": 0,
                           "references": 0, "unknown": 0, "diagnostics": []}}


def _write_request(tmp_path, module_path, *, closed=True):
    reference = {"path": str(module_path), "sha256": file_hash(module_path)}
    request = advanced_atomic_document(
        "FenceRmwPublicationRequest", model_id=MODEL_ID, scope_id="scope",
        language_standard="c11", closed_scope=closed, module_facts=[reference], source_facts=[],
        thread_graph=None, provenance_graph=None, publication_graph=None, root_plan=None,
        demand_graph=None, candidate_graph=None, budgets=budgets())
    path = tmp_path / "request.json"
    path.write_text(canonical(request), encoding="utf-8")
    return path


def _write_ast_only_request(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(canonical({
        "physical_tu_id": "c" * 64,
        "nodes": [{"id": "atomic", "kind": "atomic-expression", "canonical_type": "_Atomic(int)",
                   "attributes": ["atomic-profile:c"]}],
        "relations": [{"id": "r", "kind": "atomic-c-rmw", "from": "atomic", "to": None}],
    }), encoding="utf-8")
    request = advanced_atomic_document(
        "FenceRmwPublicationRequest", model_id=MODEL_ID, scope_id="scope",
        language_standard="c11", closed_scope=True, module_facts=[],
        source_facts=[{"path": str(source_path), "sha256": file_hash(source_path)}],
        thread_graph=None, provenance_graph=None, publication_graph=None, root_plan=None,
        demand_graph=None, candidate_graph=None, budgets=budgets())
    path = tmp_path / "ast-request.json"
    path.write_text(canonical(request), encoding="utf-8")
    return path


def test_offline_driver_writes_sidecars_and_warm_cache(tmp_path):
    module_path = tmp_path / "module.json"
    module_path.write_text(canonical(_module()), encoding="utf-8")
    request = _write_request(tmp_path, module_path)
    artifact_store = tmp_path / "artifacts"
    cold = model_fence_rmw_publication(request, artifact_store, tmp_path / "cold")
    warm = model_fence_rmw_publication(request, artifact_store, tmp_path / "warm")
    assert cold["exit_code"] == warm["exit_code"] == 0
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert warm["cache"]["hits"] == 2
    for name in ("atomic-source-construct-facts.json", "advanced-atomic-local-facts.json",
                 "bounded-atomic-communication-graph.json", "advanced-publication-protocol-overlay.json",
                 "fence-rmw-publication-report.json"):
        assert (tmp_path / "cold" / name).is_file()
    with pytest.raises(AnalysisError, match="fresh"):
        model_fence_rmw_publication(request, artifact_store, tmp_path / "cold")


def test_ast_only_driver_is_partial_and_excluded_profiles_fail(tmp_path):
    ast_request = _write_ast_only_request(tmp_path)
    report = model_fence_rmw_publication(ast_request, tmp_path / "ast-store", tmp_path / "ast-output")
    assert report["exit_code"] == 2 and report["status"] == "partial"
    assert any(item["code"] == "ast-only-runtime-binding-unavailable" for item in report["frontier"])

    module_path = tmp_path / "windows-module.json"
    value = _module()
    value["target"] = "x86_64-pc-windows-msvc"
    module_path.write_text(canonical(value), encoding="utf-8")
    request = _write_request(tmp_path, module_path)
    with pytest.raises(AnalysisError, match="excludes Windows"):
        model_fence_rmw_publication(request, tmp_path / "profile-store", tmp_path / "profile-output")


def test_cli_success_partial_failure_and_invalid_arguments(tmp_path):
    module_path = tmp_path / "module.json"
    module_path.write_text(canonical(_module()), encoding="utf-8")
    request = _write_request(tmp_path, module_path)
    stdout, stderr = __import__("io").StringIO(), __import__("io").StringIO()
    code = main(["model-fence-rmw-publication", "--request", str(request),
                 "--artifact-store", str(tmp_path / "store"), "--output", str(tmp_path / "output")],
                stdout=stdout, stderr=stderr)
    assert code == 0
    assert json.loads(stdout.getvalue())["kind"] == "FenceRmwPublicationReport"
    partial_request = _write_request(tmp_path, module_path, closed=False)
    code = main(["model-fence-rmw-publication", "--request", str(partial_request),
                 "--artifact-store", str(tmp_path / "store2"), "--output", str(tmp_path / "partial")],
                stdout=__import__("io").StringIO(), stderr=__import__("io").StringIO())
    assert code == 2
    out = __import__("io").StringIO()
    code = main(["model-fence-rmw-publication"], stdout=out, stderr=__import__("io").StringIO())
    assert code == 1
    assert json.loads(out.getvalue())["verdict"] == "failed"
    bad = json.loads(request.read_text(encoding="utf-8"))
    bad["module_facts"][0]["sha256"] = "0" * 64
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(canonical(bad), encoding="utf-8")
    out = __import__("io").StringIO()
    code = main(["model-fence-rmw-publication", "--request", str(bad_path),
                 "--artifact-store", str(tmp_path / "store3"), "--output", str(tmp_path / "bad-output")],
                stdout=out, stderr=__import__("io").StringIO())
    assert code == 1
    assert json.loads(out.getvalue())["exit_code"] == 1
