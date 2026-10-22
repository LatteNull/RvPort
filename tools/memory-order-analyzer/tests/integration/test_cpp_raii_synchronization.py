"""Offline A4 matrix: real Clang facts, verified profiles, and adjudicated truth."""

import json
import os
from pathlib import Path
import subprocess

from memory_order_analyzer.contracts import canonical, identity
from memory_order_analyzer.cpp_raii_contracts import read_cpp_raii_document
from memory_order_analyzer.cpp_raii_validation import compare_synchronization_truth
from memory_order_analyzer.source_contracts import expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_worker import analyze_source


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/cpp-raii-synchronization"
SOURCE_WORKER = str(Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker"))
                    .with_name("memory-order-source-worker"))


def _extract(tmp_path, relative, standard, *, libcxx=False):
    source = FIXTURES / relative
    driver = "clang++" if source.suffix == ".cpp" else "clang"
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
    request_path = tmp_path / f"{physical}.json"
    request_path.write_text(canonical(request), encoding="utf-8")
    return analyze_source(request, SOURCE_WORKER, tmp_path)


def test_real_c_and_cpp_mutex_source_facts_remain_language_independent(tmp_path):
    c11 = _extract(tmp_path, "c11/direct_same.c", "c11")
    c17 = _extract(tmp_path, "c17/direct_same.c", "c17")
    cpp17 = _extract(tmp_path, "cpp17/lock_guard.cpp", "c++17")
    cpp20 = _extract(tmp_path, "cpp20/lock_guard.cpp", "c++20", libcxx=True)
    for facts in (c11, c17):
        kinds = {item["kind"] for item in facts["relations"]}
        assert {"pthread_mutex_lock", "pthread_mutex_unlock"} <= kinds
        assert not any(kind.startswith("cpp-raii-") for kind in kinds)
    for facts in (cpp17, cpp20):
        kinds = {item["kind"] for item in facts["relations"]}
        assert {"cpp-raii-mutex-object", "cpp-raii-owner-object",
                "cpp-raii-owner-construct", "cpp-raii-owner-destruct",
                "cpp-raii-mutex-argument"} <= kinds


def test_locked_vendor_profiles_match_actual_compile_only_ir(tmp_path):
    probe = FIXTURES / "profile_probe.cpp"
    configurations = [
        ("libstdcpp-clang21-cpp17-x86_64.json", "c++17", False,
         "_ZNSt5mutex4lockEv", "_ZNSt5mutex6unlockEv"),
        ("libstdcpp-clang21-cpp20-x86_64.json", "c++20", False,
         "_ZNSt5mutex4lockEv", "_ZNSt5mutex6unlockEv"),
        ("libcxx21-clang21-cpp20-x86_64.json", "c++20", True,
         "_ZNSt3__15mutex4lockEv", "_ZNSt3__15mutex6unlockEv"),
    ]
    for filename, standard, libcxx, lock, unlock in configurations:
        registered = read_cpp_raii_document(
            ROOT / "cpp-raii-profiles" / filename, "CppRaiiSynchronizationProfile")
        output = tmp_path / f"{filename}.ll"
        command = ["clang++", f"-std={standard}", "-O0", "-g", "-S", "-emit-llvm",
                   str(probe), "-o", str(output)]
        if libcxx:
            command.insert(1, "-stdlib=libc++")
        subprocess.run(command, check=True)
        llvm_ir = output.read_text(encoding="utf-8")
        assert lock in llvm_ir and unlock in llvm_ir
        assert {item["symbol"] for item in registered["wrapper_signatures"]} == {lock, unlock}
        assert registered["lifecycle_profile_id"]


def test_checked_in_truth_is_exact_and_reports_each_language_separately():
    suite = read_cpp_raii_document(FIXTURES / "validation-suite.json", "CppRaiiValidationSuite")
    truth = read_cpp_raii_document(FIXTURES / "validation-truth.json", "CppRaiiValidationTruth")
    truth_by_id = {item["case_id"]: item for item in truth["cases"]}
    actuals = {}
    for case in suite["cases"]:
        expected = truth_by_id[case["id"]]
        mutexes = [{"id": item, "object_id": item} for item in expected["mutexes"]]
        owners = [{"id": item, "object_id": item} for item in expected["owners"]]
        regions = []
        for item in expected["regions"]:
            regions.append({"id": item, "owner_id": expected["owners"][0],
                            "thread_id": f"{case['id']}:thread"})
        proofs = []
        for item in expected["proofs"]:
            proof_kind, mutex_id = item.split(":", 1)
            proofs.append({"id": item, "proof_kind": proof_kind, "mutex_id": mutex_id})
        actuals[case["id"]] = {"status": "complete", "mutexes": mutexes, "owners": owners,
                               "held_regions": regions, "proofs": proofs, "gaps": [], "frontier": []}
    report = compare_synchronization_truth(suite, truth, actuals)
    assert report["status"] == "complete"
    assert report["metrics"]["exact"] == 8
    assert report["metrics"]["fp"] == report["metrics"]["fn"] == 0
    assert report["metrics"]["abstention"] == 0
    assert {name: value["planned"] for name, value in report["languages"].items()} == {
        "c11": 2, "c17": 2, "c++17": 2, "c++20": 2}
