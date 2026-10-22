"""Offline real-Clang A2 checks; fixture programs are parsed only and never linked or run."""

import json
import os
from pathlib import Path

from memory_order_analyzer.analyze_degraded_source import analyze_degraded_source
from memory_order_analyzer.contracts import canonical, identity
from memory_order_analyzer.degraded_contracts import degraded_document, expected_degraded_protocol, input_hash
from memory_order_analyzer.source_contracts import expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/degraded-source-analysis"
SOURCE_WORKER = str(Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker")).with_name("memory-order-source-worker"))


def make_request(tmp_path, cases):
    planned = []
    for standard, compiler, source in cases:
        language = "c++" if "+" in standard else "c"
        driver = "g++" if language == "c++" and compiler == "gcc" else "gcc" if compiler == "gcc" else "clang++" if language == "c++" else "clang"
        profile = build_profile(
            {"directory": str(source.parent), "file": source.name,
             "arguments": [driver, f"-std={standard}", "-pthread", "-c", source.name]},
            compiler_version="fixture")
        physical = identity({"profile": profile["profile_id"], "source": str(source)})
        request = source_document(
            "SourceSemanticRequest", profile=profile, physical_tu_id=physical,
            source_path=str(source.resolve()), budgets=expected_source_protocol()["budgets"])
        planned.append((physical, request))
    references = []
    request_dir = tmp_path / "requests"; request_dir.mkdir()
    for physical, request in sorted(planned):
        path = request_dir / f"source-{physical}.json"
        path.write_text(canonical(request), encoding="utf-8")
        references.append(input_hash(path))
    value = degraded_document(
        "DegradedSourceAnalysisRequest", scope_id="degraded-real-source-matrix",
        source_requests=references, ir_requests=[], module_facts=[], declared_failures=[],
        products={"thread_graph": None, "publication_graph": None, "publication_report": None},
        budgets=expected_degraded_protocol()["budgets"])
    path = tmp_path / "request.json"; path.write_text(canonical(value), encoding="utf-8")
    return path


def test_real_c11_c17_cpp17_cpp20_ast_only_matrix_is_source_only(tmp_path):
    request = make_request(tmp_path, [
        ("c11", "clang", FIXTURES / "c11/single.c"),
        ("c17", "gcc", FIXTURES / "c17/single.c"),
        ("c++17", "gcc", FIXTURES / "cpp17/archived_safe_03_pthread_mutex.cpp"),
        ("c++20", "clang", FIXTURES / "cpp20/single.cpp"),
    ])
    report = analyze_degraded_source(request, tmp_path / "store", tmp_path / "output",
                                     SOURCE_WORKER, SOURCE_WORKER)
    assert report["mode"] == "ast-only" and report["exit_code"] == 2
    assert report["mode_counts"] == {"ast-ir": 0, "ir-only": 0, "ast-only": 4, "failed": 0}
    facts = [json.loads(path.read_text()) for path in (tmp_path / "output/source-facts").glob("*.json")]
    assert {item["status"] for item in facts} == {"complete"}
    c_facts = [item for item in facts if any(node.get("language_linkage") == "c" for node in item["nodes"])]
    assert len(c_facts) == 2
    assert not any("std::" in node.get("canonical_type", "") for item in c_facts for node in item["nodes"])
    candidates = [json.loads(path.read_text()) for path in (tmp_path / "output/source-candidates").glob("*.json")]
    assert candidates and all(item["verdict"] == "unknown" and item["evidence_level"] == "source-only" for item in candidates)
    assert any(item["shape"] == "unknown-raii" for item in candidates)
    assert not list(tmp_path.rglob("*.o")) and not list(tmp_path.rglob("*.bc"))


def test_real_missing_generated_header_is_failed_not_recovery_evidence(tmp_path):
    request = make_request(tmp_path, [
        ("c11", "clang", FIXTURES / "c11/missing_generated.c"),
        ("c17", "gcc", FIXTURES / "c17/missing_generated.c"),
        ("c++17", "gcc", FIXTURES / "cpp17/missing_generated.cpp"),
        ("c++20", "clang", FIXTURES / "cpp20/missing_generated.cpp"),
    ])
    report = analyze_degraded_source(request, tmp_path / "store", tmp_path / "output",
                                     SOURCE_WORKER, SOURCE_WORKER)
    assert report["mode"] == "failed" and report["exit_code"] == 1
    assert report["mode_counts"] == {"ast-ir": 0, "ir-only": 0, "ast-only": 0, "failed": 4}
    assert not report["source_candidates"]
    assert report["diagnostics"] and report["safety"] == "not-established"


def test_cross_tu_fixture_inventory_has_independent_c_and_cpp_inputs():
    for profile, suffix in (("c11", ".c"), ("c17", ".c"), ("cpp17", ".cpp"), ("cpp20", ".cpp")):
        files = list((FIXTURES / profile / "cross").glob(f"*{suffix}"))
        assert len(files) >= 3
    inventory = json.loads((FIXTURES / "sample-inventory.json").read_text())
    assert {item["classification"] for item in inventory["eligible"]} == {
        "unknown-raii-regression", "direct-pthread-risk-regression"}
    assert any(item["class"] == "windows-msvc" for item in inventory["excluded"])
