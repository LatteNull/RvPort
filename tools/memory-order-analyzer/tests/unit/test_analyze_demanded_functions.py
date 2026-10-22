from copy import deepcopy
import io
import json
from pathlib import Path

import pytest

from memory_order_analyzer import cli
from memory_order_analyzer.analyze_demanded_functions import (
    _deduplicate_frontier, _load_inputs, _resolve_evidence, _wrap_shard,
    analyze_demanded_functions, failed_report,
)
from memory_order_analyzer.contracts import AnalysisError, canonical, document, file_hash, identity
from memory_order_analyzer.demand_contracts import demand_document, expected_demand_protocol
from memory_order_analyzer.root_contracts import root_document
from memory_order_analyzer.thread_entry_contracts import thread_entry_document


A, X, Y = "a" * 64, "1" * 64, "2" * 64


def upstream(scope="scope"):
    site_ref = {"kind": "ThreadCreationSiteIndex", "id": scope, "digest": X}
    roots_ref = {"kind": "ExecutionRootIndex", "id": scope, "digest": Y}
    entry = {"artifact_key": A, "function_id": f"{A}:symbol:main"}
    plan = root_document(
        "RootDrivenAnalysisPlan", scope_id=scope, request_hash=X, status="complete",
        thread_creation_sites=site_ref, execution_roots=roots_ref,
        reachable_functions=[{"id": "reach", "root_id": "root", "entry": entry, "distance": 0,
                              "status": "complete", "reason": "root"}], call_edges=[],
        contexts=[{"id": "ctx", "entry": entry, "arguments": [], "root_ids": ["root"]}],
        demands=[{"id": "demand", "function": entry, "context": "ctx", "physical_tu_id": "tu",
                  "consumers": ["P2", "P3"]}], p2_requests=[], p3_requests=[], a3_overlays=[],
        reconciliation={}, completeness={"root": {}, "reachable": {}, "candidate_relevant": {}},
        counts={"roots": 1, "reachable_functions": 1, "call_edges": 0, "contexts": 1,
                "demands": 1, "candidate_relevant_sites": 0},
        dependencies=sorted([site_ref, roots_ref], key=lambda item: (item["kind"], item["id"])),
        diagnostics=[], frontier=[], semantic_digest=None)
    thread_site = {"kind": "ThreadEntrySiteIndex", "id": scope, "digest": X}
    overlay = thread_entry_document(
        "ThreadEntryRootOverlay", scope_id=scope, request_hash=X, status="complete",
        site_index=thread_site, base_execution_roots=None, base_plan=None,
        roots=[], contexts=[], demands=[], reconciliation={"base_roots": 0, "overlay_roots": 0,
                                                           "adopted_from_base": []},
        completeness={"sites": "complete", "roots": "complete", "candidate_frontier": 0},
        counts={"roots": 0, "contexts": 0, "demands": 0, "adopted_from_base": 0},
        dependencies=[thread_site], diagnostics=[], frontier=[], semantic_digest=None)
    return plan, overlay


def make_store(tmp_path):
    store = tmp_path / "store"; (store / "artifacts").mkdir(parents=True)
    bc = store / "artifacts" / f"{A}.bc"; bc.write_bytes(b"BC\xc0\xdeunit")
    digest = file_hash(bc)
    artifact = document("BCArtifact", artifact_key=A, context_id=X, path=str(bc), sha256=digest,
                        profile="source-preserving", provenance="verified", inputs={},
                        toolchain={}, lineage=[])
    (store / "artifacts" / f"{A}.json").write_text(canonical(artifact) + "\n", encoding="utf-8")
    plan, overlay = upstream()
    (store / "r1").mkdir(); (store / "r11").mkdir()
    (store / "r1/plan.json").write_text(canonical(plan) + "\n", encoding="utf-8")
    (store / "r11/overlay.json").write_text(canonical(overlay) + "\n", encoding="utf-8")
    request = demand_document(
        "DemandDrivenAnalysisRequest", scope_id="scope", closed_scope=True,
        target="x86_64-pc-linux-gnu", data_layout="e-p:64:64-i128:128", abi="itanium",
        members=[{"physical_tu_id": "tu", "artifact_key": A, "bc_digest": digest,
                  "profile_id": "clang-c11", "compiler": "clang", "language": "c", "standard": "c11",
                  "target": "x86_64-pc-linux-gnu", "data_layout": "e-p:64:64-i128:128",
                  "abi": "itanium", "evidence_mode": "ast+ir"}],
        evidence=sorted([
            {"kind": plan["kind"], "id": "scope", "schema_version": 1,
             "producer": plan["policy_id"], "digest": identity(plan), "path": "r1/plan.json"},
            {"kind": overlay["kind"], "id": "scope", "schema_version": 1,
             "producer": overlay["policy_id"], "digest": identity(overlay), "path": "r11/overlay.json"},
        ], key=lambda item: (item["kind"], item["id"])),
        layers=["effect", "semantic", "thread"],
        budgets=deepcopy(expected_demand_protocol()["budgets"]), semantic_digest=None)
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request) + "\n", encoding="utf-8")
    return store, request_path


def raw_index(job):
    artifact = job["artifact_key"]
    symbols = [{"id": f"{artifact}:symbol:{name}", "name": name, "declaration": False,
                "materializable": True, "linkage": "external", "visibility": "default", "comdat": None}
               for name in ("helper", "main", "unreachable")]
    return {"artifact_key": artifact, "physical_tu_id": job["physical_tu_id"],
            "bc_digest": job["bc_digest"], "profile_id": job["profile_id"],
            "target": job["target"], "data_layout": job["data_layout"], "abi": job["abi"],
            "symbols": symbols, "source_bindings": [],
            "counts": {"indexed_symbols": 3, "indexed_functions": 3, "defined_functions": 3,
                       "materialized_functions": 0, "materialized_instructions": 0}}


def raw_shard(job, demand, layer):
    name = demand["function_name"]
    calls = [{"id": f"{demand['function_id']}:b0:i0", "function_id": demand["function_id"],
              "target": f"{A}:symbol:helper", "target_name": "helper", "binding": "exact",
              "arguments": [], "location": {"inline_chain": []}}] if name == "main" else []
    facts = {"reference_closed": True, "layer": layer,
             "function": {"id": demand["function_id"], "name": name, "type": "i32 ()", "linkage": "external"},
             "arguments": [], "blocks": [{"id": f"{demand['function_id']}:b0", "successors": []}],
             "instructions": [{"id": f"{demand['function_id']}:b0:i0", "block": f"{demand['function_id']}:b0",
                               "opcode": "ret", "type": "void", "location": {"inline_chain": []}}],
             "calls": calls, "accesses": []}
    if layer == "semantic": facts.update(returns=[], conditions=[])
    if layer == "effect": facts.update(effects=[], analysis_evidence=[],
                                        analysis={"dominator_tree": True, "basic_aa": True, "memory_ssa": True})
    if layer == "thread": facts.update(order_nodes=[], order_edges=[], thread_calls=[], analysis_evidence=[],
                                        analysis={"dominator_tree": True, "postdominator_tree": True, "loop_info": True})
    return {"function_id": demand["function_id"], "function_name": name,
            "context_id": demand["context_id"], "layer": layer, "status": "completed",
            "facts": facts, "counts": {"instructions": 1, "calls": len(calls), "accesses": 0}, "error": None}


def successful_runner(argv, cwd, **kwargs):
    envelope = json.loads(Path(argv[-1]).read_text(encoding="utf-8")); job = envelope["jobs"][0]
    shards = [raw_shard(job, demand, layer) for demand in job["demands"] for layer in demand["layers"]]
    result = {"id": job["id"], "index": raw_index(job), "shards": shards,
              "metrics": {"module_parses": 1, "materialized_functions": len(job["demands"]),
                          "materialized_instructions": len(job["demands"]), "analysis_queries": len(shards),
                          "wall_seconds": 0.01, "cpu_seconds": 0.01, "peak_rss_bytes": 1024,
                          "output_bytes": 100}, "error": None}
    return {"status": "completed", "code": None, "exit_code": 0,
            "stdout": json.dumps({"protocol_version": 1, "results": [result], "error": None}),
            "stderr": "", "argv": argv}


def test_end_to_end_cold_warm_demand_expansion_and_outputs(tmp_path):
    store, request = make_store(tmp_path)
    cold = analyze_demanded_functions(request, store, tmp_path / "cold", "worker", runner=successful_runner)
    assert cold["status"] == "complete" and cold["exit_code"] == 0
    assert cold["counts"]["indexed"] == 3 and cold["counts"]["demanded"] == 2
    assert cold["counts"]["materialized"] == 2 and cold["counts"]["cache_hit"] == 0
    graph = json.loads((tmp_path / "cold/demand-graph.json").read_text())
    assert {item["function_name"] for item in graph["nodes"]} == {"main", "helper"}
    assert not any(item["function_name"] == "unreachable" for item in graph["nodes"])
    assert (tmp_path / "cold/views/concurrent-access.json").is_file()
    warm = analyze_demanded_functions(request, store, tmp_path / "warm", "worker", runner=successful_runner)
    assert warm["counts"]["cache_hit"] == 6 and warm["counts"]["materialized"] == 0
    assert warm["semantic_digest"] == cold["semantic_digest"]


def test_worker_timeout_bad_evidence_output_and_failed_report(tmp_path):
    store, request = make_store(tmp_path)
    def timeout(*args, **kwargs):
        return {"status": "timed_out", "code": "timed_out", "exit_code": -9,
                "stdout": "", "stderr": "deadline", "argv": []}
    report = analyze_demanded_functions(request, store, tmp_path / "timeout", "worker", runner=timeout)
    assert report["status"] == "failed" and report["exit_code"] == 1
    assert any(item["code"] == "timed_out" for item in report["frontier"])
    assert failed_report("unit", "错误", "Broken")["safety"] == "not_evaluated"
    bad = json.loads(request.read_text()); bad["evidence"][0]["digest"] = "f" * 64
    bad["semantic_digest"] = None
    from memory_order_analyzer.demand_contracts import semantic_digest
    bad["semantic_digest"] = semantic_digest(bad)
    bad_path = tmp_path / "bad.json"; bad_path.write_text(json.dumps(bad))
    with pytest.raises(AnalysisError, match="identity changed"):
        analyze_demanded_functions(bad_path, store, tmp_path / "bad-out", "worker", runner=successful_runner)
    with pytest.raises(AnalysisError, match="fresh output"):
        analyze_demanded_functions(request, store, tmp_path / "timeout", "worker", runner=successful_runner)


def test_cli_is_explicit_dispatches_and_reports_failures(tmp_path, monkeypatch):
    parsed = cli.parser().parse_args(["analyze-demanded-functions", "--request", "r",
                                      "--artifact-store", "s", "--output", "o"])
    assert parsed.operation == "analyze-demanded-functions" and parsed.worker
    expected = failed_report("unit", "broken")
    monkeypatch.setattr(cli, "analyze_demanded_functions", lambda *args: expected)
    report, details = cli.execute(parsed)
    assert report == expected and details is None
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(["analyze-demanded-functions"], stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["kind"] == "DemandDrivenAnalysisReport"
    def fail(*args): raise AnalysisError("classified", "detail")
    monkeypatch.setattr(cli, "analyze_demanded_functions", fail)
    argv = ["analyze-demanded-functions", "--request", "r", "--artifact-store", "s", "--output", "o"]
    out, err = io.StringIO(), io.StringIO()
    assert cli.main(argv, stdout=out, stderr=err) == 1
    assert json.loads(out.getvalue())["status"] == "failed" and "detail" in err.getvalue()


def test_input_resolution_artifact_failures_and_frontier_limits(tmp_path):
    store, request_path = make_store(tmp_path)
    request_value = json.loads(request_path.read_text())
    reference = request_value["evidence"][0]
    with pytest.raises(AnalysisError, match="escapes"):
        _resolve_evidence(store, {**reference, "path": "../outside.json"})
    with pytest.raises(AnalysisError, match="missing"):
        _resolve_evidence(store, {**reference, "path": "missing.json"})
    existing = reference["path"]
    with pytest.raises(AnalysisError, match="Unsupported"):
        _resolve_evidence(store, {**reference, "kind": "Other", "path": existing})

    no_ir = deepcopy(request_value)
    no_ir["members"][0].update(bc_digest=None, evidence_mode="ast-only")
    _, _, paths = _load_inputs(no_ir, store)
    assert paths == {}
    changed = deepcopy(request_value); changed["members"][0]["bc_digest"] = "f" * 64
    with pytest.raises(AnalysisError, match="manifest identity"):
        _load_inputs(changed, store)
    artifact = store / "artifacts" / f"{A}.bc"
    saved = artifact.read_bytes(); artifact.unlink()
    with pytest.raises(AnalysisError, match="missing or changed"):
        _load_inputs(request_value, store)
    artifact.write_bytes(saved)

    one = failed_report("one", "一", "one")["frontier"][0]
    two = failed_report("two", "二", "two")["frontier"][0]
    assert _deduplicate_frontier([two, one, one], 1) == [one]


def test_partial_shards_time_and_output_budgets_are_conservative(tmp_path):
    store, request_path = make_store(tmp_path)
    request_value = json.loads(request_path.read_text())
    member_value = request_value["members"][0]
    index_value = demand_document(
        "LLVMModuleIndexFacts", artifact_key=A, physical_tu_id="tu", bc_digest=member_value["bc_digest"],
        profile_id="clang-c11", target=member_value["target"], data_layout=member_value["data_layout"],
        abi="itanium", status="complete", symbols=[], source_bindings=[],
        counts={"indexed_symbols": 0, "indexed_functions": 0, "defined_functions": 0,
                "materialized_functions": 0, "materialized_instructions": 0},
        dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    raw = raw_shard({"artifact_key": A}, {"function_id": f"{A}:symbol:main",
        "function_name": "main", "context_id": "ctx"}, "semantic")
    raw.update(status="partial", error=None, facts={"reference_closed": False}, counts={})
    wrapped = _wrap_shard(request_value, member_value, index_value, raw, "attempt")
    assert wrapped["status"] == "partial" and wrapped["frontier"][0]["code"] == "function-shard-failed"

    ticks = iter([0.0, 999999.0])
    timed = analyze_demanded_functions(request_path, store, tmp_path / "timed", "worker",
                                        runner=successful_runner, clock=lambda: next(ticks))
    assert timed["status"] == "partial"
    assert any(item["code"] == "request-time-budget-exhausted" for item in timed["frontier"])

    limited = json.loads(request_path.read_text())
    limited["budgets"]["request_output_bytes"] = 1
    from memory_order_analyzer.demand_contracts import semantic_digest
    limited["semantic_digest"] = semantic_digest(limited)
    limited_path = tmp_path / "limited.json"; limited_path.write_text(json.dumps(limited))
    with pytest.raises(AnalysisError, match="output exceeds"):
        analyze_demanded_functions(limited_path, store, tmp_path / "limited-out", "worker", runner=successful_runner)

    resource = json.loads(request_path.read_text())
    resource["budgets"].update(cpu_seconds=1, rss_bytes=1, worker_output_bytes=1)
    resource["semantic_digest"] = semantic_digest(resource)
    resource_path = tmp_path / "resource.json"; resource_path.write_text(json.dumps(resource))
    def resource_runner(argv, cwd, **kwargs):
        result = successful_runner(argv, cwd, **kwargs)
        entry = json.loads(result["stdout"])
        entry["results"][0]["metrics"].update(cpu_seconds=2, peak_rss_bytes=2, output_bytes=2)
        result["stdout"] = json.dumps(entry)
        return result
    report = analyze_demanded_functions(resource_path, store, tmp_path / "resource-out", "worker",
                                         runner=resource_runner)
    assert report["status"] == "partial"
    assert {item["code"] for item in report["frontier"]} >= {
        "cpu-budget-exhausted", "rss-budget-exhausted", "worker-output-budget-exhausted"}
