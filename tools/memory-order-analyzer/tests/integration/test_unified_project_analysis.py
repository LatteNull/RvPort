"""统一入口的四语言分母、consumer 合同和无外部构建执行验收。"""

import json
from pathlib import Path

import jsonschema

import memory_order_analyzer.unified_coordinator as coordinator
from memory_order_analyzer.contracts import canonical, file_hash
from memory_order_analyzer.finding_contracts import provenance, validate_finding
from memory_order_analyzer.finding_projection import project_assessment
from memory_order_analyzer.unified_contracts import (
    expected_unified_protocol, read_unified_document, unified_document,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/unified-project-analysis"


def test_four_language_truth_denominators_and_feature_chains():
    truth = json.loads((FIXTURE / "truth-matrix.json").read_text(encoding="utf-8"))
    profiles = {(item["language"], item["standard"]): item for item in truth["profiles"]}
    assert set(profiles) == {("c", "c11"), ("c", "c17"), ("c++", "c++17"), ("c++", "c++20")}
    assert all(item["planned"] == 5 for item in profiles.values())
    grouped = {key: [case for case in truth["cases"]
                     if (case["language"], case["standard"]) == key] for key in profiles}
    assert all(len(cases) == 5 for cases in grouped.values())
    assert all({case["mode"] for case in cases} == {"ast-ir", "ast-only", "ir-only", "failed"}
               for cases in grouped.values())
    features = {case["feature"] for case in truth["cases"]}
    assert {"pthread-publication", "thrd-create-release-acquire", "lock-guard-field",
            "jthread-cas-failure-order", "rmw-release-sequence", "fence-rmw-ambiguous-rf"} <= features
    assert all(case.get("required_steps") or case.get("required_breaks") for case in truth["cases"])


def test_consumer_contract_and_finding_collections_match_v2_shape():
    contract = json.loads((FIXTURE / "consumer-contract.json").read_text(encoding="utf-8"))
    finding_schema = json.loads((ROOT / "schemas/memory_order_finding.json").read_text(encoding="utf-8"))
    report_schema = json.loads((ROOT / "schemas/unified_project_analysis.json").read_text(encoding="utf-8"))
    assert contract["collections"] == {
        "findings": "risk", "source_candidates": "source-candidate",
        "discharged_assessments": "discharged-within-bounded-model"}
    prov = [provenance("UnitFact", "fact", "org.rvport.memory-order-analyzer.integration", 1, "a" * 64)]
    values = {
        "findings": project_assessment("scope", {"id": "risk"}, prov, category="formal"),
        "source_candidates": project_assessment("scope", {"id": "source"}, prov, category="source"),
        "discharged_assessments": project_assessment("scope", {"id": "bounded"}, prov,
                                                      category="discharged"),
    }
    for collection, value in values.items():
        validate_finding(value)
        jsonschema.Draft202012Validator({"$ref": "#/$defs/MemoryOrderFindingProjection",
                                         "$defs": finding_schema["$defs"]}).validate(value)
        assert value["conclusion"]["verdict"] == contract["collections"][collection]
        assert {"fact", "conclusion", "occurrences", "primaryOccurrenceId", "evidenceChain"} <= set(value)
    assert "UnifiedMemoryOrderAnalysisReport" in report_schema["$defs"]


def test_unified_entry_publishes_project_report_without_build_or_network_process(tmp_path, monkeypatch):
    bundle_path = tmp_path / "bundle.json"; bundle_path.write_text("{}")
    request_value = unified_document(
        "UnifiedMemoryOrderAnalysisRequest", policy_preset="bounded-default-v1",
        project={"id": "integration", "name": "integration"},
        bundle={"path": "bundle.json", "sha256": file_hash(bundle_path)},
        scope_selection={"mode": "all", "scope_ids": []}, source_assistance="disabled",
        source_requests=[], explicit_roots=[], cache={"mode": "disabled", "resume": False},
        cancel_file=None, budgets=expected_unified_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request_value))
    record = {"record_id": "tu", "physical_tu_id": "a" * 64, "source": None}
    scope = {"target_id": "scope", "records": [record]}
    bundle = {"manifest": {"bundle_id": "bundle"}, "manifest_path": bundle_path,
              "records": {"tu": record}, "source_requests": {}, "scopes": [scope]}
    plan = unified_document(
        "UnifiedAnalysisPlan", request_digest=request_value["semantic_digest"], bundle_id="bundle",
        selected_scopes=["scope"], stages=[], edges=[], diagnostics=[], frontier=[])
    execution = unified_document(
        "ScopeAnalysisExecutionRecord", scope_id="scope", status="complete", tu_modes=[], stages=[],
        counts={}, diagnostics=[], frontier=[])
    monkeypatch.setattr(coordinator, "preflight_bundle", lambda *args: bundle)
    monkeypatch.setattr(coordinator, "build_plan", lambda *args: plan)
    seen = []
    def forbidden_process(*args, **kwargs):
        seen.append(args)
        raise AssertionError("统一入口不得启动 compiler/linker/build/network/SSH/目标程序")
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", forbidden_process)
    def ingest(path, data, worker, cache_path=None):
        data.mkdir(); (data / "report.json").write_text(json.dumps({"record_artifacts": []}))
        return {"record_artifacts": []}
    analyzer = coordinator.AnalysisCoordinator(request_path, tmp_path / "result", ingest=ingest)
    monkeypatch.setattr(analyzer, "_write_request_inputs", lambda *args: {})
    monkeypatch.setattr(analyzer, "_snapshot_sources", lambda *args: ({}, {}))
    monkeypatch.setattr(analyzer, "_execute_scopes", lambda *args: (
        [coordinator._cache_payload(execution, [], [], [])], []))
    report = analyzer.run()
    assert report["status"] == "complete" and report["verdict"] == "no-finding-within-supported-model"
    assert report["exit_code"] == 0 and not seen
    assert read_unified_document(tmp_path / "result/report.json", "UnifiedMemoryOrderAnalysisReport") == report
    assert (tmp_path / "result/plan.json").is_file() and (tmp_path / "result/artifacts.json").is_file()
    forbidden = ("clang", "gcc", "llvm-link", "cmake", "ninja", "ssh", "curl", "wget")
    assert not any(token in canonical(report).lower() for token in forbidden)
