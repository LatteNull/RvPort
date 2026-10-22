from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
import memory_order_analyzer.concurrent_access_contracts as contracts
from memory_order_analyzer.concurrent_access_cache import ConcurrentAccessCache, cache_key
from memory_order_analyzer.concurrent_access_contracts import (
    concurrent_access_document, dependency, diagnostic, expected_concurrent_access_protocol,
    semantic_digest, validate_compatibility, validate_concurrent_access_document,
    validate_reference_closure,
)


A, B, C = "a" * 64, "b" * 64, "c" * 64


def ref(kind, key, digest=A, path=None):
    value = {"kind": kind, "id": key, "digest": digest}
    if path is not None:
        value.update({"path": path, "schema_version": 1, "producer": "test-producer-v1"})
    return value


def request(**updates):
    fields = {
        "scope_id": "scope", "closed_scope": True, "target": "x86_64-linux-gnu",
        "data_layout": "e-p:64:64", "abi": "itanium",
        "members": [{"physical_tu_id": "tu", "profile_id": A,
                     "language": "c", "standard": "c17", "source_digest": A,
                     "bc_digest": B, "source_ir_binding_digest": A}],
        "evidence": [
            ref("EffectSummary", "summary", A, "summary.json"),
            ref("RootDrivenAnalysisPlan", "scope", A, "plan.json"),
            ref("ThreadEntryRootOverlay", "scope", A, "overlay.json"),
        ],
        "budgets": deepcopy(expected_concurrent_access_protocol()["budgets"]),
        "semantic_digest": None,
    }
    fields.update(updates)
    return concurrent_access_document("ConcurrentAccessCandidateRequest", **fields)


def projection(status="complete", accesses=None, frontier=None):
    return concurrent_access_document(
        "ConcurrentAccessProjectionFacts", scope_id="scope", request_hash=A, status=status,
        accesses=accesses or [], observed_not_demanded=[], counts={}, dependencies=[],
        diagnostics=frontier or [], frontier=frontier or [], semantic_digest=None)


def execution(status="complete", frontier=None):
    return concurrent_access_document(
        "ExecutionInstanceBindingOverlay", scope_id="scope", request_hash=A, status=status,
        roots=[], contexts=[], instances=[], invocations=[], mhp=[], exclusions=[], counts={},
        dependencies=[], diagnostics=frontier or [], frontier=frontier or [], semantic_digest=None)


def protection(status="complete", frontier=None):
    return concurrent_access_document(
        "AccessProtectionOverlay", scope_id="scope", request_hash=A, status=status,
        protections=[], counts={}, dependencies=[], diagnostics=frontier or [],
        frontier=frontier or [], semantic_digest=None)


def graph(status="complete"):
    p, e, m = projection(), execution(), protection()
    refs = [dependency(p["kind"], "scope", p), dependency(e["kind"], "scope", e),
            dependency(m["kind"], "scope", m)]
    refs.sort(key=lambda item: (item["kind"], item["id"]))
    return concurrent_access_document(
        "ConcurrentAccessCandidateGraph", scope_id="scope", request_hash=A, status=status,
        projection=next(item for item in refs if item["kind"] == p["kind"]),
        execution_instances=next(item for item in refs if item["kind"] == e["kind"]),
        protection=next(item for item in refs if item["kind"] == m["kind"]),
        accesses=[], candidates=[], exclusions=[], atomic_handoff=[], completeness={}, counts={},
        dependencies=refs, diagnostics=[], frontier=[], semantic_digest=None)


def test_protocol_request_and_bilingual_diagnostic_are_strict(tmp_path):
    protocol = expected_concurrent_access_protocol()
    assert protocol["kinds"] == dict.fromkeys(contracts.KINDS, 1)
    assert protocol["cache_namespace"] == "concurrent-access-candidate-graph-v1"
    value = request()
    assert validate_concurrent_access_document(value, value["kind"]) is value
    item = diagnostic("x", "中" * 1000, "e" * 1000, suggestion="建议",
                      suggestion_en="suggest", limit=64)
    assert len(item["detail"].encode()) <= 64 and len(item["detail_en"].encode()) <= 64
    bad = deepcopy(protocol); bad["llvm_version"] = "0"
    path = tmp_path / "protocol.json"; path.write_text(__import__("json").dumps(bad))
    with pytest.raises(AnalysisError, match="disagree"):
        expected_concurrent_access_protocol(path)
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        expected_concurrent_access_protocol(tmp_path / "missing.json")


def test_request_rejects_versions_shape_order_profiles_paths_and_budgets():
    value = request()
    broken = deepcopy(value); broken["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["extra"] = 1; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_concurrent_access_document(broken, broken["kind"])
    with pytest.raises(AnalysisError, match="Unknown R2"):
        validate_concurrent_access_document(value, "Unknown")
    broken = deepcopy(value); broken["evidence"] = broken["evidence"][1:]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="missing required evidence"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["evidence"] = list(reversed(broken["evidence"]))
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="sorted"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["members"][0]["standard"] = "c++20"
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["members"][0].update(
        source_digest=None, bc_digest=None, source_ir_binding_digest=None)
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="source or BC lineage"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["members"][0]["bc_digest"] = None
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="binding requires both"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["evidence"][0]["path"] = "../escape.json"
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="relative"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["budgets"]["translation_units"] = 1
    broken["members"].append({**broken["members"][0], "physical_tu_id": "tu2"})
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="translation unit"):
        validate_concurrent_access_document(broken, broken["kind"])


def test_outputs_require_order_dependencies_access_refs_and_no_complete_frontier():
    access = {"id": A}
    valid = projection(accesses=[access])
    assert valid["accesses"] == [access]
    broken = deepcopy(valid); broken["accesses"] = [{"id": "z"}, {"id": "a"}]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="sorted"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(valid); broken["frontier"] = [diagnostic("x", "x", "x")]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="Complete"):
        validate_concurrent_access_document(broken, broken["kind"])
    value = graph()
    broken = deepcopy(value); broken["dependencies"] = broken["dependencies"][1:]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(value); broken["accesses"] = [{"id": A}]
    broken["candidates"] = [{"id": B, "left": A, "right": B}]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="unknown access"):
        validate_concurrent_access_document(broken, broken["kind"])


def test_report_status_safety_dependency_and_semantic_digest():
    value = graph()
    graph_ref = dependency(value["kind"], "scope", value)
    report = concurrent_access_document(
        "ConcurrentAccessCandidateReport", scope_id="scope", request_hash=A,
        status="complete", exit_code=0, safety="not_evaluated", findings=None,
        graph=graph_ref, language_counts={}, completeness={}, counts={}, dependencies=[graph_ref],
        diagnostics=[], frontier=[], cache={"hits": 0, "misses": 1}, semantic_digest=None)
    assert report["semantic_digest"] == semantic_digest(report)
    changed = deepcopy(report); changed["cache"]["hits"] = 10
    assert semantic_digest(changed) == report["semantic_digest"]
    for field, replacement, message in (("exit_code", 2, "exit code"),
                                        ("safety", "safe", "safety"),
                                        ("findings", [], "safety")):
        broken = deepcopy(report); broken[field] = replacement; broken["semantic_digest"] = semantic_digest(broken)
        with pytest.raises(AnalysisError, match=message):
            validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(report); broken["dependencies"] = []
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_concurrent_access_document(broken, broken["kind"])
    broken = deepcopy(report); broken["semantic_digest"] = B
    with pytest.raises(AnalysisError, match="semantic digest"):
        validate_concurrent_access_document(broken, broken["kind"])


def test_compatibility_and_reference_closure_reject_conflicts_stale_and_cycles():
    value = request()
    assert validate_compatibility(value, [{"kind": "x", "scope_id": "scope"}])
    for field in ("scope_id", "target", "data_layout", "abi"):
        with pytest.raises(AnalysisError, match=field):
            validate_compatibility(value, [{"kind": "x", field: "other"}])
    member = deepcopy(value["members"][0])
    assert validate_compatibility(value, [{"kind": "x", "members": [member]}])
    for field in ("profile_id", "source_digest", "bc_digest", "source_ir_binding_digest"):
        with pytest.raises(AnalysisError, match=field):
            validate_compatibility(value, [{"kind": "x", "members": [{**member, field: C}]}])
    with pytest.raises(AnalysisError, match="unrequested physical TU"):
        validate_compatibility(value, [{"kind": "x", "physical_tu_id": "other"}])
    child = {"kind": "Child", "dependencies": []}
    child_key = ("Child", "child")
    parent = {"kind": "Parent", "dependencies": [dependency("Child", "child", child)]}
    documents = {("Parent", "parent"): parent, child_key: child}
    assert validate_reference_closure(("Parent", "parent"), documents)
    documents[child_key] = {"kind": "Child", "dependencies": [], "changed": True}
    with pytest.raises(AnalysisError, match="digest changed"):
        validate_reference_closure(("Parent", "parent"), documents)
    documents = {("Parent", "parent"): {"dependencies": [ref("Child", "child")]},
                 child_key: {"dependencies": [ref("Parent", "parent")]}}
    documents[("Parent", "parent")]["dependencies"][0]["digest"] = identity(documents[child_key])
    documents[child_key]["dependencies"][0]["digest"] = identity(documents[("Parent", "parent")])
    with pytest.raises(AnalysisError, match="cycle|digest changed"):
        validate_reference_closure(("Parent", "parent"), documents)
    with pytest.raises(AnalysisError, match="missing"):
        validate_reference_closure(("Absent", "x"), {})


def test_cache_isolated_complete_only_collision_corruption_and_path_rules(tmp_path, monkeypatch):
    cache = ConcurrentAccessCache(tmp_path)
    value = projection()
    key = cache_key("projection", request(), [A, B])
    assert cache.load("projection", key, value["kind"]) is None
    path = cache.publish("projection", key, value)
    assert cache.publish("projection", key, value) == path
    assert cache.load("projection", key, value["kind"]) == value
    partial = projection("partial", frontier=[diagnostic("x", "x", "x")])
    with pytest.raises(AnalysisError, match="cannot be cached"):
        cache.publish("projection", B, partial)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid R2 cache"):
        cache.load("projection", key, value["kind"])
    path.unlink()
    cache.publish("projection", key, value)
    changed = projection(accesses=[{"id": A}])
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("projection", key, changed)
    for stage, digest in (("../escape", A), ("projection", "bad")):
        with pytest.raises(AnalysisError, match="cache"):
            cache._path(stage, digest)
    fresh = ConcurrentAccessCache(tmp_path / "race")
    original = __import__("os").link
    def racing(source, destination):
        original(source, destination)
        raise FileExistsError
    monkeypatch.setattr("memory_order_analyzer.concurrent_access_cache.os.link", racing)
    assert fresh.publish("projection", B, value).is_file()
