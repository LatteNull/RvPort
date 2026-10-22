import json
from pathlib import Path

import pytest

from memory_order_analyzer.concurrent_access_validation import (
    collect_scale_metrics, compare_truth, main, run_validation, validate_fixture_provenance,
)
from memory_order_analyzer.contracts import AnalysisError, file_hash


def test_fixture_provenance_rejects_escape_digest_duplicates_and_missing_rewrite(tmp_path):
    source = tmp_path / "case.c"; source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    item = {"case_id": "case", "path": source.name, "sha256": file_hash(source),
            "imported_from": None, "rewrite_reason": None}
    assert validate_fixture_provenance(tmp_path, {"fixtures": [item]})
    for changed in (
        {**item, "sha256": "0" * 64},
        {**item, "path": "../case.c"},
        {**item, "imported_from": "archive/sample.c", "rewrite_reason": None},
    ):
        with pytest.raises(AnalysisError, match="fixture"):
            validate_fixture_provenance(tmp_path, {"fixtures": [changed]})
    with pytest.raises(AnalysisError, match="unique"):
        validate_fixture_provenance(tmp_path, {"fixtures": [item, item]})


def test_truth_report_keeps_four_language_denominators_and_mismatches():
    standards = ("c11", "c17", "c++17", "c++20")
    suite = {"cases": [{"case_id": name, "standard": name} for name in standards]}
    truth = {"cases": [{"case_id": name, "candidate_pairs": [f"{name}-pair"],
                        "protected": [], "excluded": [],
                        "status": "failed" if name == "c++20" else "complete"} for name in standards]}
    actuals = {
        "c11": {"status": "complete", "candidate_pairs": ["c11-pair"],
                "protected": [], "excluded": [], "frontier": []},
        "c17": {"status": "partial", "candidate_pairs": [],
                "protected": [], "excluded": [], "frontier": ["unknown"]},
        "c++17": {"status": "complete", "candidate_pairs": ["wrong"],
                  "protected": [], "excluded": [], "frontier": []},
        "c++20": {"status": "failed", "candidate_pairs": [],
                  "protected": [], "excluded": [], "frontier": []},
    }
    result = compare_truth(suite, truth, actuals)
    assert result["status"] == "partial" and result["safety"] == "not_evaluated"
    assert result["metrics"] == {"planned": 4, "completed": 3, "failed": 1, "tp": 1,
                                 "fp": 1, "fn": 2, "abstention": 2,
                                 "protected": 0, "excluded": 0, "frontier": 1}
    assert all(result["languages"][name]["planned"] == 1 for name in standards)
    assert {item["case_id"] for item in result["diagnostics"]} == {"c17", "c++17"}


def test_truth_zero_denominator_and_missing_actual_are_explicit():
    empty = compare_truth({"cases": []}, {"cases": []}, {})
    assert empty["status"] == "complete" and empty["metrics"]["planned"] == 0
    suite = {"cases": [{"case_id": "missing", "standard": "c11"}]}
    truth = {"cases": [{"case_id": "missing", "candidate_pairs": []}]}
    result = compare_truth(suite, truth, {})
    assert result["status"] == "partial" and result["metrics"]["failed"] == 1


def test_checked_in_four_language_corpus_is_exact_and_cli_writes_report(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1] / "fixtures/concurrent-access-candidate"
    report = run_validation(root, tmp_path / "report.json")
    assert report["status"] == "complete" and not report["diagnostics"]
    assert report["metrics"] == {"planned": 13, "completed": 12, "failed": 1,
                                 "tp": 8, "fp": 0, "fn": 0, "abstention": 3,
                                 "protected": 3, "excluded": 2, "frontier": 2}
    assert {name: values["planned"] for name, values in report["languages"].items()} == {
        "c11": 3, "c17": 3, "c++17": 4, "c++20": 3}
    assert report["scale"]["accesses"] == report["scale"]["buckets"] == 1000
    assert report["scale"]["alias_comparisons"] == report["scale"]["candidates"] == 0
    assert report["scale"]["peak_bytes"] > 0 and report["scale"]["output_bytes"] > 0
    assert main(["--fixture-root", str(root), "--output", str(tmp_path / "second.json")]) == 0
    assert json.loads(capsys.readouterr().out)["findings"] is None
    assert main(["--fixture-root", str(root), "--output", str(tmp_path / "second.json")]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "output_exists"


def test_scale_metrics_are_bounded_and_do_not_form_global_cartesian_pairs():
    small, large = collect_scale_metrics(20), collect_scale_metrics(200)
    assert small["buckets"] == 20 and large["buckets"] == 200
    assert small["alias_comparisons"] == large["alias_comparisons"] == 0
    assert large["output_bytes"] < 4096 and large["peak_bytes"] < 8 * 1024 * 1024
