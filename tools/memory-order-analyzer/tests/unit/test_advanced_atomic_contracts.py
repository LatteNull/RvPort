import json
from copy import deepcopy
from pathlib import Path

import pytest

from memory_order_analyzer.advanced_atomic_contracts import (
    MODEL_ID,
    advanced_atomic_document,
    diagnostic,
    expected_advanced_atomic_protocol,
    failed_report,
    semantic_digest,
    validate_advanced_atomic_document,
    verify_input,
)
from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash


def budgets(**updates):
    value = dict(expected_advanced_atomic_protocol()["budgets"])
    value.update(updates)
    return value


def input_ref(path):
    return {"path": str(path), "sha256": file_hash(path)}


def request(tmp_path):
    module = tmp_path / "module.json"
    module.write_text("{}", encoding="utf-8")
    return advanced_atomic_document(
        "FenceRmwPublicationRequest", model_id=MODEL_ID, scope_id="scope",
        language_standard="c11", closed_scope=True, module_facts=[input_ref(module)],
        source_facts=[], thread_graph=None, provenance_graph=None, publication_graph=None,
        root_plan=None, demand_graph=None, candidate_graph=None, budgets=budgets())


def event(identifier="event", **updates):
    value = {
        "id": identifier, "artifact_key": "a" * 64, "function_id": "f", "context_id": None,
        "thread_instance_id": None, "source_id": identifier, "kind": "load", "outcome": "single",
        "object_key": "object", "offset_bytes": 0, "size_bytes": 4, "address_space": 0,
        "ordering": "acquire", "failure_ordering": None, "syncscope": "system",
        "operation": None, "compare_ref": None, "desired_ref": None, "observed_ref": "r",
        "value": None, "weak": False, "guards": [], "multiplicity": "single",
        "mo_member": False, "read_effect": True, "write_effect": False,
        "status": "exact", "reason": None, "evidence": ["p1:e"],
    }
    value.update(updates)
    return value


def test_protocol_request_digest_and_bilingual_diagnostic(tmp_path):
    protocol = expected_advanced_atomic_protocol()
    assert protocol["kinds"]["BoundedAtomicCommunicationGraph"] == 1
    value = request(tmp_path)
    assert validate_advanced_atomic_document(value, "FenceRmwPublicationRequest") is value
    item = diagnostic("x", "中文", "English", suggestion="建议", suggestion_en="Suggestion")
    assert item["suggestion_en"] == "Suggestion"
    with pytest.raises(AnalysisError, match="Bilingual"):
        diagnostic("x", "中文", "English", suggestion="only")


def test_independent_function_shard_is_versioned_and_digest_checked():
    shard = advanced_atomic_document(
        "AdvancedAtomicFunctionFacts", artifact_key="a" * 64,
        function_id="a" * 64 + ":symbol:f", function_name="f", context_id="ctx",
        layer="advanced-atomic", status="complete",
        facts={"reference_closed": True, "atomic_events": []},
        counts={"instructions": 0, "calls": 0, "accesses": 0, "atomic_events": 0},
        error=None)
    assert validate_advanced_atomic_document(shard, "AdvancedAtomicFunctionFacts") is shard
    stale = deepcopy(shard)
    stale["semantic_digest"] = "0" * 64
    with pytest.raises(AnalysisError, match="semantic digest"):
        validate_advanced_atomic_document(stale, "AdvancedAtomicFunctionFacts")


def test_request_rejects_versions_duplicates_and_bad_input(tmp_path):
    value = request(tmp_path)
    bad = dict(value, schema_version=2)
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_advanced_atomic_document(bad, "FenceRmwPublicationRequest")
    bad = dict(value, module_facts=value["module_facts"] * 2)
    with pytest.raises(AnalysisError, match="Duplicate"):
        validate_advanced_atomic_document(bad, "FenceRmwPublicationRequest")
    reference = value["module_facts"][0]
    assert verify_input(reference) == {}
    broken = dict(reference, sha256="0" * 64)
    with pytest.raises(AnalysisError, match="digest"):
        verify_input(broken)
    with pytest.raises(AnalysisError, match="Missing"):
        verify_input({"path": str(tmp_path / "missing"), "sha256": "0" * 64})
    empty = dict(value, module_facts=[], source_facts=[])
    with pytest.raises(AnalysisError, match="at least one"):
        validate_advanced_atomic_document(empty, "FenceRmwPublicationRequest")
    source_only = dict(value, module_facts=[], source_facts=value["module_facts"])
    assert validate_advanced_atomic_document(source_only, "FenceRmwPublicationRequest") is source_only


def test_local_event_semantics_reject_false_cas_and_fence():
    cas = event(kind="cas", outcome="success", read_effect=True, write_effect=True, mo_member=True)
    local = advanced_atomic_document(
        "AdvancedAtomicLocalFacts", scope_id="scope", language_standard="c++20", dependencies=[],
        events=[cas], local_order=[], status="complete", frontier=[], diagnostics=[])
    assert local["semantic_digest"] == semantic_digest(local)
    bad = json.loads(canonical(local))
    bad["events"][0]["write_effect"] = False
    bad["semantic_digest"] = semantic_digest(bad)
    with pytest.raises(AnalysisError, match="CAS success"):
        validate_advanced_atomic_document(bad, "AdvancedAtomicLocalFacts")
    fence = event(kind="fence", object_key="x", read_effect=False, ordering="release")
    with pytest.raises(AnalysisError, match="Fence"):
        advanced_atomic_document(
            "AdvancedAtomicLocalFacts", scope_id="scope", language_standard="c11", dependencies=[],
            events=[fence], local_order=[], status="complete", frontier=[], diagnostics=[])


def test_graph_references_and_complete_frontier_are_strict():
    load = event()
    graph = advanced_atomic_document(
        "BoundedAtomicCommunicationGraph", model_id=MODEL_ID, scope_id="scope",
        language_standard="c11", release_sequence_policy="c11-c17-cpp17-v1",
        dependencies=[], events=[load], rf_edges=[], mo_orders=[], assignments=[],
        release_sequences=[], fence_pairings=[], assessments=[], counts={}, status="complete",
        frontier=[], diagnostics=[])
    assert graph["status"] == "complete"
    bad = json.loads(canonical(graph))
    bad["rf_edges"] = [{"id": "rf", "write_event": "missing", "read_event": "event"}]
    bad["semantic_digest"] = semantic_digest(bad)
    with pytest.raises(AnalysisError, match="missing event"):
        validate_advanced_atomic_document(bad, "BoundedAtomicCommunicationGraph")
    bad = json.loads(canonical(graph))
    bad["frontier"] = [diagnostic("open", "未闭合", "Open")]
    bad["semantic_digest"] = semantic_digest(bad)
    with pytest.raises(AnalysisError, match="frontier"):
        validate_advanced_atomic_document(bad, "BoundedAtomicCommunicationGraph")


@pytest.mark.parametrize(
    ("exit_code", "status", "verdict", "findings", "frontier"),
    [
        (0, "complete", "complete-no-supported-risk", [], []),
        (3, "complete", "risk", [{"id": "finding"}], []),
        (2, "partial", "inconclusive", [], [diagnostic("open", "未闭合", "Open")]),
        (1, "failed", "failed", [], [diagnostic("failed", "失败", "Failed")]),
    ],
)
def test_report_exit_contract(exit_code, status, verdict, findings, frontier):
    report = advanced_atomic_document(
        "FenceRmwPublicationReport", model_id=MODEL_ID, scope_id="scope",
        language_standard="c17", status=status, verdict=verdict, safety="not_established",
        exit_code=exit_code, stages={}, counts={}, outputs=[], cache={"hits": 0, "misses": 0},
        findings=findings, frontier=frontier, diagnostics=[], limitations=["bounded"])
    assert report["exit_code"] == exit_code


def test_failed_report_and_semantic_digest_exclude_operational_fields():
    report = failed_report("broken", "失败", "Failed")
    assert report["exit_code"] == 1
    left = {"semantic_digest": "ignored", "cache": {"hits": 0}, "value": 1}
    right = {"semantic_digest": "other", "cache": {"hits": 99}, "value": 1}
    assert semantic_digest(left) == semantic_digest(right)


def test_protocol_and_json_load_failures_are_classified(tmp_path, monkeypatch):
    missing = tmp_path / "missing-protocol.json"
    with pytest.raises(AnalysisError, match="Invalid or missing JSON"):
        expected_advanced_atomic_protocol(missing)
    bad_protocol = tmp_path / "protocol.json"
    bad_protocol.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="does not match"):
        expected_advanced_atomic_protocol(bad_protocol)

    import memory_order_analyzer.advanced_atomic_contracts as contracts
    schema_root = tmp_path / "root"
    (schema_root / "schemas").mkdir(parents=True)
    (schema_root / "schemas/advanced_atomic.json").write_text(
        json.dumps({"$defs": {"Budgets": {"properties": {"broken": None}}}}), encoding="utf-8")
    monkeypatch.setattr(contracts, "ROOT", schema_root)
    with pytest.raises(AnalysisError, match="budget schema"):
        contracts.expected_advanced_atomic_protocol(bad_protocol)


def test_request_optional_inputs_nul_relative_and_duplicate_paths(tmp_path):
    value = request(tmp_path)
    reference = value["module_facts"][0]
    relative = {"path": Path(reference["path"]).name, "sha256": reference["sha256"]}
    assert verify_input(relative, base=tmp_path) == {}
    bad = deepcopy(value)
    bad["thread_graph"] = reference
    bad["source_facts"] = [reference]
    with pytest.raises(AnalysisError, match="Duplicate"):
        validate_advanced_atomic_document(bad, "FenceRmwPublicationRequest")
    bad = deepcopy(value)
    bad["module_facts"][0]["path"] = "bad\0path"
    with pytest.raises(AnalysisError, match="NUL"):
        validate_advanced_atomic_document(bad, "FenceRmwPublicationRequest")


def test_all_event_semantic_invariants_and_duplicate_identity():
    valid = event()
    local_fields = dict(scope_id="scope", language_standard="c11", dependencies=[],
                        local_order=[], status="complete", frontier=[], diagnostics=[])
    with pytest.raises(AnalysisError, match="Duplicate advanced"):
        advanced_atomic_document("AdvancedAtomicLocalFacts", events=[valid, valid], **local_fields)
    invalid_events = [
        (event(kind="cas", outcome="single"), "explicit outcome"),
        (event(kind="cas", outcome="failure", write_effect=True), "read-only"),
        (event(kind="load", outcome="success"), "Only CAS"),
        (event(kind="rmw", read_effect=True, write_effect=False, mo_member=True), "RMW"),
    ]
    for invalid, message in invalid_events:
        with pytest.raises(AnalysisError, match=message):
            advanced_atomic_document("AdvancedAtomicLocalFacts", events=[invalid], **local_fields)
    frontier = [diagnostic("open", "未闭合", "Open")]
    with pytest.raises(AnalysisError, match="Complete local"):
        advanced_atomic_document("AdvancedAtomicLocalFacts", events=[], frontier=frontier,
                                 **{key: value for key, value in local_fields.items() if key != "frontier"})


def test_graph_overlay_and_report_cross_references_are_rejected():
    load, store = event("load"), event("store", kind="store", ordering="release",
                                        read_effect=False, write_effect=True, mo_member=True)
    base = advanced_atomic_document(
        "BoundedAtomicCommunicationGraph", model_id=MODEL_ID, scope_id="scope",
        language_standard="c11", release_sequence_policy="c11-c17-cpp17-v1",
        dependencies=[], events=[load, store],
        rf_edges=[{"id": "rf", "write_event": "store", "read_event": "load"}],
        mo_orders=[{"id": "mo", "events": ["store"]}],
        assignments=[{"id": "assignment", "rf_edges": ["rf"]}], release_sequences=[],
        fence_pairings=[], assessments=[], counts={}, status="complete", frontier=[], diagnostics=[])
    variants = [
        ("mo_orders", [{"id": "mo", "events": ["missing"]}], "MO order"),
        ("assignments", [{"id": "assignment", "rf_edges": ["missing"]}], "Assignment"),
        ("rf_edges", base["rf_edges"] * 2, "Duplicate RF"),
    ]
    for field, replacement, message in variants:
        bad = deepcopy(base)
        bad[field] = replacement
        bad["semantic_digest"] = semantic_digest(bad)
        with pytest.raises(AnalysisError, match=message):
            validate_advanced_atomic_document(bad, "BoundedAtomicCommunicationGraph")

    overlay_fields = dict(scope_id="scope", dependencies=[], status="complete", frontier=[], diagnostics=[])
    with pytest.raises(AnalysisError, match="Invalid A6"):
        advanced_atomic_document("AdvancedPublicationProtocolOverlay",
                                 protocols=[{"id": "p", "assessment": "safe", "frontier": []}],
                                 **overlay_fields)
    with pytest.raises(AnalysisError, match="cannot retain"):
        advanced_atomic_document(
            "AdvancedPublicationProtocolOverlay",
            protocols=[{"id": "p", "assessment": "discharged-within-bounded-model", "frontier": ["open"]}],
            **overlay_fields)
    with pytest.raises(AnalysisError, match="Duplicate A6"):
        advanced_atomic_document(
            "AdvancedPublicationProtocolOverlay",
            protocols=[{"id": "p", "assessment": "unknown", "frontier": []}] * 2,
            **overlay_fields)


def test_invalid_report_combinations_schema_and_digest_are_rejected():
    def report(**updates):
        fields = dict(model_id=MODEL_ID, scope_id="scope", language_standard="c17",
                      status="complete", verdict="complete-no-supported-risk",
                      safety="not_established", exit_code=0, stages={}, counts={}, outputs=[],
                      cache={}, findings=[], frontier=[], diagnostics=[], limitations=["bounded"])
        fields.update(updates)
        return advanced_atomic_document("FenceRmwPublicationReport", **fields)

    for updates, message in [
        ({"status": "partial"}, "Exit zero"),
        ({"exit_code": 3, "verdict": "risk"}, "Exit three"),
        ({"exit_code": 2, "status": "partial", "verdict": "inconclusive"}, "Exit two"),
        ({"exit_code": 1, "status": "failed"}, "Exit one"),
    ]:
        with pytest.raises(AnalysisError, match=message):
            report(**updates)
    with pytest.raises(AnalysisError, match="Unknown advanced"):
        validate_advanced_atomic_document({}, "Unknown")
    valid = report()
    invalid_schema = deepcopy(valid)
    invalid_schema["unexpected"] = True
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_advanced_atomic_document(invalid_schema, "FenceRmwPublicationReport")
    stale = deepcopy(valid)
    stale["semantic_digest"] = "0" * 64
    with pytest.raises(AnalysisError, match="semantic digest"):
        validate_advanced_atomic_document(stale, "FenceRmwPublicationReport")
