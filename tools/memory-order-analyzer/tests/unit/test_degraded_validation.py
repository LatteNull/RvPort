from copy import deepcopy
import json
from pathlib import Path

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.degraded_contracts import degraded_document
from memory_order_analyzer.degraded_validation import validate_degraded_suite


def suite_truth():
    cases = []
    for standard, language in (("c11", "c"), ("c17", "c"), ("c++17", "c++"), ("c++20", "c++")):
        cases.append({"id": standard, "language": language, "standard": standard,
                      "expected_mode": "ast-only", "expected_formal": "unknown",
                      "eligible": True, "input_digest": "a" * 64})
    suite = degraded_document("DegradedValidationSuite", suite_id="degraded-v1", suite_version=1,
                              cases=sorted(cases, key=lambda item: item["id"]), semantic_digest=None)
    truth_cases = [{"case_id": item["id"], "mode": item["expected_mode"],
                    "formal": item["expected_formal"]} for item in suite["cases"]]
    truth = degraded_document("DegradedValidationTruth", suite_id=suite["suite_id"],
                              suite_digest=identity(suite), cases=truth_cases,
                              review={"status": "reviewed", "method": "manual"}, semantic_digest=None)
    return suite, truth


def test_validation_reports_four_independent_profiles_and_zero_metrics():
    suite, truth = suite_truth()
    observations = {item["id"]: {"mode": "ast-only", "formal": "unknown",
                    "source_candidates": 1, "formal_candidates": 0} for item in suite["cases"]}
    report = validate_degraded_suite(suite, truth, observations, performance={"cold_seconds": 1})
    assert report["status"] == "complete" and set(report["profiles"]) == {"c11", "c17", "c++17", "c++20"}
    assert all(value["exact_match"]["value"] == 1 for value in report["profiles"].values())
    assert report["aggregate"]["precision"]["value"] is None
    partial = validate_degraded_suite(suite, truth, {"c11": observations["c11"]})
    assert partial["status"] == "partial" and partial["diagnostics"][0]["code"] == "profile-incomplete"


def test_validation_rejects_stale_duplicate_and_invalid_truth():
    suite, truth = suite_truth()
    stale = deepcopy(truth); stale["suite_digest"] = "b" * 64; stale["semantic_digest"] = None
    stale["semantic_digest"] = __import__("memory_order_analyzer.degraded_contracts", fromlist=["semantic_digest"]).semantic_digest(stale)
    with pytest.raises(AnalysisError, match="does not match"):
        validate_degraded_suite(suite, stale, {})
    invalid = deepcopy(truth); invalid["cases"][0]["formal"] = "maybe"
    with pytest.raises(AnalysisError, match="expectations"):
        validate_degraded_suite(suite, invalid, {})
    absent = deepcopy(suite); absent["cases"] = absent["cases"][1:]
    absent["semantic_digest"] = None
    from memory_order_analyzer.degraded_contracts import semantic_digest
    absent["semantic_digest"] = semantic_digest(absent)
    with pytest.raises(AnalysisError, match="four"):
        __import__("memory_order_analyzer.degraded_contracts", fromlist=["validate_degraded_document"]).validate_degraded_document(absent, absent["kind"])


def test_validation_counts_tp_fp_fn_abstention_and_ineligible_cases():
    suite, truth = suite_truth()
    expectations = {
        "c11": ("risk", "risk"), "c17": ("no-risk", "risk"),
        "c++17": ("risk", "unknown"), "c++20": ("no-risk", "no-risk"),
    }
    for item in truth["cases"]:
        item["formal"] = expectations[item["case_id"]][0]
    observations = {case_id: {"mode": "ast-only", "formal": values[1],
                    "source_candidates": 2, "formal_candidates": 1}
                    for case_id, values in expectations.items()}
    report = validate_degraded_suite(suite, truth, observations)
    aggregate = report["aggregate"]
    assert (aggregate["true_positive"], aggregate["false_positive"], aggregate["false_negative"]) == (1, 1, 1)
    assert aggregate["abstention"]["hit"] == 1
    suite["cases"][0]["eligible"] = False
    truth["suite_digest"] = identity(suite)
    report = validate_degraded_suite(suite, truth, observations)
    assert report["aggregate"]["eligible"] == 3


def test_validation_rejects_truth_denominator_mismatch():
    suite, truth = suite_truth()
    truth["cases"] = truth["cases"][:-1]
    with pytest.raises(AnalysisError, match="uniquely match"):
        validate_degraded_suite(suite, truth, {})


def test_versioned_offline_truth_and_report_are_reproducible():
    root = Path(__file__).parents[1] / "fixtures/degraded-source-analysis"
    suite = json.loads((root / "validation-suite.json").read_text(encoding="utf-8"))
    truth = json.loads((root / "validation-truth.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "validation-report.json").read_text(encoding="utf-8"))
    observations = {
        case["id"]: {
            "mode": case["expected_mode"],
            "formal": case["expected_formal"],
            "source_candidates": 1 if case["expected_mode"] == "ast-only" else 0,
            "formal_candidates": 0,
        }
        for case in suite["cases"]
    }
    actual = validate_degraded_suite(
        suite, truth, observations, performance=expected["performance"])
    assert actual == expected
    assert all(actual["profiles"][profile]["planned"] == 2
               for profile in ("c11", "c17", "c++17", "c++20"))
