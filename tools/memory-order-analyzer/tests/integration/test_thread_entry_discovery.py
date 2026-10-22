"""Real Clang source/BC thread-entry checks plus the adjudicated four-language matrix."""

from copy import deepcopy
import json
import os
from pathlib import Path

from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document, identity
from memory_order_analyzer.source_contracts import expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_worker import analyze_source
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document
from test_offline import collect, WORKER


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/thread-entry-discovery"
SOURCE_WORKER = str(Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker"))
                    .with_name("memory-order-source-worker"))


def extract_source(tmp_path, source_name, standard):
    source = FIXTURES / "sources" / source_name
    driver = "clang++" if source.suffix == ".cpp" else "clang"
    profile = build_profile(
        {"directory": str(source.parent), "file": source.name,
         "arguments": [driver, f"-std={standard}", "-pthread", "-c", source.name]},
        compiler_version="21.1.8")
    request = source_document(
        "SourceSemanticRequest", profile=profile,
        physical_tu_id=identity({"source": source_name, "profile": profile["profile_id"]}),
        source_path=str(source), budgets=expected_source_protocol()["budgets"])
    return analyze_source(request, SOURCE_WORKER, tmp_path)


def test_real_clang_four_language_thread_entry_semantics(tmp_path):
    c11 = extract_source(tmp_path, "c11-thrd.c", "c11")
    c17 = extract_source(tmp_path, "c17-pthread-no-debug.c", "c17")
    cpp17 = extract_source(tmp_path, "cpp17-async.cpp", "c++17")
    cpp20 = extract_source(tmp_path, "cpp20-jthread.cpp", "c++20")
    negative = extract_source(tmp_path, "cpp20-negative.cpp", "c++20")
    assert {"thrd_create", "thrd-callback"} <= {item["kind"] for item in c11["relations"]}
    assert {"pthread_create", "callback"} <= {item["kind"] for item in c17["relations"]}
    assert {item["reason"] for item in cpp17["relations"] if item["kind"] == "cpp-async-call"} == {"async", "deferred"}
    assert sum(item["kind"] == "cpp-jthread-construct" for item in cpp20["relations"]) == 2
    negative_kinds = [item["kind"] for item in negative["relations"]]
    assert negative_kinds.count("unsupported-thread-api") == 2
    assert {"cpp-thread-move-construct", "cpp-thread-factory-return"} <= set(negative_kinds)


def test_real_no_debug_c11_thrd_create_ir_callback(tmp_path):
    source = (FIXTURES / "sources/c11-thrd.c").read_text(encoding="utf-8")
    report, artifacts, modules, _ = collect(tmp_path, {"main.c": source}, "clang", "c11",
                                             flags=("-pthread", "-g0"))
    assert report["build_status"] == "complete" and len(artifacts) == 1
    key = next(iter(artifacts))
    main = next(item for item in modules[key]["functions"] if item["name"] == "main")
    scope = document("ScopeManifest", target_id="thread-entry-thrd", members=[key],
                     evidence="compile-only no-debug thrd_create", closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(canonical(scope), encoding="utf-8")
    request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": main["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=deepcopy(expected_thread_protocol()["budgets"]))
    request_path = tmp_path / "thread-request.json"
    request_path.write_text(canonical(request), encoding="utf-8")
    output = tmp_path / "thread-output"
    cli.main(["model-threads", "--request", str(request_path), "--artifact-store", str(tmp_path / "out"),
              "--output", str(output), "--worker", WORKER])
    local = json.loads((output / f"thread-local/{key}.json").read_text(encoding="utf-8"))
    call = next(item for item in local["calls"] if item["symbol"] == "thrd_create")
    assert call["status"] == "candidate" and len(call["callback_targets"]) == 1
    assert modules[key]["source_mapping"] in {"unavailable", "partial"}


def test_checked_in_truth_provenance_and_language_denominators():
    suite = json.loads((FIXTURES / "validation-suite.json").read_text(encoding="utf-8"))
    truth = json.loads((FIXTURES / "validation-truth.json").read_text(encoding="utf-8"))
    actual = json.loads((FIXTURES / "validation-actual.json").read_text(encoding="utf-8"))
    report = json.loads((FIXTURES / "validation-report.json").read_text(encoding="utf-8"))
    provenance = json.loads((FIXTURES / "provenance.json").read_text(encoding="utf-8"))
    inventory = json.loads((FIXTURES / "case-inventory.json").read_text(encoding="utf-8"))
    assert suite["suite_version"] == truth["suite_version"] == actual["suite_version"]
    assert truth["cases"] == actual["cases"]
    assert {item["standard"] for item in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    assert {item["mode"] for item in suite["cases"]} == {"AST+IR", "IR-only/no-debug", "AST-only"}
    assert report["metrics"] == {"planned": 8, "completed": 8, "failed": 0, "exact": 8,
                                  "tp": 8, "fp": 0, "fn": 0, "abstention": 3, "sites": 12,
                                  "dual-exact": 10, "ir-exact": 1, "source-candidate": 1, "frontier": 3}
    assert {name: value["planned"] for name, value in report["languages"].items()} == {
        "c11": 2, "c17": 2, "c++17": 2, "c++20": 2}
    for case in suite["cases"]:
        assert (FIXTURES / case["source"]).is_file()
    for item in provenance["cases"]:
        assert len(item["sha256"]) == 64
        for fixture in item["fixture"].split(";"):
            assert (FIXTURES / fixture).is_file()
    assert {item["capability"] for item in inventory["cases"]} >= {
        "c11-thrd-create", "c17-cross-tu-wrapper", "cpp17-member-functor-async",
        "cpp20-jthread-stop-token", "async-policy-matrix", "framework-unsupported",
        "source-ir-callback-conflict", "open-scope-frontier", "budget-and-cache", "windows-excluded"}
    for item in inventory["cases"]:
        for fixture in item["fixture"].split(";"):
            assert (FIXTURES / fixture).is_file()
    assert report["safety"] == "not_evaluated" and report["findings"] is None
