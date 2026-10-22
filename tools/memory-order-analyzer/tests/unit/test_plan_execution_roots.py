from copy import deepcopy
from io import StringIO
import json

import pytest

from memory_order_analyzer.cli import main
from memory_order_analyzer.contracts import AnalysisError, canonical, document, identity
from memory_order_analyzer.plan_execution_roots import (
    _read_evidence, _resolve_input, load_root_evidence, plan_execution_roots,
)
from memory_order_analyzer.protocol import expected_protocol
from memory_order_analyzer.root_contracts import expected_root_protocol, root_document, semantic_digest
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document


A, B, C = "a" * 64, "b" * 64, "c" * 64


def module():
    functions = [{"id": name, "name": name, "linkage": "external" if name == "main" else "internal",
                  "declaration": False, "comdat": False, "parameters": [], "return_type": "i32",
                  "vararg": False, "blocks": []} for name in ("main", "worker")]
    return document(
        "ModuleFacts", artifact_key=A, module_hash=B, target="x86_64-pc-linux-gnu",
        layout="e-p:64:64", producer=[], functions=functions, globals=[], events=[], calls=[],
        capabilities={}, source_mapping="unavailable", values=[], protocol=expected_protocol(),
        extraction={"status": "complete", "roots": 2, "nodes": 0, "references": 0,
                    "unknown": 0, "diagnostics": []})


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
    return thread_document(
        "ThreadLocalFacts", origin=origin, budgets=budgets, calls=[call], provenance=[],
        analysis_evidence=[], diagnostics=[], frontier=[], status="complete")


def prepare(tmp_path):
    store = tmp_path / "artifacts"; (store / "facts").mkdir(parents=True); (store / "thread-local").mkdir()
    mod, local = module(), thread_local()
    (store / f"facts/{A}.json").write_text(canonical(mod), encoding="utf-8")
    (store / f"thread-local/{A}.json").write_text(canonical(local), encoding="utf-8")
    evidence = [
        {"kind": "ModuleFacts", "id": A, "digest": identity(mod), "path": f"facts/{A}.json"},
        {"kind": "ThreadLocalFacts", "id": A, "digest": identity(local), "path": f"thread-local/{A}.json"},
    ]
    req = root_document(
        "ExecutionRootDiscoveryRequest", scope_id="scope", closed_scope=True, discover_main=True,
        members=[{"physical_tu_id": "tu", "profile_id": A, "language": "c", "standard": "c11",
                  "evidence": evidence}], global_evidence=[], explicit_roots=[],
        budgets=deepcopy(expected_root_protocol()["budgets"]), semantic_digest=None)
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(req), encoding="utf-8")
    return store, request_path, req


def test_end_to_end_output_layout_cache_and_determinism(tmp_path):
    store, request_path, _ = prepare(tmp_path)
    first = plan_execution_roots(request_path, store, tmp_path / "out-1")
    second = plan_execution_roots(request_path, store, tmp_path / "out-2")
    assert first["status"] == "complete" and first["exit_code"] == 0
    assert first["classification_counts"]["ir-exact"] == 1
    assert second["cache"]["hits"] == 3 and second["cache"]["misses"] == 0
    for relative in ("request.json", "thread-creation-sites/index.json", "execution-roots/index.json", "report.json"):
        assert (tmp_path / "out-1" / relative).is_file()
    assert list((tmp_path / "out-1" / "plans").glob("*.json"))
    assert len(list((tmp_path / "out-1" / "effects/requests").glob("*.json"))) == 2
    assert len(list((tmp_path / "out-1" / "threads/requests").glob("*.json"))) == 2
    a = json.loads((tmp_path / "out-1/thread-creation-sites/index.json").read_text())
    b = json.loads((tmp_path / "out-2/thread-creation-sites/index.json").read_text())
    assert a == b


def test_evidence_loader_rejects_kind_id_digest_path_and_existing_output(tmp_path):
    store, request_path, req = prepare(tmp_path)
    with pytest.raises(AnalysisError, match="Unsupported"):
        _read_evidence(request_path, "Unknown")
    with pytest.raises(AnalysisError, match="Unsupported"):
        _resolve_input(store, {"kind": "Unknown", "id": "x", "digest": A, "path": f"facts/{A}.json"})
    bad = deepcopy(req["members"][0]["evidence"][0]); bad["id"] = B
    with pytest.raises(AnalysisError, match="id disagrees"):
        _resolve_input(store, bad)
    bad = deepcopy(req["members"][0]["evidence"][0]); bad["digest"] = C
    with pytest.raises(AnalysisError, match="digest changed"):
        _resolve_input(store, bad)
    bad = deepcopy(req["members"][0]["evidence"][0]); bad["path"] = "missing.json"
    with pytest.raises(AnalysisError, match="missing or escapes"):
        _resolve_input(store, bad)
    loaded = load_root_evidence(req, store)
    assert set(loaded["by_member"]["tu"]) == {"ModuleFacts", "ThreadLocalFacts"}
    global_request = deepcopy(req)
    global_request["global_evidence"] = [global_request["members"][0]["evidence"].pop()]
    global_request["semantic_digest"] = semantic_digest(global_request)
    loaded = load_root_evidence(global_request, store)
    assert A in loaded["ThreadLocalFacts"]
    (tmp_path / "exists").mkdir()
    with pytest.raises(AnalysisError, match="fresh output"):
        plan_execution_roots(request_path, store, tmp_path / "exists")


@pytest.mark.parametrize("kind", [
    "SourceSemanticFacts", "ProgramEntityIndex", "SourceIRBinding", "ThreadLocalFacts",
    "ExecutionOrderFacts", "EffectSummary", "ThreadContextGraph", "CppThreadLocalFacts",
    "CppThreadLifecycleGraph",
])
def test_evidence_dispatch_reaches_each_existing_validator(kind, tmp_path):
    path = tmp_path / "wrong-kind.json"; path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError):
        _read_evidence(path, kind)


def test_request_time_and_output_budgets_fail_closed(tmp_path):
    store, request_path, req = prepare(tmp_path)
    times = iter([0.0, 4000.0])
    with pytest.raises(AnalysisError, match="wall-clock"):
        plan_execution_roots(request_path, store, tmp_path / "timeout", clock=times.__next__)
    small = deepcopy(req); small["budgets"]["request_output_bytes"] = 1024
    small["semantic_digest"] = semantic_digest(small)
    path = tmp_path / "small.json"; path.write_text(canonical(small), encoding="utf-8")
    with pytest.raises(AnalysisError, match="output exceeds"):
        plan_execution_roots(path, store, tmp_path / "small-out")


def test_cli_success_failure_and_argument_failure_are_machine_readable(tmp_path):
    store, request_path, _ = prepare(tmp_path)
    stdout, stderr = StringIO(), StringIO()
    code = main(["plan-execution-roots", "--request", str(request_path),
                 "--artifact-store", str(store), "--output", str(tmp_path / "cli")],
                stdout=stdout, stderr=stderr)
    assert code == 0 and json.loads(stdout.getvalue())["kind"] == "RootDrivenAnalysisReport"
    stdout, stderr = StringIO(), StringIO()
    code = main(["plan-execution-roots"], stdout=stdout, stderr=stderr)
    assert code == 1 and json.loads(stdout.getvalue())["status"] == "failed"
    broken = json.loads(request_path.read_text()); broken["semantic_digest"] = "0" * 64
    broken_path = tmp_path / "broken.json"; broken_path.write_text(json.dumps(broken))
    stdout, stderr = StringIO(), StringIO()
    code = main(["plan-execution-roots", "--request", str(broken_path),
                 "--artifact-store", str(store), "--output", str(tmp_path / "broken-out")],
                stdout=stdout, stderr=stderr)
    assert code == 1 and json.loads(stdout.getvalue())["exit_code"] == 1 and stderr.getvalue()
