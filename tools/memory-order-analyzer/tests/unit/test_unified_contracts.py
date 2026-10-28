from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.unified_contracts import (
    diagnostic, expected_unified_protocol, failed_report, read_unified_document,
    semantic_digest, unified_document, validate_unified_document,
)


def budgets(**updates):
    value = dict(expected_unified_protocol()["budgets"])
    value.update(updates)
    return value


def request(**updates):
    fields = {
        "policy_preset": "bounded-default-v1", "project": {"id": "project", "name": "示例"},
        "bundle": {"path": "bundle/manifest.json", "sha256": "a" * 64},
        "scope_selection": {"mode": "all", "scope_ids": []}, "source_assistance": "auto",
        "source_requests": [], "explicit_roots": [],
        "cache": {"mode": "read-write", "resume": True}, "cancel_file": None,
        "budgets": budgets(),
    }
    fields.update(updates)
    return unified_document("UnifiedMemoryOrderAnalysisRequest", **fields)


def test_protocol_request_round_trip_and_runtime_paths_do_not_change_digest(tmp_path):
    assert expected_unified_protocol()["finding_schema_version"] == "3.0"
    assert expected_unified_protocol()["cache_namespace"] == "unified-project-analysis-results-v3"
    assert len(diagnostic("test", "中" * 600, "x" * 600)["detail"]) == 512
    value = request()
    changed = request(bundle={"path": "elsewhere/manifest.json", "sha256": "a" * 64},
                      cache={"mode": "disabled", "resume": False},
                      cancel_file=str((tmp_path / "cancel").resolve()))
    assert value["semantic_digest"] == changed["semantic_digest"]
    path = tmp_path / "request.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert read_unified_document(path, value["kind"]) == value
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        read_unified_document(tmp_path / "missing", value["kind"])


def test_v2_request_declares_source_request_version_and_v1_remains_readable():
    legacy = request()
    assert legacy["schema_version"] == 1
    source_reference = {"record_id": "tu", "path": "source/tu.json", "sha256": "b" * 64,
                        "schema_version": 2}
    current = request(source_requests=[source_reference])
    assert current["schema_version"] == 2
    broken = deepcopy(current)
    broken["source_requests"][0].pop("schema_version")
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="schema_version=2"):
        validate_unified_document(broken, "UnifiedMemoryOrderAnalysisRequest")


@pytest.mark.parametrize("changes,match", [
    ({"scope_selection": {"mode": "all", "scope_ids": ["scope"]}}, "all selection"),
    ({"scope_selection": {"mode": "explicit", "scope_ids": []}}, "explicit selection"),
    ({"scope_selection": {"mode": "explicit", "scope_ids": ["z", "a"]}}, "sorted"),
    ({"bundle": {"path": "../manifest.json", "sha256": "a" * 64}}, "relative"),
    ({"source_requests": [{"record_id": "b", "path": "b.json", "sha256": "b" * 64},
                           {"record_id": "a", "path": "a.json", "sha256": "a" * 64}]}, "sorted"),
    ({"explicit_roots": [{"kind": "program-entry", "symbol": "z"},
                          {"kind": "program-entry", "symbol": "a"}]}, "sorted"),
    ({"cancel_file": "relative.cancel"}, "absolute"),
])
def test_request_cross_field_rejections(changes, match):
    with pytest.raises(AnalysisError, match=match):
        request(**changes)


def test_request_schema_budget_unknown_and_digest_rejections():
    with pytest.raises(AnalysisError):
        request(budgets=budgets(scopes=0))
    value = request()
    for mutation in (
        lambda item: item.update(extra=True),
        lambda item: item.update(policy_preset="all-stages-off"),
        lambda item: item.update(semantic_digest="0" * 64),
        lambda item: item.update(schema_version=3),
    ):
        broken = deepcopy(value); mutation(broken)
        with pytest.raises(AnalysisError):
            validate_unified_document(broken, value["kind"])
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_unified_document({}, "Unknown")


def _stage(identifier, dependencies=(), scope="scope", status="planned"):
    return {"id": identifier, "scope_id": scope, "stage": identifier[0], "version": "v1",
            "producer": "org.rvport.memory-order-analyzer.test", "inputs": [], "outputs": [],
            "dependencies": list(dependencies), "status": status, "applicability": "unit",
            "budget_key": "stages", "cache_policy": "complete-only", "failure_policy": "isolate"}


def test_plan_execution_and_report_contracts():
    a, b = "a" * 64, "b" * 64
    plan = unified_document("UnifiedAnalysisPlan", request_digest="c" * 64, bundle_id="bundle",
                            selected_scopes=["scope"], stages=[_stage(a), _stage(b, [a])],
                            edges=[{"from": a, "to": b}], diagnostics=[], frontier=[])
    assert plan["semantic_digest"] == semantic_digest(plan)
    record = unified_document(
        "ScopeAnalysisExecutionRecord", scope_id="scope", status="partial",
        tu_modes=[{"record_id": "tu", "physical_tu_id": "d" * 64, "mode": "ir-only",
                   "status": "partial", "available_evidence": ["ir"], "missing_evidence": ["ast"]}],
        stages=[{"stage_id": a, "stage": "a", "status": "unknown", "cache": "miss",
                 "outputs": [], "diagnostics": [], "frontier": []}], counts={}, diagnostics=[],
        frontier=[diagnostic("x", "不完整", "incomplete", scope_id="scope")])
    reference = {"kind": record["kind"], "id": "scope", "producer": "producer", "schema_version": 1,
                 "digest": "e" * 64, "path": "scopes/scope.json"}
    report = unified_document(
        "UnifiedMemoryOrderAnalysisReport", project={"id": "p", "name": "p"},
        request_digest="c" * 64, bundle_id="bundle", status="partial", verdict="inconclusive",
        exit_code=2, scope_records=[reference], summary={}, findings=[], source_candidates=[],
        discharged_assessments=[], unsupported=[], frontier=[diagnostic("x", "不完整", "incomplete")],
        diagnostics=[], artifacts=[])
    assert report["exit_code"] == 2 and record["status"] == "partial"


@pytest.mark.parametrize("mutator", [
    lambda value: value["stages"][1].update(dependencies=["f" * 64]),
    lambda value: value.update(edges=[]),
    lambda value: value["stages"][0].update(scope_id="other"),
    lambda value: value["stages"][0].update(dependencies=[value["stages"][1]["id"]]),
])
def test_plan_rejects_dangling_disagreement_scope_and_cycle(mutator):
    a, b = "a" * 64, "b" * 64
    value = unified_document("UnifiedAnalysisPlan", request_digest="c" * 64, bundle_id="bundle",
                             selected_scopes=["scope"], stages=[_stage(a), _stage(b, [a])],
                             edges=[{"from": a, "to": b}], diagnostics=[], frontier=[])
    mutator(value)
    if value["stages"][0]["dependencies"]:
        value["edges"] = sorted([{"from": dep, "to": item["id"]} for item in value["stages"]
                                 for dep in item["dependencies"]], key=lambda item: (item["from"], item["to"]))
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError):
        validate_unified_document(value, value["kind"])


def test_execution_and_report_reject_inconsistent_claims_and_failure_builder():
    base = failed_report("bad", "错误", "broken")
    assert base["status"] == "failed" and base["exit_code"] == 1
    broken = deepcopy(base); broken.update(status="complete", verdict="no-finding-within-supported-model", exit_code=0,
                                           frontier=[], diagnostics=[])
    broken["semantic_digest"] = semantic_digest(broken)
    assert validate_unified_document(broken, broken["kind"])["exit_code"] == 0
    for status, verdict, code in (("complete", "risk", 3), ("partial", "risk", 3),
                                  ("partial", "no-finding-within-supported-model", 0)):
        invalid = deepcopy(base); invalid.update(status=status, verdict=verdict, exit_code=code)
        invalid["semantic_digest"] = semantic_digest(invalid)
        with pytest.raises(AnalysisError, match="verdict"):
            validate_unified_document(invalid, invalid["kind"])
    cancelled = failed_report("cancel", "取消", "cancelled", cancelled=True)
    assert cancelled["status"] == "cancelled"


def test_report_rejects_mixed_versions_and_wrong_result_collection():
    from memory_order_analyzer.finding_projection import project_assessment
    from memory_order_analyzer.finding_contracts import provenance
    source = project_assessment("scope", {"id": "source"},
        [provenance("Fact", "id", "org.rvport.memory-order-analyzer.test", 1, "a" * 64)], category="source")
    report = failed_report("partial", "证据不完整", "Incomplete evidence")
    report["source_candidates"] = [source]
    report["finding_schema_version"] = "2.0"
    report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="version disagrees"):
        validate_unified_document(report, report["kind"])
    report["finding_schema_version"] = "3.0"
    report["findings"], report["source_candidates"] = [source], []
    report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="wrong Finding verdict"):
        validate_unified_document(report, report["kind"])
