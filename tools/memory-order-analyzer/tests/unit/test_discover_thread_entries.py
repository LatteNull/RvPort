from copy import deepcopy
from io import StringIO
import json

import pytest

from memory_order_analyzer.cli import main
from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.discover_thread_entries import (
    _evidence_id, _read_evidence, _resolve_input, discover_thread_entries, load_evidence,
)
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document
from memory_order_analyzer.thread_entry_cache import ThreadEntryCache, cache_key
from memory_order_analyzer.thread_entry_contracts import expected_thread_entry_protocol, semantic_digest, thread_entry_document
from memory_order_analyzer.thread_entry_profiles import c_api_profile


A, B, C = "a" * 64, "b" * 64, "c" * 64


def thread_local():
    budgets = deepcopy(expected_thread_protocol()["budgets"])
    origin = {"artifact_key": A, "module_hash": B, "facts_hash": C,
              "profile": "source-preserving", "extractor_version": "0.2.0", "llvm_version": "21.1.8"}
    ref = lambda ident, function="main": {"artifact_key": A, "function_id": function, "id": ident}
    call = {
        "source": ref("call"), "function": ref("main", None), "symbol": "pthread_create",
        "direct": True, "function_type": "i32 (ptr, ptr, ptr, ptr)", "calling_convention": 0,
        "arguments": [ref("tid"), None, ref("worker", None), None], "result": ref("call"),
        "normal_successor": ref("next"), "unwind_successor": None, "noreturn": False,
        "success_test": ref("ok"), "callback_metadata": [[2, 3, 0]],
        "callback_targets": [ref("worker", None)], "handle_source": ref("tid"),
        "mutex_source": None, "mutex_initializer": None, "status": "candidate", "reason": None,
    }
    return thread_document("ThreadLocalFacts", origin=origin, budgets=budgets, calls=[call], provenance=[],
                           analysis_evidence=[], diagnostics=[], frontier=[], status="complete")


def prepare(tmp_path):
    store = tmp_path / "artifacts"; (store / "thread-local").mkdir(parents=True)
    facts = thread_local()
    (store / f"thread-local/{A}.json").write_text(canonical(facts), encoding="utf-8")
    evidence = [{"kind": "ThreadLocalFacts", "id": A, "digest": identity(facts),
                 "path": f"thread-local/{A}.json"}]
    request = thread_entry_document(
        "ThreadEntryDiscoveryRequest", scope_id="scope", closed_scope=True,
        members=[{"physical_tu_id": "tu", "profile_id": A, "language": "c", "standard": "c11",
                  "evidence": evidence}], global_evidence=[],
        model_profiles=[c_api_profile("pthread", "x86_64-pc-linux-gnu", "e-p:64:64")],
        framework_descriptors=[], budgets=deepcopy(expected_thread_entry_protocol()["budgets"]),
        semantic_digest=None)
    path = tmp_path / "request.json"; path.write_text(canonical(request), encoding="utf-8")
    return store, path, request


def test_end_to_end_layout_cache_determinism_and_cli(tmp_path):
    store, path, _ = prepare(tmp_path)
    first = discover_thread_entries(path, store, tmp_path / "out-1",
                                    source_worker=tmp_path / "crashed-source-worker",
                                    ir_worker=tmp_path / "timed-out-ir-worker")
    second = discover_thread_entries(path, store, tmp_path / "out-2")
    assert first["status"] == "complete" and first["exit_code"] == 0
    assert first["evidence_counts"]["ir-exact"] == 1
    assert second["cache"] == {"hits": 3, "misses": 0}
    assert first["semantic_digest"] == second["semantic_digest"]
    for relative in ("request.json", "local/tu.json", "sites/index.json", "roots/overlay.json", "report.json"):
        assert (tmp_path / "out-1" / relative).is_file()
    stdout, stderr = StringIO(), StringIO()
    code = main(["discover-thread-entries", "--request", str(path), "--artifact-store", str(store),
                 "--output", str(tmp_path / "cli")], stdout=stdout, stderr=stderr)
    assert code == 0 and json.loads(stdout.getvalue())["kind"] == "ThreadEntryDiscoveryReport"


def test_loader_and_cli_fail_closed(tmp_path):
    store, path, request = prepare(tmp_path)
    with pytest.raises(AnalysisError, match="Unsupported"):
        _read_evidence(path, "Unknown")
    bad = deepcopy(request["members"][0]["evidence"][0]); bad["digest"] = B
    with pytest.raises(AnalysisError, match="digest changed"):
        _resolve_input(store, bad)
    bad = deepcopy(request["members"][0]["evidence"][0]); bad["id"] = B
    with pytest.raises(AnalysisError, match="id disagrees"):
        _resolve_input(store, bad)
    bad = deepcopy(request["members"][0]["evidence"][0]); bad["path"] = "../bad.json"
    with pytest.raises(AnalysisError, match="missing or escapes"):
        _resolve_input(store, bad)
    assert load_evidence(request, store)["by_member"]["tu"]["ThreadLocalFacts"]["kind"] == "ThreadLocalFacts"
    (tmp_path / "exists").mkdir()
    with pytest.raises(AnalysisError, match="fresh output"):
        discover_thread_entries(path, store, tmp_path / "exists")
    stdout, stderr = StringIO(), StringIO()
    code = main(["discover-thread-entries"], stdout=stdout, stderr=stderr)
    assert code == 1 and json.loads(stdout.getvalue())["status"] == "failed"
    broken = json.loads(path.read_text()); broken["semantic_digest"] = "0" * 64
    broken_path = tmp_path / "broken.json"; broken_path.write_text(json.dumps(broken))
    stdout, stderr = StringIO(), StringIO()
    code = main(["discover-thread-entries", "--request", str(broken_path), "--artifact-store", str(store),
                 "--output", str(tmp_path / "broken-out")], stdout=stdout, stderr=stderr)
    assert code == 1 and json.loads(stdout.getvalue())["exit_code"] == 1 and stderr.getvalue()


def test_time_output_budget_and_cache_rejections(tmp_path):
    store, path, request = prepare(tmp_path)
    times = iter([0.0, 4000.0])
    timeout = discover_thread_entries(path, store, tmp_path / "timeout", clock=times.__next__)
    assert timeout["status"] == "partial" and timeout["exit_code"] == 2
    assert any(item["code"] == "request-time-budget-exhausted" for item in timeout["frontier"])
    small = deepcopy(request); small["budgets"]["request_output_bytes"] = 1024
    small["semantic_digest"] = semantic_digest(small)
    small_path = tmp_path / "small.json"; small_path.write_text(canonical(small))
    with pytest.raises(AnalysisError, match="output exceeds"):
        discover_thread_entries(small_path, store, tmp_path / "small-out")
    cache = ThreadEntryCache(tmp_path / "cache")
    with pytest.raises(AnalysisError, match="complete"):
        cache.publish("x", A, {"status": "partial"})
    cache_path = cache._path("x", A); cache_path.parent.mkdir(parents=True); cache_path.write_text("broken")
    with pytest.raises(AnalysisError, match="Invalid"):
        cache.load("x", A, "ThreadEntrySiteIndex")
    assert cache_key("layer", {"x": 1}, [B, A]) == cache_key("layer", {"x": 1}, [A, B])
    assert cache_key("layer", {"x": 1}, [A, B]) != cache_key("layer", {"x": 1}, [A, C])


def test_evidence_reader_dispatch_and_identity_fields(tmp_path, monkeypatch):
    path = tmp_path / "evidence.json"; path.write_text("{}")
    monkeypatch.setattr("memory_order_analyzer.discover_thread_entries.read_document",
                        lambda value, kind: {"reader": "module", "kind": kind})
    monkeypatch.setattr("memory_order_analyzer.source_contracts.read_source_document",
                        lambda value, kind: {"reader": "source", "kind": kind})
    monkeypatch.setattr("memory_order_analyzer.thread_contracts.read_thread_document",
                        lambda value, kind: {"reader": "thread", "kind": kind})
    monkeypatch.setattr("memory_order_analyzer.cpp_thread_contracts.read_cpp_thread_document",
                        lambda value, kind: {"reader": "cpp", "kind": kind})
    monkeypatch.setattr("memory_order_analyzer.root_contracts.read_root_document",
                        lambda value, kind: {"reader": "root", "kind": kind})
    expected = {
        "ModuleFacts": "module", "SourceSemanticFacts": "source", "SourceIRBinding": "source",
        "ThreadLocalFacts": "thread", "CppThreadLocalFacts": "cpp",
        "ExecutionRootIndex": "root", "RootDrivenAnalysisPlan": "root",
    }
    for kind, reader in expected.items():
        assert _read_evidence(path, kind)["reader"] == reader
    assert _evidence_id({"artifact_key": A}, "ModuleFacts") == A
    assert _evidence_id({"physical_tu_id": A}, "SourceSemanticFacts") == A
    assert _evidence_id({"scope_id": A}, "SourceIRBinding") == A
    assert _evidence_id({"origin": {"artifact_key": A}}, "ThreadLocalFacts") == A
    assert _evidence_id({"physical_tu_id": A}, "CppThreadLocalFacts") == A
    assert _evidence_id({"scope_id": A}, "ExecutionRootIndex") == A
    assert _evidence_id({"scope_id": A}, "RootDrivenAnalysisPlan") == A
