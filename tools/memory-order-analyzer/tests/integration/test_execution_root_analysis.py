"""Real GCC/Clang-compatible C/C++ compile-only R1 matrix; target programs are never linked or run."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from test_offline import collect, WORKER
from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document, identity
from memory_order_analyzer.root_contracts import expected_root_protocol, root_document
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document


@pytest.mark.parametrize("language,standard,driver,suffix", [
    ("c", "c11", "clang", "c"), ("c", "c17", "clang", "c"),
    ("c++", "c++17", "clang++", "cpp"), ("c++", "c++20", "clang++", "cpp"),
])
def test_real_four_language_pthread_root_plan(language, standard, driver, suffix, tmp_path):
    null = "nullptr" if language == "c++" else "0"
    source = f"""
#include <pthread.h>
static void *worker(void *arg) {{ return arg; }}
int main() {{
  pthread_t thread;
  if (pthread_create(&thread, {null}, worker, {null}) != 0) return 1;
  return pthread_join(thread, {null});
}}
"""
    report, artifacts, modules, _ = collect(tmp_path, {f"main.{suffix}": source}, driver, standard,
                                             flags=("-pthread",))
    assert report["build_status"] == "complete" and len(artifacts) == 1
    key = next(iter(artifacts)); root = next(item for item in modules[key]["functions"] if item["name"] == "main")
    scope = document("ScopeManifest", target_id=f"r1-{standard}", members=[key],
                     evidence="R1 compile-only matrix", closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope), encoding="utf-8")
    thread_request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread.json"; thread_path.write_text(canonical(thread_request), encoding="utf-8")
    thread_output = tmp_path / "thread-output"
    cli.main(["model-threads", "--request", str(thread_path), "--artifact-store", str(tmp_path / "out"),
              "--output", str(thread_output), "--worker", WORKER])
    local = json.loads((thread_output / f"thread-local/{key}.json").read_text(encoding="utf-8"))
    local_path = tmp_path / f"out/r1-thread-local/{key}.json"; local_path.parent.mkdir()
    local_path.write_text(canonical(local), encoding="utf-8")
    module = modules[key]
    evidence = [
        {"kind": "ModuleFacts", "id": key, "digest": identity(module), "path": f"facts/{key}.json"},
        {"kind": "ThreadLocalFacts", "id": key, "digest": identity(local),
         "path": f"r1-thread-local/{key}.json"},
    ]
    request = root_document(
        "ExecutionRootDiscoveryRequest", scope_id=identity(scope), closed_scope=True, discover_main=True,
        members=[{"physical_tu_id": identity({"artifact": key, "standard": standard}),
                  "profile_id": identity({"driver": driver, "standard": standard}),
                  "language": language, "standard": standard, "evidence": evidence}],
        global_evidence=[], explicit_roots=[], budgets=deepcopy(expected_root_protocol()["budgets"]),
        semantic_digest=None)
    request_path = tmp_path / "root-request.json"; request_path.write_text(canonical(request), encoding="utf-8")
    root_output = tmp_path / "root-output"
    code = cli.main(["plan-execution-roots", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(root_output)])
    result = json.loads((root_output / "report.json").read_text(encoding="utf-8"))
    roots = json.loads((root_output / "execution-roots/index.json").read_text(encoding="utf-8"))
    assert code == result["exit_code"] == 0
    assert result["classification_counts"]["ir-exact"] == 1
    assert {item["kind"] for item in roots["roots"]} == {"main", "pthread"}
    assert result["safety"] == "not_evaluated" and result["findings"] is None
    assert not list(tmp_path.glob("*.o"))


def test_checked_in_fixture_truth_has_four_language_denominators():
    root = Path(__file__).resolve().parents[2] / "tests/fixtures/execution-root-analysis"
    suite = json.loads((root / "validation-suite.json").read_text(encoding="utf-8"))
    truth = json.loads((root / "validation-truth.json").read_text(encoding="utf-8"))
    actual = json.loads((root / "validation-actual.json").read_text(encoding="utf-8"))
    report = json.loads((root / "validation-report.json").read_text(encoding="utf-8"))
    assert suite["suite_version"] == truth["suite_version"] == "execution-root-r1-v1"
    assert {item["standard"] for item in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    assert [item["id"] for item in suite["cases"]] == [item["case_id"] for item in truth["cases"]]
    assert [item["case_id"] for item in actual["cases"]] == [item["case_id"] for item in truth["cases"]]
    expected = {item["case_id"]: item for item in truth["cases"]}
    exact = sum({"case_id": item["case_id"], "root_kinds": item["root_kinds"],
                 "classifications": item["classifications"]} == expected[item["case_id"]]
                for item in actual["cases"])
    assert exact == report["metrics"]["exact"] == 8
    assert {name: report["metrics"][name] for name in
            ("planned", "completed", "exact", "fp", "fn", "abstention")} == {
                "planned": 8, "completed": 8, "exact": 8,
                "fp": 0, "fn": 0, "abstention": 2}
    assert {name: report["metrics"][name] for name in
            ("source_candidates", "ir_candidates", "aligned_candidates",
             "formal_roots", "candidate_roots", "frontier_items")} == {
                "source_candidates": 4, "ir_candidates": 6, "aligned_candidates": 3,
                "formal_roots": 14, "candidate_roots": 1, "frontier_items": 2}
    assert report["metrics"]["classifications"] == {
        "dual-exact": 3, "ir-exact": 2, "source-candidate": 0,
        "ambiguous": 0, "unsupported": 1, "failed": 0}
    assert report["metrics"]["reachable"] == {"planned": 14, "complete": 14, "ratio": 1.0}
    assert {name: value["planned"] for name, value in report["languages"].items()} == {
        "c11": 2, "c17": 2, "c++17": 2, "c++20": 2}
    assert all({"source_candidates", "ir_candidates", "aligned_candidates", "formal_roots",
                "candidate_roots", "reachable", "frontier_items"} <= set(value)
               for value in report["languages"].values())
    assert report["safety"] == "not_evaluated" and report["findings"] is None


def test_fixture_inventory_covers_required_r1_scenarios():
    root = Path(__file__).resolve().parents[2] / "tests/fixtures/execution-root-analysis"
    inventory = json.loads((root / "case-inventory.json").read_text(encoding="utf-8"))
    capabilities = {item["capability"] for item in inventory["cases"]}
    assert capabilities >= {
        "c17-nested-thread-creation", "exported-framework-explicit-root",
        "same-callback-multiple-callsites", "recursive-fixed-point", "open-scope",
        "ir-only-no-debug", "ast-only", "callback-conflict", "profile-abi-mismatch",
        "budget-frontier", "cache-hit-and-invalidation", "plan-observation-mismatch"}
    for item in inventory["cases"]:
        for fixture in item["fixture"].split(";"):
            assert (root / fixture).is_file(), fixture
