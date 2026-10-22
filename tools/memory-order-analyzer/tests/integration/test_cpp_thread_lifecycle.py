"""Offline A3 matrix: real Clang AST extraction plus adjudicated lifecycle projection."""

import json
import os
from pathlib import Path

from memory_order_analyzer.contracts import canonical, identity
from memory_order_analyzer.cpp_thread_contracts import read_cpp_thread_document
from memory_order_analyzer.cpp_thread_validation import compare_lifecycle_truth
from memory_order_analyzer.source_contracts import expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_worker import analyze_source


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/cpp-thread-lifecycle"
SOURCE_WORKER = str(Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker"))
                    .with_name("memory-order-source-worker"))


def _extract(tmp_path, case_id, standard, *, libcxx=False):
    suffix = ".c" if standard.startswith("c") and "+" not in standard else ".cpp"
    source = FIXTURES / "sources" / f"{case_id}{suffix}"
    driver = "clang++" if suffix == ".cpp" else "clang"
    arguments = [driver, f"-std={standard}", "-pthread", "-c", source.name]
    if libcxx:
        arguments.insert(1, "-stdlib=libc++")
    profile = build_profile(
        {"directory": str(source.parent), "file": source.name, "arguments": arguments},
        compiler_version="21.1.8")
    physical = identity({"profile": profile["profile_id"], "source": str(source)})
    request = source_document(
        "SourceSemanticRequest", profile=profile, physical_tu_id=physical,
        source_path=str(source), budgets=expected_source_protocol()["budgets"])
    path = tmp_path / f"{case_id}.json"
    path.write_text(canonical(request), encoding="utf-8")
    return analyze_source(request, SOURCE_WORKER, tmp_path)


def test_real_clang_c_and_cpp_source_semantics_are_independent(tmp_path):
    c11 = _extract(tmp_path, "c11-pthread-single", "c11")
    c17 = _extract(tmp_path, "c17-pthread-cross-tu", "c17")
    cpp17 = _extract(tmp_path, "cpp17-gnu-free-join", "c++17")
    cpp20 = _extract(tmp_path, "cpp20-libcxx-member-move", "c++20", libcxx=True)
    for facts in (c11, c17):
        kinds = {item["kind"] for item in facts["relations"]}
        assert {"pthread_create", "pthread_join"} <= kinds
        assert not any(kind.startswith("cpp-thread-") for kind in kinds)
        assert not any("std::" in item.get("canonical_type", "") for item in facts["nodes"])
    assert {"cpp-thread-construct", "cpp-thread-join", "cpp-thread-callback"} <= {
        item["kind"] for item in cpp17["relations"]}
    assert {"cpp-thread-construct", "cpp-thread-move-construct", "cpp-thread-join"} <= {
        item["kind"] for item in cpp20["relations"]}


def test_checked_in_truth_is_exact_and_keeps_language_denominators_separate():
    suite = read_cpp_thread_document(FIXTURES / "validation-suite.json", "CppThreadValidationSuite")
    truth = read_cpp_thread_document(FIXTURES / "validation-truth.json", "CppThreadValidationTruth")
    expected = read_cpp_thread_document(FIXTURES / "validation-report.json", "CppThreadValidationReport")
    actual = json.loads((FIXTURES / "validation-actual.json").read_text(encoding="utf-8"))["cases"]
    report = compare_lifecycle_truth(suite, truth, actual)
    assert report == expected
    assert report["metrics"]["exact"] == 8 and report["metrics"]["fp"] == report["metrics"]["fn"] == 0
    assert report["metrics"]["abstention"] == 3
    assert {name: value["planned"] for name, value in report["languages"].items()} == {
        "c11": 1, "c17": 1, "c++17": 3, "c++20": 3}
    assert all(value["failed"] == 0 for value in report["languages"].values())
