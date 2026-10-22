"""P5 contract and semantic validation unit tests."""

from copy import deepcopy
import json

import pytest

from memory_order_analyzer.contracts import AnalysisError, canonical, file_hash, identity
from memory_order_analyzer.validation_analysis import case_input_digest
from memory_order_analyzer.validation_contracts import (
    CAPABILITIES,
    KINDS,
    diagnostic,
    expected_validation_protocol,
    failed_validation_report,
    read_validation_document,
    validate_validation_document,
    validation_document,
    write_validation_document,
)


H = "a" * 64


def entry(path, role, digest=H):
    return {"path": path, "sha256": digest, "role": role}


def profile(identifier="c11"):
    return {"id": identifier, "language": "c", "standard": "c11", "compiler": "clang",
            "compiler_version": "21.1.8", "target": "x86_64-linux-gnu", "data_layout": "e-p:64:64",
            "optimization": "O0", "debug": True, "compile_arguments": ["-std=c11", "-pthread"]}


def case(identifier="case-1", profile_id="c11"):
    return {"id": identifier, "profile_id": profile_id, "category": "correct", "layout": "single-tu",
            "source_root": "cases/case-1", "sources": [entry("cases/case-1/main.c", "source")],
            "compile_commands": entry("cases/case-1/compile_commands.json", "compile-database"),
            "scope": entry("cases/case-1/scope.json", "scope"), "roots": ["main"],
            "truth": entry("cases/case-1/truth.json", "truth"), "stages": [],
            "observation_report": "cases/case-1/report.json", "observation_graph": "cases/case-1/graph.json"}


def suite(**changes):
    fields = {"suite_id": "offline", "suite_version": 1, "title": "离线语料", "title_en": "Offline corpus",
              "profiles": [profile()], "cases": [case()], "real_project_profile": None}
    fields.update(changes)
    return validation_document("ValidationSuiteManifest", **fields)


def truth(**changes):
    fields = {"suite_id": "offline", "suite_version": 1, "case_id": "case-1", "truth_version": 1,
              "input_digest": H,
              "expected": {"required_findings": [], "forbidden_findings": [],
                           "verdicts": ["discharged"], "statuses": ["complete"], "unknown_codes": []},
              "relations": ["publisher-before-release"],
              "review": {"status": "reviewed", "reviewer": "reviewer@example.invalid", "method": "manual",
                         "reviewed_on": "2026-09-18", "basis": "按 C11 内存模型人工审阅",
                         "basis_en": "Manually reviewed against the C11 memory model"}}
    fields.update(changes)
    return validation_document("TruthAnnotation", **fields)


def request(**changes):
    fields = {"suite": "suite.json", "suite_sha256": H, "case_ids": [], "run_modes": ["cold", "warm"],
              "requested_backends": [], "real_project_profile": None, "sampling_seed": 7,
              "budgets": deepcopy(expected_validation_protocol()["budgets"])}
    fields.update(changes)
    return validation_document("AnalysisValidationRequest", **fields)


def empty_metrics():
    zero = {"hit": 0, "total": 0, "value": None}
    return {"true_positive": 0, "false_positive": 0, "false_negative": 0,
            **{name: deepcopy(zero) for name in ("precision", "recall", "supported_precision",
                                                 "supported_recall", "exact_match", "abstention")}}


def report(**changes):
    layers = {name: {"status": "complete", "hit": 1, "total": 1} for name in
              ("request_input", "compile", "p1", "p2", "p3", "p4", "truth", "sampling", "performance", "backend")}
    fields = {"request_hash": H, "suite_digest": H, "layers": layers, "cases": [],
              "metrics": empty_metrics(), "performance": {}, "backend_dependencies": [],
              "diagnostics": [], "frontier": [], "safety": "not_established", "verdict": "matched", "exit_code": 0}
    fields.update(changes)
    return validation_document("AnalysisValidationReport", **fields)


def decisions():
    return validation_document("AnalysisExtensionDecision", request_hash=H, report_hash=H, entries=[{
        "capability": name, "state": "insufficient-evidence", "blocking_cases": 0, "blocking_tus": 0,
        "blocking_candidates": 0, "potential_coverage_gain": None, "cost": "unknown",
        "compatibility": "unknown", "detail": "证据不足", "detail_en": "Insufficient evidence",
        "suggestion": "人工确认", "suggestion_en": "Confirm manually", "human_confirmed": False,
    } for name in CAPABILITIES])


def test_protocol_roundtrip_and_strict_loading(tmp_path):
    protocol = expected_validation_protocol()
    assert protocol["kinds"] == dict.fromkeys(KINDS, 1)
    value = request()
    path = tmp_path / "request.json"
    assert write_validation_document(path, value, "AnalysisValidationRequest") == identity(value)
    assert read_validation_document(path, "AnalysisValidationRequest") == value
    path.write_text("[")
    with pytest.raises(AnalysisError, match="Invalid or missing JSON"):
        read_validation_document(path, "AnalysisValidationRequest")
    with pytest.raises(AnalysisError, match="Unknown validation contract"):
        validate_validation_document(value, "Future")
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_validation_document({**value, "schema_version": 2}, "AnalysisValidationRequest")
    with pytest.raises(AnalysisError, match="Additional properties"):
        validate_validation_document({**value, "future": True}, "AnalysisValidationRequest")
    bad = deepcopy(protocol); bad["runner_version"] = "future"
    bad_path = tmp_path / "protocol.json"; bad_path.write_text(json.dumps(bad))
    with pytest.raises(AnalysisError, match="does not match"):
        expected_validation_protocol(bad_path)
    with pytest.raises(AnalysisError):
        expected_validation_protocol(tmp_path / "missing.json")


def test_suite_profile_reference_roles_duplicates_and_order():
    assert suite()["kind"] == "ValidationSuiteManifest"
    invalid_profiles = [profile("z"), profile("a")]
    with pytest.raises(AnalysisError, match="deterministic"):
        suite(profiles=invalid_profiles, cases=[case(profile_id="z")])
    duplicate = [profile(), profile()]
    with pytest.raises(AnalysisError, match="Duplicate validation profile"):
        suite(profiles=duplicate)
    with pytest.raises(AnalysisError, match="Unknown profile"):
        suite(cases=[case(profile_id="missing")])
    cpp_bad = profile(); cpp_bad.update(language="c++")
    with pytest.raises(AnalysisError, match=r"C\+\+"):
        suite(profiles=[cpp_bad])
    c_bad = profile(); c_bad.update(standard="c++20")
    with pytest.raises(AnalysisError, match="C profile"):
        suite(profiles=[c_bad])
    wrong = case(); wrong["truth"] = entry("truth.json", "source")
    with pytest.raises(AnalysisError, match="truth role"):
        suite(cases=[wrong])
    wrong = case(); wrong["scope"] = entry("scope.json", "source")
    with pytest.raises(AnalysisError, match="roles"):
        suite(cases=[wrong])
    wrong = case(); wrong["sources"] *= 2
    with pytest.raises(AnalysisError, match="Duplicate source"):
        suite(cases=[wrong])


def test_truth_conflict_duplicates_and_diagnostics_pairing():
    assertion = {"code": "risk", "object": None, "thread_relation": None, "evidence_relation": None}
    conflict = deepcopy(truth())
    conflict["expected"]["required_findings"] = [assertion]
    conflict["expected"]["forbidden_findings"] = [assertion]
    with pytest.raises(AnalysisError, match="both required and forbidden"):
        validate_validation_document(conflict, "TruthAnnotation")
    duplicate = deepcopy(truth()); duplicate["expected"]["required_findings"] = [assertion, assertion]
    with pytest.raises(AnalysisError, match="Duplicate truth"):
        validate_validation_document(duplicate, "TruthAnnotation")
    assert diagnostic("x", "中文", "English", suggestion="建议", suggestion_en="Suggestion")["code"] == "x"
    with pytest.raises(AnalysisError, match="paired"):
        diagnostic("x", "中文", "English", suggestion="建议")


def test_report_metric_layer_and_exit_semantics():
    assert report()["exit_code"] == 0
    invalid = deepcopy(report()); invalid["metrics"]["exact_match"] = {"hit": 1, "total": 2, "value": 1.0}
    with pytest.raises(AnalysisError, match="Metric exact_match"):
        validate_validation_document(invalid, "AnalysisValidationReport")
    invalid = deepcopy(report()); invalid["layers"]["p1"].update(hit=2, total=1)
    with pytest.raises(AnalysisError, match="exceeds"):
        validate_validation_document(invalid, "AnalysisValidationReport")
    invalid = deepcopy(report()); invalid["layers"]["p1"].update(hit=0)
    with pytest.raises(AnalysisError, match="full denominator"):
        validate_validation_document(invalid, "AnalysisValidationReport")
    for code, verdict, partial, pattern in [
        (0, "mismatch", False, "Exit zero"), (3, "matched", False, "Exit three"),
        (2, "inconclusive", False, "Exit two"), (1, "matched", True, "Exit one")]:
        value = deepcopy(report()); value.update(exit_code=code, verdict=verdict)
        if partial:
            value["layers"]["p1"] = {"status": "partial", "hit": 0, "total": 1}
        with pytest.raises(AnalysisError, match=pattern):
            validate_validation_document(value, "AnalysisValidationReport")
    partial = deepcopy(report()); partial.update(exit_code=2, verdict="inconclusive")
    partial["layers"]["p1"] = {"status": "partial", "hit": 0, "total": 1}
    assert validate_validation_document(partial, "AnalysisValidationReport")["exit_code"] == 2


def test_decision_coverage_and_failed_report():
    assert [item["capability"] for item in decisions()["entries"]] == list(CAPABILITIES)
    invalid = deepcopy(decisions()); invalid["entries"][-1]["capability"] = CAPABILITIES[0]
    with pytest.raises(AnalysisError, match="Duplicate extension"):
        validate_validation_document(invalid, "AnalysisExtensionDecision")
    failed = failed_validation_report("bad", "错误", "Bad")
    assert failed["exit_code"] == 1 and failed["safety"] == "not_established"


def test_case_digest_uses_sources_compile_scope_but_not_truth(tmp_path):
    item = case()
    for source in [*item["sources"], item["compile_commands"], item["scope"], item["truth"]]:
        path = tmp_path / source["path"]; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source["role"])
        source["sha256"] = file_hash(path)
    first = case_input_digest(tmp_path, item)
    (tmp_path / item["truth"]["path"]).write_text("changed truth")
    assert case_input_digest(tmp_path, item) == first
    (tmp_path / item["sources"][0]["path"]).write_text("changed source")
    with pytest.raises(AnalysisError, match="changed"):
        case_input_digest(tmp_path, item)
