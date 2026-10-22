import json
from copy import deepcopy
from pathlib import Path

import pytest

from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.source_contracts import read_source_document, semantic_digest, validate_source_document
from memory_order_analyzer.source_validation import (
    LAYERS, build_ast_extension_decision, build_ast_validation_report,
)


ROOT = Path(__file__).parents[1] / "fixtures" / "validation" / "ast-ir-v2"


def inputs():
    return (read_source_document(ROOT / "suite.json", "AstIrValidationSuite"),
            read_source_document(ROOT / "truth.json", "AstIrValidationTruth"))


def observations(suite, truth):
    expected = {item["case_id"]: item for item in truth["cases"]}
    values = []
    for mode in ("ir_only", "ast_assisted"):
        for case in suite["cases"]:
            truth_case = expected[case["id"]]
            layers = {name: {"status": "complete", "hit": 1, "total": 1} for name in LAYERS}
            values.append({"mode": mode, "case_id": case["id"], "status": "complete",
                           "verdict": truth_case["verdict"], "matched": True, "abstained": False,
                           "supported": True, "layers": layers})
    return values


def test_ast_validation_suite_is_versioned_reviewed_and_covers_matrix():
    suite, truth = inputs()
    assert suite["suite_version"] == truth["suite_version"] == 2
    assert truth["review"]["status"] == "reviewed"
    assert {item["standard"] for item in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    assert {item["compiler"] for item in suite["cases"]} == {"gcc", "clang"}
    assert {item["layout"] for item in suite["cases"]} == {"single-tu", "three-tu"}
    features = {feature for item in suite["cases"] for feature in item["features"]}
    assert {"macro", "no-debug", "odr", "weak", "comdat", "tls", "path-map",
            "cross-tu-wrapper", "pthread-handle", "budget"} <= features


def test_ast_validation_report_compares_modes_layers_and_zero_denominators():
    suite, truth = inputs()
    values = observations(suite, truth)
    ir_case = next(item for item in values if item["mode"] == "ir_only" and item["case_id"] == "c11-risk-multi")
    ir_case.update(verdict="unknown", matched=False, abstained=True, supported=False,
                   true_positive=0, false_positive=0, false_negative=2)
    report = build_ast_validation_report(suite, truth, values,
                                         performance={"cold_wall_seconds": 2.0, "warm_wall_seconds": 1.0,
                                                      "cache_hits": 4, "cache_misses": 4})
    assert report["modes"]["ir_only"]["false_negative"] == 2
    assert report["modes"]["ir_only"]["supported_precision"]["value"] == 1.0
    assert report["delta"]["new_hits"] == ["c11-risk-multi"]
    assert report["layers"]["expression_binding"]["counts"]["ratio"] == 1.0
    assert report["safety"] == "not_established"


def test_ast_validation_preserves_partial_denominators_and_rejects_stale_truth():
    suite, truth = inputs()
    values = observations(suite, truth)
    values = [item for item in values if not (
        item["mode"] == "ast_assisted" and item["case_id"] == suite["cases"][-1]["id"])]
    report = build_ast_validation_report(suite, truth, values)
    assert report["status"] == "partial"
    assert report["frontier"][0]["detail_en"] == "Validation denominator is incomplete"

    stale = deepcopy(truth)
    stale["suite_digest"] = "0" * 64
    stale["semantic_digest"] = semantic_digest(stale)
    validate_source_document(stale, "AstIrValidationTruth")
    with pytest.raises(AnalysisError, match="immutable suite"):
        build_ast_validation_report(suite, stale, values)


def test_ast_validation_rejects_duplicate_unknown_and_layer_schema():
    suite, truth = inputs()
    values = observations(suite, truth)
    with pytest.raises(AnalysisError, match="duplicate"):
        build_ast_validation_report(suite, truth, [*values, deepcopy(values[0])])
    bad = deepcopy(values[0]); bad["mode"] = "other"
    with pytest.raises(AnalysisError, match="outside"):
        build_ast_validation_report(suite, truth, [bad])
    document = build_ast_validation_report(suite, truth, values)
    document["layers"].pop("overlay")
    document["semantic_digest"] = semantic_digest(document)
    with pytest.raises(AnalysisError, match="layers"):
        validate_source_document(document, "AstAssistedValidationReport")


def test_ast_extension_decision_quantifies_remaining_frontiers():
    suite, truth = inputs()
    values = observations(suite, truth)
    for item in values:
        if item["mode"] == "ast_assisted" and item["case_id"] in {
                "c11-risk-multi", "cpp17-unknown-multi", "cpp20-risk-multi"}:
            item.update(verdict="unknown", matched=False, abstained=True, supported=False)
    report = build_ast_validation_report(suite, truth, values)
    decision = build_ast_extension_decision(suite, report)
    entries = {item["capability"]: item for item in decision["entries"]}
    assert entries["std-thread"]["state"] == "insufficient-evidence"
    assert entries["pointer-analysis"]["blocking_cases"] == 3
    assert entries["b1-cmake-scope"]["blocking_tus"] >= 9
    assert "AST added" in entries["fence-rmw"]["detail_en"]
    assert all(not item["human_confirmed"] for item in entries.values())
