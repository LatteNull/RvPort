from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.root_cache import RootAnalysisCache, cache_key
from memory_order_analyzer.root_contracts import (
    diagnostic, expected_root_protocol, root_document, semantic_digest,
    validate_root_document,
)


A, B = "a" * 64, "b" * 64


def request(language="c", **changes):
    standard = "c11" if language == "c" else "c++17"
    evidence = [{"kind": "ModuleFacts", "id": A, "digest": B, "path": f"facts/{A}.json"}]
    fields = dict(scope_id="scope", closed_scope=True, discover_main=True,
                  members=[{"physical_tu_id": "tu", "profile_id": A,
                            "language": language, "standard": standard, "evidence": evidence}],
                  global_evidence=[], explicit_roots=[],
                  budgets=deepcopy(expected_root_protocol()["budgets"]), semantic_digest=None)
    fields.update(changes)
    return root_document("ExecutionRootDiscoveryRequest", **fields)


def outputs():
    req = request(); request_hash = identity(req)
    sites = root_document(
        "ThreadCreationSiteIndex", scope_id="scope", request_hash=request_hash,
        status="complete", sites=[], counts={"sites": 0}, dependencies=[], diagnostics=[],
        frontier=[], semantic_digest=None)
    site_ref = {"kind": "ThreadCreationSiteIndex", "id": "scope", "digest": identity(sites)}
    roots = root_document(
        "ExecutionRootIndex", scope_id="scope", request_hash=request_hash,
        status="partial", roots=[], counts={"roots": 0}, dependencies=[site_ref],
        diagnostics=[], frontier=[], semantic_digest=None)
    root_ref = {"kind": "ExecutionRootIndex", "id": "scope", "digest": identity(roots)}
    plan = root_document(
        "RootDrivenAnalysisPlan", scope_id="scope", request_hash=request_hash, status="partial",
        thread_creation_sites=site_ref, execution_roots=root_ref, reachable_functions=[], call_edges=[],
        contexts=[], demands=[], p2_requests=[], p3_requests=[], a3_overlays=[], reconciliation={},
        completeness={}, counts={}, dependencies=sorted([site_ref, root_ref], key=lambda x: (x["kind"], x["id"])),
        diagnostics=[], frontier=[], semantic_digest=None)
    plan_ref = {"kind": "RootDrivenAnalysisPlan", "id": "scope", "digest": identity(plan)}
    report = root_document(
        "RootDrivenAnalysisReport", scope_id="scope", request_hash=request_hash,
        status="partial", exit_code=2, safety="not_evaluated", findings=None,
        thread_creation_sites=site_ref, execution_roots=root_ref, plan=plan_ref,
        classification_counts={}, root_counts={}, reachable_counts={}, analysis_counts={}, completeness={},
        dependencies=sorted([site_ref, root_ref, plan_ref], key=lambda x: (x["kind"], x["id"])),
        diagnostics=[], frontier=[], cache={"hits": 0, "misses": 3}, semantic_digest=None)
    return req, sites, roots, plan, report


def test_protocol_documents_and_bilingual_bounded_diagnostic(tmp_path):
    assert expected_root_protocol()["cache_namespace"] == "execution-root-driven-analysis-v1"
    values = outputs()
    assert [item["kind"] for item in values] == [
        "ExecutionRootDiscoveryRequest", "ThreadCreationSiteIndex", "ExecutionRootIndex",
        "RootDrivenAnalysisPlan", "RootDrivenAnalysisReport"]
    item = diagnostic("x", "中" * 5000, "e" * 5000, suggestion="修复", suggestion_en="repair", limit=128)
    assert len(item["detail"].encode()) <= 128 and item["detail_en"] and item["limitation_en"]
    path = tmp_path / "request.json"; path.write_text(json.dumps(values[0]), encoding="utf-8")
    from memory_order_analyzer.root_contracts import read_root_document
    assert read_root_document(path, "ExecutionRootDiscoveryRequest") == values[0]
    assert diagnostic("x", "", "", limitation="", limitation_en="")["detail"] == "-"
    with pytest.raises(AnalysisError, match="Invalid or missing JSON"):
        read_root_document(tmp_path / "missing.json", "ExecutionRootDiscoveryRequest")
    bad_protocol = tmp_path / "protocol.json"; bad_protocol.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="protocol and schema"):
        expected_root_protocol(bad_protocol)


@pytest.mark.parametrize("mutate,code", [
    (lambda x: x.update(schema_version=2), "schema_version"),
    (lambda x: x.update(kind="bad"), "schema_invalid"),
    (lambda x: x.update(semantic_digest="0" * 64), "semantic_digest"),
    (lambda x: x["members"][0].update(standard="c++17"), "profile_conflict"),
    (lambda x: x["members"][0]["evidence"][0].update(path="../escape.json"), "invalid_reference"),
])
def test_request_rejects_version_kind_digest_profile_and_escape(mutate, code):
    value = request(); mutate(value)
    if code != "semantic_digest":
        value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="") as caught:
        validate_root_document(value, "ExecutionRootDiscoveryRequest")
    assert caught.value.code == code


def test_request_rejects_duplicate_evidence_c_cpp_mix_and_framework_without_entity():
    value = request(); value["global_evidence"] = deepcopy(value["members"][0]["evidence"])
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="declared more than once"):
        validate_root_document(value, value["kind"])
    value = request(); value["members"][0]["evidence"] = [{
        "kind": "CppThreadLocalFacts", "id": "tu", "digest": B, "path": "cpp/tu.json"}]
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="C members"):
        validate_root_document(value, value["kind"])
    value = request(explicit_roots=[{"id": "fw", "kind": "framework",
        "entry": {"artifact_key": A, "function_id": "run"}, "source_entity_id": "entity", "arguments": []}])
    value["explicit_roots"][0]["source_entity_id"] = None
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="source entity"):
        validate_root_document(value, value["kind"])
    value = request(); value["members"][0]["evidence"] = [{
        "kind": "EffectSummary", "id": "ctx", "digest": B, "path": "summaries/ctx.json"}]
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="at least one"):
        validate_root_document(value, value["kind"])
    value = request(); value["budgets"]["translation_units"] = 1
    value["members"].append({**deepcopy(value["members"][0]), "physical_tu_id": "zz"})
    value["members"][1]["evidence"][0]["id"] = "z" * 64
    value["members"][1]["evidence"][0]["path"] = "facts/z.json"
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="translation unit budget"):
        validate_root_document(value, value["kind"])


def test_output_semantics_reject_invalid_exact_site_root_plan_and_report():
    _, sites, roots, plan, report = outputs()
    sites["sites"] = [{"id": "site", "classification": "dual-exact", "callback": {"entry": None}}]
    sites["semantic_digest"] = semantic_digest(sites)
    with pytest.raises(AnalysisError, match="callback entry"):
        validate_root_document(sites, sites["kind"])
    sites["sites"][0]["classification"] = "invented"; sites["semantic_digest"] = semantic_digest(sites)
    with pytest.raises(AnalysisError, match="Unknown thread"):
        validate_root_document(sites, sites["kind"])
    roots["roots"] = [{"id": "root", "kind": "pthread", "status": "complete",
                       "entry": None, "creation_site_id": None, "thread_instance_key": None}]
    roots["semantic_digest"] = semantic_digest(roots)
    with pytest.raises(AnalysisError, match="require an entry"):
        validate_root_document(roots, roots["kind"])
    roots["roots"][0].update(status="partial", entry={"artifact_key": A, "function_id": "f"})
    roots["semantic_digest"] = semantic_digest(roots)
    with pytest.raises(AnalysisError, match="instance identity"):
        validate_root_document(roots, roots["kind"])
    plan["dependencies"] = []
    plan["semantic_digest"] = semantic_digest(plan)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_root_document(plan, plan["kind"])
    report["exit_code"] = 0; report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="exit code"):
        validate_root_document(report, report["kind"])
    report = outputs()[-1]; report["dependencies"] = []; report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_root_document(report, report["kind"])
    report = outputs()[-1]; report["safety"] = "safe"; report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="schema"):
        validate_root_document(report, report["kind"])
    with pytest.raises(AnalysisError, match="Unknown R1 contract"):
        validate_root_document({}, "Unknown")


def test_cache_hit_collision_stale_and_transient(tmp_path):
    cache = RootAnalysisCache(tmp_path)
    sites = outputs()[1]; key = cache_key("sites", {"b": 2, "a": 1}, ["b", "a"])
    assert key == cache_key("sites", {"a": 1, "b": 2}, ["a", "b"])
    cache.publish("sites", key, sites)
    assert cache.publish("sites", key, sites).is_file()
    assert cache.load("sites", key, "ThreadCreationSiteIndex") == sites
    changed = deepcopy(sites); changed["counts"]["sites"] = 1; changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("sites", key, changed)
    path = cache._path("sites", key)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid R1 cache"):
        cache.load("sites", key, "ThreadCreationSiteIndex")
    with pytest.raises(AnalysisError, match="Transient"):
        cache.publish("sites", "x", sites, stability="transient")
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../outside", "x")


def test_cache_io_and_link_race_failures(tmp_path, monkeypatch):
    cache = RootAnalysisCache(tmp_path); sites = outputs()[1]
    key = cache_key("sites", sites); path = cache._path("sites", key); path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid R1 cache"):
        cache.load("sites", key, "ThreadCreationSiteIndex")
    path.unlink()
    from memory_order_analyzer import root_cache as module
    original = module.os.link
    def raced(source, destination):
        destination.write_text(canonical(sites), encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(module.os, "link", raced)
    assert cache.publish("sites", key, sites) == path
    path.unlink()
    other = deepcopy(sites); other["counts"]["sites"] = 2; other["semantic_digest"] = semantic_digest(other)
    def conflicting(source, destination):
        destination.write_text(canonical(other), encoding="utf-8")
        raise FileExistsError
    monkeypatch.setattr(module.os, "link", conflicting)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("sites", key, sites)
    monkeypatch.setattr(module.os, "link", original)
