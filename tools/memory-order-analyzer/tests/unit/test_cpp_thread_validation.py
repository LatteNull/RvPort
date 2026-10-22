from copy import deepcopy

import pytest

from memory_order_analyzer.cpp_thread_contracts import cpp_thread_document
from memory_order_analyzer.cpp_thread_contracts import read_cpp_thread_document
from memory_order_analyzer.cpp_thread_validation import compare_lifecycle_truth


def suite():
    cases = [
        {"id": "c11", "language": "c", "standard": "c11", "vendor": None,
         "request": "c11.json", "expected_status": "complete"},
        {"id": "c17", "language": "c", "standard": "c17", "vendor": None,
         "request": "c17.json", "expected_status": "complete"},
        {"id": "gnu17", "language": "c++", "standard": "c++17", "vendor": "libstdc++",
         "request": "gnu17.json", "expected_status": "complete"},
        {"id": "llvm20", "language": "c++", "standard": "c++20", "vendor": "libc++",
         "request": "llvm20.json", "expected_status": "partial"},
    ]
    return cpp_thread_document("CppThreadValidationSuite", suite_version="a3-v1",
                               cases=cases, semantic_digest=None)


def truth():
    cases = [{"case_id": name, "callables": [], "instances": [], "relations": [],
              "unknown": ["missing-result"] if name == "llvm20" else []}
             for name in ("c11", "c17", "gnu17", "llvm20")]
    return cpp_thread_document("CppThreadValidationTruth", suite_version="a3-v1",
                               cases=cases, semantic_digest=None)


def test_validation_reports_four_denominators_and_abstention():
    empty = {"status": "complete", "contexts": [], "instances": [], "relations": [],
             "gaps": [], "frontier": []}
    actuals = {name: deepcopy(empty) for name in ("c11", "c17", "gnu17")}
    report = compare_lifecycle_truth(suite(), truth(), actuals)
    assert report["status"] == "complete" and report["metrics"]["exact"] == 4
    assert report["metrics"]["abstention"] == 1
    assert all(report["languages"][name]["planned"] == 1
               for name in ("c11", "c17", "c++17", "c++20"))


def test_validation_mismatch_and_denominator_errors_are_explicit():
    empty = {"status": "complete", "contexts": [], "instances": [], "relations": [],
             "gaps": [], "frontier": []}
    actuals = {name: deepcopy(empty) for name in ("c11", "c17", "gnu17", "llvm20")}
    report = compare_lifecycle_truth(suite(), truth(), actuals)
    assert report["status"] == "partial" and report["metrics"]["fn"] == 1
    changed = truth(); changed["suite_version"] = "other"
    from memory_order_analyzer.cpp_thread_contracts import semantic_digest
    changed["semantic_digest"] = semantic_digest(changed)
    with pytest.raises(ValueError, match="versions differ"):
        compare_lifecycle_truth(suite(), changed, actuals)
    missing = truth(); missing["cases"][-1]["case_id"] = "zzz"; missing["semantic_digest"] = semantic_digest(missing)
    with pytest.raises(ValueError, match="denominator differs"):
        compare_lifecycle_truth(suite(), missing, actuals)


def test_checked_in_four_language_truth_and_sources_are_complete():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "tests/fixtures/cpp-thread-lifecycle"
    checked_suite = read_cpp_thread_document(root / "validation-suite.json", "CppThreadValidationSuite")
    checked_truth = read_cpp_thread_document(root / "validation-truth.json", "CppThreadValidationTruth")
    expected_report = read_cpp_thread_document(root / "validation-report.json", "CppThreadValidationReport")
    actuals = json.loads((root / "validation-actual.json").read_text(encoding="utf-8"))["cases"]
    assert compare_lifecycle_truth(checked_suite, checked_truth, actuals) == expected_report
    assert expected_report["metrics"] == {
        "expected": 16, "actual": 16, "exact": 8, "fp": 0, "fn": 0,
        "unknown": 3, "abstention": 3,
    }
    for case in checked_suite["cases"]:
        matches = list((root / "sources").glob(f"{case['id']}.*"))
        assert matches, case["id"]
