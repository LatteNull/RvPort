from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.demand_cache import DemandAnalysisCache, cache_key
from memory_order_analyzer.demand_contracts import (
    demand_document, dependency, diagnostic, expected_demand_protocol,
    read_demand_document, semantic_digest, validate_demand_document,
    validate_reference_closure,
)


A, B = "a" * 64, "b" * 64


def request(**updates):
    fields = {
        "scope_id": "scope", "closed_scope": True, "target": "x86_64-pc-linux-gnu",
        "data_layout": "e-p:64:64-i128:128", "abi": "itanium",
        "members": [{"physical_tu_id": "tu", "artifact_key": A, "bc_digest": B,
                     "profile_id": "clang-c11", "compiler": "clang", "language": "c",
                     "standard": "c11", "target": "x86_64-pc-linux-gnu",
                     "data_layout": "e-p:64:64-i128:128", "abi": "itanium",
                     "evidence_mode": "ast+ir"}],
        "evidence": [
            {"kind": "RootDrivenAnalysisPlan", "id": "scope", "schema_version": 1,
             "producer": "execution-root-driven-analysis-v1", "digest": A, "path": "r1/plan.json"},
            {"kind": "ThreadEntryRootOverlay", "id": "scope", "schema_version": 1,
             "producer": "thread-entry-discovery-v1", "digest": B, "path": "r11/overlay.json"},
        ],
        "layers": ["effect", "semantic", "thread"],
        "budgets": deepcopy(expected_demand_protocol()["budgets"]), "semantic_digest": None,
    }
    fields.update(updates)
    return demand_document("DemandDrivenAnalysisRequest", **fields)


def index(**updates):
    fields = {"artifact_key": A, "physical_tu_id": "tu", "bc_digest": B,
              "profile_id": "clang-c11", "target": "x86_64-pc-linux-gnu",
              "data_layout": "e-p:64:64-i128:128", "abi": "itanium", "status": "complete",
              "symbols": [{"id": f"{A}:symbol:main", "name": "main", "declaration": False,
                           "materializable": True, "linkage": "external", "visibility": "default",
                           "comdat": None}], "source_bindings": [],
              "counts": {"indexed_symbols": 1, "indexed_functions": 1, "defined_functions": 1,
                         "materialized_functions": 0, "materialized_instructions": 0},
              "dependencies": [], "diagnostics": [], "frontier": [], "semantic_digest": None}
    fields.update(updates)
    return demand_document("LLVMModuleIndexFacts", **fields)


def shard(layer="semantic", status="completed", **updates):
    kind = {"semantic": "FunctionSemanticFacts", "effect": "FunctionEffectFacts",
            "thread": "FunctionThreadFacts"}[layer]
    frontier = [] if status == "completed" else [diagnostic("unit", "不完整", "Incomplete", layer=layer)]
    fields = {"scope_id": "scope", "artifact_key": A, "physical_tu_id": "tu", "bc_digest": B,
              "function_id": f"{A}:symbol:main", "function_name": "main", "context_id": "root",
              "layer": layer, "status": status, "facts": {"reference_closed": status == "completed"},
              "counts": {}, "dependencies": [], "diagnostics": deepcopy(frontier),
              "frontier": frontier, "semantic_digest": None}
    fields.update(updates)
    return demand_document(kind, **fields)


def graph(**updates):
    node = {"id": A, "artifact_key": A, "function_id": f"{A}:symbol:main", "function_name": "main",
            "context_id": "root", "physical_tu_id": "tu", "layers": ["semantic"],
            "state": "completed", "root_ids": ["main"], "consumers": ["P2"],
            "reasons": ["execution-root"], "depth": 0}
    fields = {"scope_id": "scope", "request_hash": A, "status": "complete", "nodes": [node],
              "edges": [], "counts": {"completed": 1, "total": 1}, "dependencies": [],
              "diagnostics": [], "frontier": [], "semantic_digest": None}
    fields.update(updates)
    return demand_document("AnalysisDemandGraph", **fields)


def test_protocol_request_and_diagnostics_are_strict(tmp_path):
    assert expected_demand_protocol()["kinds"]["FunctionThreadFacts"] == 1
    value = request()
    assert validate_demand_document(value, value["kind"]) is value
    item = diagnostic("x", "中" * 5000, "e" * 5000, suggestion="修复", suggestion_en="fix", limit=128)
    assert len(item["reason"].encode()) <= 128 and item["reason_en"] and item["suggestion_en"] == "fix"
    path = tmp_path / "request.json"; path.write_text(json.dumps(value), encoding="utf-8")
    assert read_demand_document(path, value["kind"]) == value
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        read_demand_document(tmp_path / "missing", value["kind"])
    broken = tmp_path / "protocol.json"; broken.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="disagree"):
        expected_demand_protocol(broken)


@pytest.mark.parametrize("mutate,code", [
    (lambda x: x.update(schema_version=2), "schema_version"),
    (lambda x: x.update(kind="Other"), "schema_invalid"),
    (lambda x: x.update(semantic_digest="0" * 64), "semantic_digest"),
    (lambda x: x["members"][0].update(standard="c++17"), "profile_conflict"),
    (lambda x: x["evidence"][0].update(path="../escape"), "invalid_reference"),
    (lambda x: x["members"][0].update(target="other"), "profile_conflict"),
])
def test_request_rejects_invalid_contracts(mutate, code):
    value = request(); mutate(value)
    if code != "semantic_digest": value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError) as caught:
        validate_demand_document(value, "DemandDrivenAnalysisRequest")
    assert caught.value.code == code


def test_request_profiles_lineage_order_and_budgets():
    value = request(); value["members"][0].update(bc_digest=None, evidence_mode="ast-only")
    value["semantic_digest"] = semantic_digest(value)
    assert validate_demand_document(value, value["kind"])
    for update in (
        {"target": "x86_64-pc-windows-msvc"},
        {"profile_id": "clang-cl-c11"},
        {"profile_id": "libstdc++-c11"},
        {"bc_digest": None, "evidence_mode": "ir-only"},
    ):
        broken = request(); broken["members"][0].update(update)
        if "target" in update: broken["target"] = update["target"]
        broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError): validate_demand_document(broken, broken["kind"])
    broken = request(); broken["layers"] = ["thread", "semantic"]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="sorted"): validate_demand_document(broken, broken["kind"])
    broken = request(); broken["budgets"]["translation_units"] = 1
    broken["members"].append({**deepcopy(broken["members"][0]), "physical_tu_id": "tu2", "artifact_key": "c" * 64})
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="budget"): validate_demand_document(broken, broken["kind"])


def test_index_shard_graph_manifest_and_report_semantics():
    assert index()["status"] == "complete"
    broken = index(); broken["counts"]["materialized_functions"] = 1; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="must not materialize"): validate_demand_document(broken, broken["kind"])
    broken = index(); broken.update(status="partial", frontier=[], diagnostics=[])
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="require a frontier"): validate_demand_document(broken, broken["kind"])
    assert shard("effect")["kind"] == "FunctionEffectFacts"
    broken = shard("semantic"); broken["facts"]["reference_closed"] = False; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="closed reference"): validate_demand_document(broken, broken["kind"])
    value = graph()
    broken = deepcopy(value); broken["nodes"][0]["state"] = "invented"; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="invalid state"): validate_demand_document(broken, broken["kind"])
    broken = deepcopy(value); broken["edges"] = [{"id": B, "source": A, "target": B}]; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="unknown node"): validate_demand_document(broken, broken["kind"])
    manifest = demand_document("WorkerExecutionManifest", scope_id="scope", request_hash=A,
        status="complete", batches=[{"batch_id": "x", "wall_seconds": 1.0}], metrics={"cache_hits": 0},
        dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    changed = deepcopy(manifest); changed["batches"][0]["wall_seconds"] = 100.0
    changed["semantic_digest"] = semantic_digest(changed)
    assert changed["semantic_digest"] == manifest["semantic_digest"]
    graph_ref = dependency("AnalysisDemandGraph", "scope", value)
    manifest_ref = dependency("WorkerExecutionManifest", "scope", manifest)
    report = demand_document("DemandDrivenAnalysisReport", scope_id="scope", request_hash=A,
        status="complete", exit_code=0, safety="not_evaluated", findings=None,
        demand_graph=graph_ref, worker_manifest=manifest_ref,
        counts={"demanded": 1, "completed": 1, "partial": 0, "failed": 0}, coverage={},
        resources={}, cache={}, dependencies=sorted([graph_ref, manifest_ref], key=lambda x: (x["kind"], x["id"])),
        diagnostics=[], frontier=[], semantic_digest=None)
    assert report["exit_code"] == 0
    for field, value in (("exit_code", 2), ("safety", "safe")):
        broken = deepcopy(report); broken[field] = value; broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError): validate_demand_document(broken, broken["kind"])
    broken = deepcopy(report); broken["counts"]["completed"] = 0; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="counts"): validate_demand_document(broken, broken["kind"])
    with pytest.raises(AnalysisError, match="Unknown R3"): validate_demand_document({}, "Unknown")


def test_reference_closure_and_completed_shard_cache(tmp_path, monkeypatch):
    parent = graph(); child = index()
    parent["dependencies"] = [dependency(child["kind"], A, child)]; parent["semantic_digest"] = semantic_digest(parent)
    documents = {(parent["kind"], "scope"): parent, (child["kind"], A): child}
    assert validate_reference_closure((parent["kind"], "scope"), documents)
    changed = deepcopy(child); changed["counts"]["indexed_symbols"] = 2; changed["semantic_digest"] = semantic_digest(changed)
    documents[(child["kind"], A)] = changed
    with pytest.raises(AnalysisError, match="digest changed"): validate_reference_closure((parent["kind"], "scope"), documents)
    cyclic = deepcopy(parent); cyclic["dependencies"] = [dependency(parent["kind"], "scope", parent)]
    cyclic["semantic_digest"] = semantic_digest(cyclic)
    with pytest.raises(AnalysisError, match="cycle"): validate_reference_closure((parent["kind"], "scope"), {(parent["kind"], "scope"): cyclic})

    cache = DemandAnalysisCache(tmp_path)
    key = cache_key(bc_digest=B, profile_id="clang-c11", target="x", data_layout="e", function_id="f",
                    layer="semantic", context_id="c", policy_id="p", budgets={"x": 1})
    value = shard()
    cache.publish("semantic", key, value)
    assert cache.publish("semantic", key, value).is_file()
    assert cache.load("semantic", key, value["kind"]) == value
    conflicting = deepcopy(value); conflicting["counts"] = {"instructions": 1}
    conflicting["semantic_digest"] = semantic_digest(conflicting)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("semantic", key, conflicting)
    with pytest.raises(AnalysisError, match="completed"): cache.publish("semantic", key, shard(status="partial"))
    with pytest.raises(AnalysisError): cache._path("bad", key)
    with pytest.raises(AnalysisError): cache._path("semantic", "bad")
    cache._path("semantic", key).write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid R3 cache"): cache.load("semantic", key, value["kind"])


def test_cache_atomic_publish_race_accepts_identical_winner(tmp_path, monkeypatch):
    cache = DemandAnalysisCache(tmp_path)
    key = cache_key(bc_digest=B, profile_id="clang-c11", target="x", data_layout="e", function_id="f",
                    layer="semantic", context_id="c", policy_id="p", budgets={"x": 1})
    value = shard()
    import memory_order_analyzer.demand_cache as module
    real_link = module.os.link
    def raced(source, target):
        real_link(source, target)
        raise FileExistsError(target)
    monkeypatch.setattr(module.os, "link", raced)
    assert cache.publish("semantic", key, value).is_file()
