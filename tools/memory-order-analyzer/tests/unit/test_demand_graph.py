from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.demand_adapters import (
    compare_semantics, concurrent_access_view, effect_view, eager_function_view,
    lazy_function_view, normalize_semantics, thread_view,
)
from memory_order_analyzer.demand_contracts import expected_demand_protocol
from memory_order_analyzer.demand_graph import (
    expand_demands, function_name, graph_counts, node_key, normalized_nodes, seed_demands,
)
from memory_order_analyzer.demand_scheduler import (
    execute_batches, plan_batches, plan_index_batches, worker_job,
)


A, B, C = "a" * 64, "b" * 64, "c" * 64


def member(artifact=A, tu="tu", mode="ast+ir"):
    return {"physical_tu_id": tu, "artifact_key": artifact,
            "bc_digest": B if mode in {"ast+ir", "ir-only"} else None,
            "profile_id": "clang-c11", "compiler": "clang", "language": "c", "standard": "c11",
            "target": "x86_64-pc-linux-gnu", "data_layout": "e", "abi": "itanium",
            "evidence_mode": mode}


def request(members=None, closed=True, **budget_updates):
    budgets = deepcopy(expected_demand_protocol()["budgets"]); budgets.update(budget_updates)
    return {"layers": ["effect", "semantic", "thread"], "members": members or [member()],
            "closed_scope": closed, "budgets": budgets}


def plan():
    entry = {"artifact_key": A, "function_id": f"{A}:symbol:main"}
    return {"contexts": [{"id": "ctx", "root_ids": ["root"]}],
            "demands": [{"id": "d", "function": entry, "context": "ctx",
                         "physical_tu_id": "tu", "consumers": ["P2", "P3"]}]}


def overlay(entry=None):
    entry = entry or {"artifact_key": A, "function_id": f"{A}:symbol:main"}
    return {"roots": [{"id": "r11", "context_id": "ctx", "entry": entry}],
            "demands": [{"id": "od", "root_id": "r11", "entry": entry,
                         "physical_tu_id": "tu", "kind": "reachable-entry"}]}


def shard(node, layer="semantic", *, calls=None, thread_calls=None, status="completed"):
    return {"kind": {"semantic": "FunctionSemanticFacts", "effect": "FunctionEffectFacts",
                     "thread": "FunctionThreadFacts"}[layer], "layer": layer, "status": status,
            "artifact_key": node["artifact_key"], "function_id": node["function_id"],
            "context_id": node["context_id"], "frontier": [],
            "facts": {"reference_closed": status == "completed", "calls": calls or [],
                      "thread_calls": thread_calls or [], "effects": [], "order_nodes": [], "order_edges": []}}


def test_seed_merges_r1_r11_open_scope_and_ast_only():
    nodes, edges, frontier = seed_demands(request(closed=False), plan(), overlay())
    assert len(nodes) == 1 and not edges
    node = next(iter(nodes.values()))
    assert node["root_ids"] == ["r11", "root"] and node["consumers"] == ["P2", "P3"]
    assert any(item["code"] == "open-scope-frontier" for item in frontier)
    ast = request([member(mode="ast-only")])
    nodes, _, frontier = seed_demands(ast, plan(), {"roots": [], "demands": []})
    assert next(iter(nodes.values()))["state"] == "partial"
    assert frontier[0]["code"] == "ast-only-no-runtime-facts"
    empty, _, frontier = seed_demands(request(), {"contexts": [], "demands": []}, {"roots": [], "demands": []})
    assert not empty and frontier[0]["code"] == "zero-demand-roots"
    separate = overlay({"artifact_key": C, "function_id": f"{C}:symbol:worker"})
    separate["roots"][0]["context_id"] = "ctx2"
    nodes, _, _ = seed_demands(request([member(), member(C, "tu2")]), plan(), separate)
    assert len(nodes) == 2
    limited_nodes, _, limited_frontier = seed_demands(
        request([member(), member(C, "tu2")], roots=1, contexts=1), plan(), separate)
    assert all(node["state"] == "partial" for node in limited_nodes.values())
    assert {item["code"] for item in limited_frontier} >= {"root-budget-exhausted", "context-budget-exhausted"}
    with pytest.raises(AnalysisError, match="no symbol"):
        function_name("invalid")


def test_exact_direct_and_callback_expansion_never_all_defined():
    req = request([member(), member(C, "tu2")])
    nodes, edges, frontier = seed_demands(req, plan(), {"roots": [], "demands": []})
    parent = next(iter(nodes.values())); parent["state"] = "completed"
    indexes = {
        A: {"symbols": [
            {"id": f"{A}:symbol:main", "name": "main", "materializable": True, "declaration": False},
            {"id": f"{A}:symbol:missing", "name": "missing", "materializable": False, "declaration": True}]},
        C: {"symbols": [{"id": f"{C}:symbol:helper", "name": "helper", "materializable": True, "declaration": False}]},
    }
    calls = [{"id": "call", "target_name": "helper", "binding": "exact"},
             {"id": "indirect", "target_name": None, "binding": "indirect"},
             {"id": "runtime", "target_name": "pthread_create", "binding": "exact"}]
    thread_calls = [{"source": "create", "callbacks": [f"{C}:symbol:helper"]}]
    inserted = expand_demands(req, parent, [shard(parent, calls=calls),
        shard(parent, "thread", thread_calls=thread_calls)], indexes, nodes, edges, frontier)
    assert len(inserted) == 1 and len(nodes) == 2
    child = nodes[inserted[0]]
    assert child["artifact_key"] == C and child["function_name"] == "helper"
    assert any(item["code"] == "indirect-call-frontier" for item in frontier)
    parent["state"] = "completed"
    duplicate = expand_demands(req, parent, [shard(parent, calls=calls)], indexes, nodes, edges, frontier)
    assert duplicate == [] and len(nodes) == 2


def test_ambiguous_missing_recursion_and_demand_budgets_are_frontier():
    req = request([member(), member(C, "tu2")], demands=1, recursion_depth=1)
    nodes, edges, frontier = seed_demands(req, plan(), {"roots": [], "demands": []})
    parent = next(iter(nodes.values())); parent["state"] = "completed"
    indexes = {A: {"symbols": []}, C: {"symbols": [
        {"id": f"{C}:symbol:dup1", "name": "dup", "materializable": True, "declaration": False},
        {"id": f"{C}:symbol:dup2", "name": "dup", "materializable": True, "declaration": False}]}}
    calls = [{"id": "a", "target_name": "dup", "binding": "exact"},
             {"id": "b", "target_name": "absent", "binding": "exact"}]
    assert not expand_demands(req, parent, [shard(parent, calls=calls)], indexes, nodes, edges, frontier)
    assert {item["code"] for item in frontier} >= {"ambiguous-call-target", "missing-definition"}
    indexes[A]["symbols"] = [{"id": f"{A}:symbol:main", "name": "main", "materializable": True, "declaration": False}]
    recursive = [{"id": "r", "target_name": "main", "binding": "exact"}]
    expand_demands(req, parent, [shard(parent, calls=recursive)], indexes, nodes, edges, frontier)
    assert edges[-1]["recursive"]
    assert graph_counts(nodes)["completed"] == 1
    assert normalized_nodes(nodes)[0]["id"] == parent["id"]
    assert function_name(f"{A}:symbol:_Z6workerv") == "_Z6workerv"
    assert node_key(A, "f", "c", ["thread", "semantic"]) == node_key(A, "f", "c", ["semantic", "thread"])

    budget_req = request([member(), member(C, "tu2")], demands=1)
    budget_nodes, budget_edges, budget_frontier = seed_demands(budget_req, plan(), {"roots": [], "demands": []})
    budget_parent = next(iter(budget_nodes.values()))
    expand_demands(budget_req, budget_parent, [shard(budget_parent, calls=[
        {"id": "budget", "target_name": "helper", "binding": "exact"}])],
        {C: {"symbols": [{"id": f"{C}:symbol:helper", "name": "helper",
                           "materializable": True, "declaration": False}]}},
        budget_nodes, budget_edges, budget_frontier)
    assert any(item["code"] == "demand-budget-exhausted" for item in budget_frontier)

    depth_req = request([member(), member(C, "tu2")], recursion_depth=1)
    depth_nodes, depth_edges, depth_frontier = seed_demands(depth_req, plan(), {"roots": [], "demands": []})
    depth_parent = next(iter(depth_nodes.values())); depth_parent["depth"] = 1
    expand_demands(depth_req, depth_parent, [shard(depth_parent, calls=[
        {"id": "depth", "target_name": "helper", "binding": "exact"}])],
        {C: {"symbols": [{"id": f"{C}:symbol:helper", "name": "helper",
                           "materializable": True, "declaration": False}]}},
        depth_nodes, depth_edges, depth_frontier)
    assert any(item["code"] == "recursion-budget" for item in depth_frontier)


def test_adapters_preserve_partial_and_operational_normalization():
    node = next(iter(seed_demands(request(), plan(), {"roots": [], "demands": []})[0].values()))
    effect = shard(node, "effect"); effect["facts"]["effects"] = [
        {"source": "i", "kind": "write", "object": "g", "guard": None,
         "binding": "local-candidate", "atomic_order": "not_atomic"}]
    thread = shard(node, "thread"); thread["facts"].update(
        thread_calls=[{"source": "c", "api": "pthread_create"}],
        order_nodes=[{"id": "i"}], order_edges=[])
    assert effect_view([effect])["effects"][0]["kind"] == "write"
    assert thread_view([thread])["calls"][0]["api"] == "pthread_create"
    r2 = concurrent_access_view([effect, thread])
    assert len(r2["accesses"]) == 1 and r2["safety"] == "not_evaluated"
    partial = shard(node, "effect", status="partial")
    assert effect_view([partial])["status"] == "partial" and effect_view([partial])["frontier"]
    left = {"id": "x", "wall_seconds": 1, "items": [{"id": "b"}, {"id": "a"}]}
    right = {"id": "x", "wall_seconds": 9, "items": [{"id": "a"}, {"id": "b"}]}
    assert compare_semantics(left, right)["exact"]
    assert "wall_seconds" not in normalize_semantics(left)
    assert lazy_function_view([effect], node["function_id"], node["context_id"])["status"] == "partial"


def test_eager_lazy_function_projection_covers_identity_memory_calls_and_returns():
    fid = f"{A}:symbol:main"; block = f"{fid}:b0"
    eager = {"functions": [{"id": fid, "name": "main", "linkage": "external",
                            "blocks": [{"id": block, "successors": [], "terminator": {
                                "id": f"{block}:i2", "opcode": "ret"}}]}],
             "values": [{"id": f"{block}:i0"}],
             "events": [{"id": f"{block}:i0", "function": fid, "kind": "store", "ordering": "not_atomic"}],
             "calls": [{"id": f"{block}:i1", "function": fid, "target": "helper"}]}
    view = eager_function_view(eager, fid)
    assert view["instructions"] == [f"{block}:i0", f"{block}:i1", f"{block}:i2"]
    assert view["accesses"][0]["kind"] == "write" and view["calls"][0]["target_name"] == "helper"
    semantic = {"layer": "semantic", "status": "completed", "function_id": fid, "context_id": "ctx",
                "facts": {"function": {"id": fid, "name": "main", "linkage": "external"},
                          "blocks": [{"id": block, "successors": []}],
                          "instructions": [{"id": f"{block}:i0"}, {"id": f"{block}:i1"}, {"id": f"{block}:i2"}],
                          "accesses": [{"id": f"{block}:i0", "kind": "write", "atomic_order": "not_atomic"},
                                       {"id": f"{block}:i1", "kind": "call", "atomic_order": "not_atomic"}],
                          "calls": [{"id": f"{block}:i1", "target_name": "helper"}],
                          "returns": [{"source": f"{block}:i2"}]}}
    effect = {"layer": "effect", "status": "completed", "function_id": fid, "context_id": "ctx",
              "facts": {"effects": [{"source": f"{block}:i0", "kind": "write"}]}}
    thread = {"layer": "thread", "status": "completed", "function_id": fid, "context_id": "ctx",
              "facts": {"order_nodes": [{"id": f"{block}:i0"}, {"id": f"{block}:i1"}]}}
    lazy = lazy_function_view([semantic, effect, thread], fid, "ctx")
    consistency = lazy["view"].pop("layer_consistency")
    assert consistency == {"effect_accesses": True, "thread_order": True}
    assert compare_semantics(view, lazy["view"])["exact"]
    effect["status"] = "partial"
    assert lazy_function_view([semantic, effect, thread], fid, "ctx")["status"] == "partial"


def test_batch_planning_worker_transport_and_failure_isolation(tmp_path):
    req = request([member(), member(C, "tu2")], functions_per_batch=1, workers=2)
    nodes, _, _ = seed_demands(req, plan(), {"roots": [], "demands": []})
    first = next(iter(nodes.values()))
    second = {**deepcopy(first), "id": "second", "artifact_key": C,
              "function_id": f"{C}:symbol:worker", "function_name": "worker", "physical_tu_id": "tu2"}
    batches = plan_batches([second, first], req["members"], req["budgets"])
    assert [item["artifact_key"] for item in batches] == [A, C]
    indexes = plan_index_batches(req["members"], skip={A})
    assert len(indexes) == 1 and indexes[0]["artifact_key"] == C
    job = worker_job(batches[0], tmp_path / "a.bc", req["budgets"])
    assert job["demands"][0]["function_name"] == "main"

    def success(argv, cwd, **kwargs):
        request_value = json.loads(open(argv[-1], encoding="utf-8").read())
        raw_job = request_value["jobs"][0]
        result = {"id": raw_job["id"], "index": {}, "shards": [],
                  "metrics": {"module_parses": 1}, "error": None}
        return {"status": "completed", "code": None, "exit_code": 0,
                "cpu_seconds": 0.02, "peak_rss_bytes": 2048, "output_bytes": 512,
                "stdout": json.dumps({"protocol_version": 1, "results": [result], "error": None}),
                "stderr": "", "argv": argv}
    paths = {A: tmp_path / "a.bc", C: tmp_path / "c.bc"}
    results, attempts = execute_batches(batches, paths, "worker", tmp_path / "out", req["budgets"], runner=success)
    assert len(results) == len(attempts) == 2 and all(item["status"] == "completed" for item in attempts)
    assert results[0][1]["metrics"]["peak_rss_bytes"] == 2048
    assert results[0][1]["metrics"]["output_bytes"] == 512

    def invalid(*args, **kwargs):
        return {"status": "completed", "code": None, "exit_code": 0, "stdout": "{", "stderr": "", "argv": []}
    _, attempts = execute_batches(batches[:1], paths, "worker", tmp_path / "invalid", req["budgets"], runner=invalid)
    assert attempts[0]["code"] == "invalid-worker-output"
    def timeout(*args, **kwargs):
        return {"status": "timed_out", "code": "timed_out", "exit_code": -9,
                "stdout": "", "stderr": "timeout", "argv": []}
    _, attempts = execute_batches(batches[:1], paths, "worker", tmp_path / "timeout", req["budgets"], runner=timeout)
    assert attempts[0]["status"] == "timed_out"

    assert plan_batches([{**first, "artifact_key": "f" * 64}], req["members"], req["budgets"]) == []
    assert execute_batches([], paths, "worker", tmp_path / "empty", req["budgets"], runner=success) == ([], [])
    def wrong_id(argv, cwd, **kwargs):
        return {"status": "completed", "code": None, "exit_code": 0,
                "stdout": json.dumps({"protocol_version": 1, "results": [{"id": "wrong", "error": None}], "error": None}),
                "stderr": "", "argv": argv}
    _, attempts = execute_batches(batches[:1], paths, "worker", tmp_path / "wrong", req["budgets"], runner=wrong_id)
    assert attempts[0]["code"] == "invalid-worker-output"
    def job_error(argv, cwd, **kwargs):
        envelope = json.loads(open(argv[-1], encoding="utf-8").read())
        return {"status": "completed", "code": None, "exit_code": 0,
                "stdout": json.dumps({"protocol_version": 1, "results": [
                    {"id": envelope["jobs"][0]["id"], "error": {"code": "reader_failed", "detail": "bad"}}], "error": None}),
                "stderr": "", "argv": argv}
    _, attempts = execute_batches(batches[:1], paths, "worker", tmp_path / "job-error", req["budgets"], runner=job_error)
    assert attempts[0]["code"] == "reader_failed"
    def crash(*args, **kwargs):
        raise RuntimeError("boom")
    _, attempts = execute_batches(batches[:1], paths, "worker", tmp_path / "crash", req["budgets"], runner=crash)
    assert attempts[0]["code"] == "worker-crash"
