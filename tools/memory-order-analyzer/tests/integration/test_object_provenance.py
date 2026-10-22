"""Real Clang/LLVM A5 matrix for C11/C17/C++17/C++20 and cross-TU binding."""

import json
import os
from pathlib import Path
import subprocess

from memory_order_analyzer.analyze_object_provenance import analyze_object_provenance
from memory_order_analyzer.contracts import canonical, file_hash, identity
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol
from memory_order_analyzer.object_provenance import compare_truth
from memory_order_analyzer.provenance_contracts import (
    expected_provenance_protocol, provenance_document, read_provenance_document, semantic_digest,
)
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_contracts import counts, source_document


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/object-provenance"
IR_WORKER = Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker"))
SOURCE_WORKER = IR_WORKER.with_name("memory-order-source-worker")


def _case(case, tmp_path, suffix=""):
    budgets = expected_provenance_protocol()["budgets"]
    members, compiled = [], {}
    for index, relative in enumerate(case["sources"]):
        source = FIXTURES / relative
        driver = "clang++" if source.suffix == ".cpp" else "clang"
        command = [driver, f"-std={case['standard']}", "-O0", "-g0", "-pthread",
                   "-emit-llvm", "-c", str(source)]
        bitcode = tmp_path / f"{case['id']}-{index}.bc"
        subprocess.run([*command, "-o", str(bitcode)], check=True)
        profile = build_profile(
            {"directory": str(source.parent), "file": source.name,
             "arguments": [driver, f"-std={case['standard']}", "-O0", "-g0", "-pthread", "-c", source.name]},
            compiler_version="21.1.8")
        physical = identity({"case": case["id"], "source": relative, "profile": profile["profile_id"]})
        source_request = provenance_document(
            "SourceObjectPathRequest", profile=profile, physical_tu_id=physical,
            source_path=str(source), budgets=budgets, semantic_digest=None)
        llvm_request = provenance_document(
            "LLVMObjectProvenanceRequest", artifact_key=file_hash(bitcode),
            profile_id=profile["profile_id"], physical_tu_id=physical,
            bitcode={"path": str(bitcode), "sha256": file_hash(bitcode)},
            dependencies=[], budgets=budgets, semantic_digest=None)
        source_request_path = tmp_path / f"{case['id']}-{index}-source.json"
        llvm_request_path = tmp_path / f"{case['id']}-{index}-llvm.json"
        source_request_path.write_text(canonical(source_request), encoding="utf-8")
        llvm_request_path.write_text(canonical(llvm_request), encoding="utf-8")
        members.append({"physical_tu_id": physical, "profile_id": profile["profile_id"],
                        "language": case["language"], "standard": case["standard"],
                        "source_request": str(source_request_path), "llvm_request": str(llvm_request_path)})
        compiled[relative] = {"artifact_key": file_hash(bitcode), "physical_tu_id": physical}
    members.sort(key=lambda item: item["physical_tu_id"])
    artifact_store = tmp_path / "cache"
    dependencies = []
    cross = {
        "02-c11-cross": ("c11/cross_caller.c", "c11/cross_impl.c", "c11_read", "c11_field"),
        "06-cpp17-cross": ("cpp17/cross_caller.cpp", "cpp17/cross_impl.cpp",
                           "_Z10cpp17_readv", "_Z11cpp17_fieldP3Box"),
    }.get(case["id"])
    if cross:
        caller_path, callee_path, caller_name, callee_name = cross
        caller, callee = compiled[caller_path], compiled[callee_path]
        scope = identity({"case": case["id"], "layer": "a5-scope"})
        entity = {
            "id": identity({"function": callee_name}), "object_id": None, "kind": "function",
            "resolution": "resolved", "key": {"symbol": callee_name, "kind": "function"},
            "declarations": [f"declaration:{callee_name}"],
            "definitions": [f"definition:{callee_name}"], "candidates": [],
            "evidence": ["usr"], "reason": None,
        }
        index = source_document(
            "ProgramEntityIndex", scope_id=scope, status="complete", dependencies=[],
            entities=[entity], counts={"groups": counts(1)}, diagnostics=[], frontier=[],
            semantic_digest=None)
        context = f"{case['id']}:context"
        source_ref = {"artifact_key": caller["artifact_key"], "function_id": None,
                      "id": caller_name}
        summary = effect_document(
            "EffectSummary", scope_id=scope, context_id=context,
            root_invocation_id=f"{context}:root",
            invocations=[{"id": f"{context}:root", "context_id": context,
                          "function": source_ref, "parent_id": None, "callsite": None,
                          "cardinality": "single", "reason": None}],
            root={"artifact_key": caller["artifact_key"], "function_id": caller_name,
                  "arguments": []},
            origins=[{"artifact_key": caller["artifact_key"], "module_hash": "a" * 64,
                      "facts_hash": "b" * 64, "extractor_version": "0.2.0",
                      "llvm_version": "21.1.8", "profile": "source-preserving"}],
            budgets=expected_analysis_protocol()["budgets"], effects=[], order=[], returns=[],
            escape=[], adoptions=[{
                "call": {"artifact_key": caller["artifact_key"], "function_id": caller_name,
                         "id": f"{caller_name}:call:0"},
                "target": {"artifact_key": callee["artifact_key"], "function_id": None,
                           "id": callee_name},
                "kind": "unique-definition", "reason": "exact_unique_definition",
                "assumptions": [],
            }], dependencies=[], local_dependencies=[], resolutions=[], diagnostics=[],
            status="complete")
        for directory, identifier, value in (
                ("entity-index", scope, index), ("summaries", context, summary)):
            path = artifact_store / directory / f"{identifier}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(canonical(value), encoding="utf-8")
            dependencies.append({"kind": value["kind"], "id": identifier,
                                 "digest": identity(value)})
    else:
        scope = identity({"case": case["id"], "layer": "a5-scope"})
    request = provenance_document(
        "BoundedObjectProvenanceRequest", scope_id=scope, roots=[case["id"]],
        members=members, dependencies=sorted(dependencies, key=lambda item: (item["kind"], item["id"])),
        budgets=budgets, semantic_digest=None)
    request_path = tmp_path / f"{case['id']}-request.json"
    request_path.write_text(canonical(request), encoding="utf-8")
    output = tmp_path / f"{case['id']}{suffix}-output"
    report = analyze_object_provenance(request_path, artifact_store, output,
                                       SOURCE_WORKER, IR_WORKER)
    graph = json.loads((output / "graphs" / f"{report['graph']['id']}.json").read_text(encoding="utf-8"))
    return report, graph, output


def _observations(graph, output):
    source_facts = [json.loads(path.read_text(encoding="utf-8"))
                    for path in (output / "source-path-facts").glob("*.json")]
    llvm_facts = [json.loads(path.read_text(encoding="utf-8"))
                  for path in (output / "llvm-provenance-facts").glob("*.json")]
    result = set()
    if graph["objects"]:
        result.add("runtime-object")
    if len({item["storage"]["id"] for item in graph["objects"]}) > 1:
        result.add("distinct-storage")
    if any(len(path["segments"]) >= 2 for facts in source_facts for path in facts["paths"]):
        result.add("nested-source-path")
    if any(segment.get("union_group") for facts in source_facts for path in facts["paths"]
           for segment in path["segments"]):
        result.add("union-overlap")
    if any(segment["kind"] == "cast" for facts in source_facts for path in facts["paths"]
           for segment in path["segments"]):
        result.add("source-cast")
    if any(value["opcode"] == "load" and value["domain"]["state"] != "must"
           for facts in llvm_facts for value in facts["values"]):
        result.add("conservative-load")
    if any(item["kind"] == "direct-actual-to-formal" and item["status"] == "exact"
           for item in graph["relations"]):
        result.add("exact-direct-binding")
    if any(item["kind"] == "direct-return-to-call" and item["status"] == "exact"
           for item in graph["relations"]):
        result.add("exact-return-binding")
    return sorted(result)


def test_four_language_real_workers_cross_tu_truth_and_cache(tmp_path):
    suite = read_provenance_document(FIXTURES / "validation-suite.json", "ObjectProvenanceValidationSuite")
    truth = read_provenance_document(FIXTURES / "validation-truth.json", "ObjectProvenanceValidationTruth")
    actuals = {}
    graphs = {}
    for case in suite["cases"]:
        report, graph, output = _case(case, tmp_path)
        assert report["status"] == "complete"
        assert report["exit_code"] == 0
        assert report["safety"] == "not_established" and report["findings"] is None
        assert report["modes"]["ast+ir"] == len(case["sources"])
        assert graph["objects"]
        assert (output / "source-path-facts").is_dir()
        actuals[case["id"]] = {"status": report["status"],
                                "must_objects": _observations(graph, output), "unknown": False}
        graphs[case["id"]] = graph
    validation = compare_truth(suite, truth, actuals)
    assert validation["status"] == "complete"
    assert validation["metrics"] == {"planned": 8, "completed": 8, "tp": 29,
                                      "fp": 0, "fn": 0, "abstention": 0}
    assert {name: item["planned"] for name, item in validation["languages"].items()} == {
        "c11": 2, "c17": 2, "c++17": 2, "c++20": 2}
    assert any(item["kind"] == "direct-actual-to-formal" and item["status"] == "exact"
               for item in graphs["02-c11-cross"]["relations"])
    assert any(item["kind"] == "direct-return-to-call" and item["status"] == "exact"
               for item in graphs["02-c11-cross"]["relations"])
    assert any(item["kind"] == "direct-actual-to-formal" and item["status"] == "exact"
               for item in graphs["06-cpp17-cross"]["relations"])
    cpp_objects = graphs["05-cpp17-objects"]["objects"]
    assert len({item["storage"]["id"] for item in cpp_objects}) > 1


def test_ast_only_ir_only_and_candidate_relevant_failure_modes_are_partial(tmp_path):
    suite = read_provenance_document(FIXTURES / "validation-suite.json", "ObjectProvenanceValidationSuite")
    case = suite["cases"][0]
    report, graph, output = _case(case, tmp_path)
    source_request = next((output / "source-path-facts").glob("*.json"))
    source_facts = json.loads(source_request.read_text(encoding="utf-8"))
    assert source_facts["mode"] == "ast-only"
    assert report["status"] == "complete" and graph["status"] == "complete"

    base_path = tmp_path / f"{case['id']}-request.json"
    base = read_provenance_document(base_path, "BoundedObjectProvenanceRequest")
    member = base["members"][0]
    source = read_provenance_document(member["source_request"], "SourceObjectPathRequest")
    llvm = read_provenance_document(member["llvm_request"], "LLVMObjectProvenanceRequest")
    bad_source = json.loads(canonical(source)); bad_source["profile"]["source"]["path"] = "/missing/a5.c"
    bad_source["semantic_digest"] = semantic_digest(bad_source)
    bad_llvm = json.loads(canonical(llvm)); bad_llvm["bitcode"]["path"] = "/missing/a5.bc"
    bad_llvm["semantic_digest"] = semantic_digest(bad_llvm)
    bad_source_path = tmp_path / "bad-source.json"; bad_source_path.write_text(canonical(bad_source), encoding="utf-8")
    bad_llvm_path = tmp_path / "bad-llvm.json"; bad_llvm_path.write_text(canonical(bad_llvm), encoding="utf-8")

    def variant(name, source_path, llvm_path):
        value = json.loads(canonical(base))
        value["members"][0]["source_request"] = str(source_path)
        value["members"][0]["llvm_request"] = str(llvm_path)
        value["semantic_digest"] = semantic_digest(value)
        path = tmp_path / f"{name}.json"; path.write_text(canonical(value), encoding="utf-8")
        result = analyze_object_provenance(path, tmp_path / "cache", tmp_path / name,
                                           SOURCE_WORKER, IR_WORKER)
        result_graph = json.loads((tmp_path / name / "graphs" /
                                   f"{result['graph']['id']}.json").read_text(encoding="utf-8"))
        return result, result_graph

    ir_only, ir_graph = variant("ir-only", bad_source_path, member["llvm_request"])
    ast_only, ast_graph = variant("ast-only", member["source_request"], bad_llvm_path)
    failed, failed_graph = variant("failed", bad_source_path, bad_llvm_path)
    assert ir_only["status"] == ast_only["status"] == "partial"
    assert ir_only["exit_code"] == ast_only["exit_code"] == 2
    assert ir_graph["members"][0]["mode"] == "ir-only"
    assert ast_graph["members"][0]["mode"] == "ast-only"
    assert failed["status"] == "failed" and failed["exit_code"] == 1
    assert failed_graph["members"][0]["mode"] == "failed"
    assert all(item["code"] == "object-provenance-member-failed"
               for item in failed_graph["frontier"][:2])


def test_real_worker_cold_warm_cache_preserves_semantic_digest(tmp_path):
    suite = read_provenance_document(FIXTURES / "validation-suite.json", "ObjectProvenanceValidationSuite")
    case = suite["cases"][1]
    cold, cold_graph, _ = _case(case, tmp_path, "-cold")
    warm, warm_graph, _ = _case(case, tmp_path, "-warm")
    assert cold["cache"] == {"hits": 0, "misses": 5}
    assert warm["cache"] == {"hits": 5, "misses": 0}
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert cold_graph["semantic_digest"] == warm_graph["semantic_digest"]
