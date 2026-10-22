from copy import deepcopy
import pytest
from memory_order_analyzer import scope as s
from memory_order_analyzer.contracts import AnalysisError, document
from memory_order_analyzer.report import make_report, ratio


def symbol(name, key, linkage="external", declaration=False, comdat=False):
    return {"name": name, "id": key + ":symbol:" + name, "linkage": linkage, "declaration": declaration, "comdat": comdat}


def scope(members, **kwargs):
    return document("ScopeManifest", target_id="app", members=members, evidence="unit explicit manifest", closed=True, external_boundaries=[], **kwargs)


def test_direct_symbols_unknown_and_invalidation(fixture_module, fixture_artifact):
    a, b = "a" * 64, "b" * 64
    artifacts = {a: fixture_artifact, b: {**fixture_artifact, "artifact_key": b}}
    facts = {a: fixture_module, b: {**fixture_module, "artifact_key": b}}
    facts[a]["functions"] = [symbol("_Z1fi", a, declaration=True), symbol("local", a, "internal")]
    facts[b]["functions"] = [symbol("_Z1fi", b), symbol("_Z1fd", b), symbol("local", b, "internal"), symbol("weak", b, "weak"), symbol("once", b, "linkonce", comdat=True)]
    facts[b]["globals"] = [symbol("x", b)]
    facts[a]["calls"] = [{"id": str(i), "kind": "direct" if name else "indirect", "target": name, "source": {"inline_chain": []}} for i, name in enumerate(("_Z1fi", "local", "missing", None, "weak", "once"))]
    facts[a]["events"] = [{"id": "global-read", "kind": "load", "source": {"inline_chain": []}, "address": {"kind": "constant_gep", "base": {"kind": "global", "symbol": "x"}, "indices": [1]}}, {"id": "unknown-read", "kind": "load", "source": {"inline_chain": []}, "address": {"kind": "unknown"}}]
    add_graph(facts[a])
    add_graph(facts[b])
    manifest = scope([a, b])
    index = s.index_scope(manifest, artifacts, facts)
    assert len(index["bindings"]) == 3 and len(index["unknown"]) == 5
    assert index["bindings"][0]["definition"]["artifact_key"] == b
    assert index["bindings"][1]["definition"]["artifact_key"] == a
    assert not index["capabilities"]["effect_propagation"]
    assert index["scope_id"] == s.index_scope(manifest, artifacts, facts)["scope_id"]
    changed = {**manifest, "target_id": "other"}
    assert index["scope_id"] != s.index_scope(changed, artifacts, facts)["scope_id"]
    assert index["scope_id"] != s.index_scope({**manifest, "members": [a]}, artifacts, facts)["scope_id"]
    assert len(s.index_scope({**manifest, "closed": False}, artifacts, facts)["bindings"]) == 1
    facts[a]["functions"][0]["declaration"] = False
    assert s.index_scope(manifest, artifacts, facts)["diagnostics"][0]["code"] == "duplicate_strong_definition"


def test_scope_preflight_conflicts(fixture_module, fixture_artifact):
    a, b = "a" * 64, "b" * 64
    artifacts = {a: fixture_artifact, b: {**fixture_artifact, "artifact_key": b}}
    facts = {a: fixture_module, b: {**fixture_module, "artifact_key": b}}
    manifest = scope([a, b])
    for mutation, expected in ((lambda ar, fa: fa[b].update(target="arm"), "target_conflict"),
                              (lambda ar, fa: fa[b].update(layout="different"), "target_conflict"),
                              (lambda ar, fa: ar[b].update(lineage=[a]), "lineage_overlap"),
                              (lambda ar, fa: fa[b].update(artifact_key=a), "invalid_reference")):
        ar, fa = deepcopy(artifacts), deepcopy(facts)
        mutation(ar, fa)
        with pytest.raises(AnalysisError) as caught:
            s.preflight(manifest, ar, fa)
        assert caught.value.code == expected
    ar = deepcopy(artifacts)
    ar[a]["toolchain"] = {"source": "/a.c", "abi": {"mabi": "a"}}
    ar[b]["toolchain"] = {"source": "/a.c", "abi": {"mabi": "b"}}
    ar[b]["context_id"] = "d" * 64
    with pytest.raises(AnalysisError, match="Mutually exclusive"):
        s.preflight(manifest, ar, facts)
    ar[b]["toolchain"]["source"] = "/b.c"
    with pytest.raises(AnalysisError, match="ABI"):
        s.preflight(manifest, ar, facts)
    with pytest.raises(AnalysisError):
        s.preflight(manifest, {}, facts)
    ar = deepcopy(artifacts)
    ar[a]["inputs"] = {"/shared.h": "a" * 64}
    ar[b]["inputs"] = {"/shared.h": "b" * 64}
    with pytest.raises(AnalysisError, match="Different input revisions"):
        s.preflight(manifest, ar, facts)
    ar[b]["inputs"] = dict(ar[a]["inputs"])
    assert s.preflight(manifest, ar, facts)


def test_integrity_counts_status_and_no_safety(fixture_artifact, fixture_module):
    fixture_module["source_mapping"] = "complete"
    fixture_module["events"] = [{"source": {"inline_chain": [1]}}]
    for operation in ("collect", "import-bc", "index", "link"):
        report = make_report(operation, planned=1, records=2, artifacts=[fixture_artifact], facts=[fixture_module])
        assert report["exit_code"] == 0 and report["scope_status"] == "unknown"
        assert report["semantic_analysis"] == "not_run" and report["safety"] == "not_evaluated" and report["findings"] is None
        assert report["counts"]["located_ratio"] == 1
    report = make_report("collect", planned=10, artifacts=[fixture_artifact] * 8, facts=[fixture_module] * 8, failures=[{"code": "missing_header"}] * 2, cached=3)
    assert report["exit_code"] == 2 and report["build_status"] == "partial"
    assert report["counts"]["planned_tus"] == 10 and report["counts"]["verified"] == 8
    assert report["counts"]["cache_hits"] == 3 and report["counts"]["success_ratio"] == 0.8
    empty = make_report("collect")
    assert empty["exit_code"] == 1 and empty["counts"]["success_ratio"] is None and empty["counts"]["located_ratio"] is None
    fixture_module["source_mapping"] = "partial"
    assert make_report("collect", planned=1, artifacts=[fixture_artifact], facts=[fixture_module])["exit_code"] == 2
    fixture_module["source_mapping"] = "unavailable"
    assert make_report("import-bc", planned=1, artifacts=[fixture_artifact], facts=[fixture_module])["source_mapping"] == "unavailable"
    assert make_report("doctor", ready=True)["exit_code"] == 0
    assert make_report("doctor", ready=True)["stages"]["ir"] == "not_run"
    assert make_report("doctor", ready=False)["exit_code"] == 1
    assert make_report("collect", failures=[{"code": "timed_out"}])["stages"]["collect"] == "timed_out"
    assert make_report("collect", failures=[{"code": "driver_unsupported"}])["stages"]["collect"] == "unsupported"
    for unknown, expected in (([], "declared"), ([1], "partial")):
        report = make_report("index", planned=1, artifacts=[fixture_artifact], facts=[fixture_module], scope={"unknown": unknown, "diagnostics": []})
        assert report["scope_status"] == expected

def add_graph(facts):
    """Explicit v2 scaffolding for symbol-resolution-only test fixtures."""
    owner = next(f["id"] for f in facts["functions"] if f["name"] == "local")
    block = owner + ":b0"
    pointer = facts["artifact_key"] + ":constant:ptr"
    facts["values"] = [{"id": pointer, "kind": "null", "type": "ptr", "type_kind": "pointer",
                        "address_space": 0, "function": None, "block": None, "operands": [], "details": {}, "status": "known"}]
    for f in facts["functions"]:
        f.update(parameters=[], return_type="void", vararg=False)
        if f["id"] == owner:
            f["blocks"] = [{"id": block, "successors": [], "terminator": {
                "id": block + ":i99", "opcode": "ret", "condition_ref": None, "return_ref": None, "edges": [], "status": "known"}}]
    for event in facts["events"]:
        event.update(function=owner, block=block, inputs={}, result_ref=None, ranges=[], range_status="unknown")
    for call in facts["calls"]:
        call.update(function=owner, called_ref=pointer, arguments=[], result_ref=None, function_type="void ()",
                    calling_convention=0, normal=None, unwind=None, tail="none", attributes="", attribute_status="not_applicable", bundles=[], status="known")
    facts["extraction"]["nodes"] = 1
