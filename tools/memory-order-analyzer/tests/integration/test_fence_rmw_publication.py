"""A6 real Clang/LLVM compile-only and four-language truth acceptance."""

import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from memory_order_analyzer.advanced_atomic_analysis import (
    classify_source_constructs,
    extract_local_facts,
    normalize_for_equivalence,
)
from memory_order_analyzer.advanced_atomic_contracts import (
    advanced_atomic_document,
    expected_advanced_atomic_protocol,
)
from memory_order_analyzer.contracts import canonical, file_hash, identity
from memory_order_analyzer.source_contracts import expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.source_worker import analyze_source


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fence-rmw-publication"
WORKER = Path(os.environ.get("MOA_WORKER", "/output/build/moa-worker")).resolve()
SOURCE_WORKER = WORKER.with_name("memory-order-source-worker")


def compile_facts(tmp_path, source, standard, optimization, *, debug=False):
    driver = "clang++" if standard.startswith("c++") else "clang"
    output = tmp_path / f"{source.stem}-{standard.replace('+', 'p')}-{optimization}.bc"
    command = [driver, f"-std={standard}", f"-{optimization}", "-emit-llvm", "-c", str(source),
               "-o", str(output), "-g" if debug else "-g0"]
    subprocess.run(command, check=True, capture_output=True, text=True)
    artifact = file_hash(output)
    result = subprocess.run([WORKER, output, artifact], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def source_facts(tmp_path, source, standard, optimization):
    driver = "clang++" if standard.startswith("c++") else "clang"
    profile = build_profile(
        {"directory": str(source.parent), "file": source.name,
         "arguments": [driver, f"-std={standard}", f"-{optimization}", "-c", source.name]},
        compiler_version="21.1.8")
    request = source_document(
        "SourceSemanticRequest", profile=profile,
        physical_tu_id=identity({"source": str(source), "profile": profile["profile_id"]}),
        source_path=str(source), budgets=expected_source_protocol()["budgets"])
    return analyze_source(request, str(SOURCE_WORKER), tmp_path)


def test_checked_in_truth_has_four_independent_denominators_and_optional_backends():
    suite = json.loads((FIXTURES / "validation-suite.json").read_text(encoding="utf-8"))
    truth = json.loads((FIXTURES / "validation-truth.json").read_text(encoding="utf-8"))
    assert {case["language"] for case in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    for language in ("c11", "c17", "c++17", "c++20"):
        assert sum(case["language"] == language for case in suite["cases"]) == truth["languages"][language]["planned"] == 3
        assert truth["languages"][language]["fp"] == truth["languages"][language]["fn"] == 0
    assert {case["mode"] for case in suite["cases"]} == {"ast-ir", "ir-only", "ast-only"}
    comparison = json.loads((FIXTURES / "external-comparison.json").read_text(encoding="utf-8"))
    assert all(item["status"] == "not_run" and "not-oracle" in item["role"] for item in comparison["backends"])
    assert truth["safety"] == "not_established"


@pytest.mark.parametrize("standard,name", [
    ("c11", "c11-advanced.c"), ("c17", "c17-advanced.c"),
    ("c++17", "cpp17-advanced.cpp"), ("c++20", "cpp20-advanced.cpp"),
])
def test_real_clang_o0_o2_atomic_semantics_and_canonical_source_are_supported(tmp_path, standard, name):
    source = FIXTURES / "sources" / name
    facts = {opt: compile_facts(tmp_path, source, standard, opt) for opt in ("O0", "O2")}
    source_products = {opt: classify_source_constructs(
        [source_facts(tmp_path, source, standard, opt)], scope_id="scope", language_standard=standard)
                       for opt in ("O0", "O2")}
    locals_ = {opt: extract_local_facts([value], scope_id="scope", language_standard=standard,
                                        budgets=expected_advanced_atomic_protocol()["budgets"],
                                        source_constructs=source_products[opt])
               for opt, value in facts.items()}
    for local in locals_.values():
        kinds = {item["kind"] for item in local["events"]}
        assert "rmw" in kinds
        if standard in {"c11", "c++20"}:
            assert "cas" in kinds
    def lowering_signature(local):
        return sorted((
            item["function_id"].split(":symbol:")[-1], item["kind"], item["outcome"],
            item["ordering"], item["failure_ordering"], item["operation"], item["weak"],
            item["multiplicity"], item["read_effect"], item["write_effect"], item["mo_member"],
        ) for item in local["events"] if item["kind"] != "initialization")
    # Object/value identity is intentionally not compared here: at -O0 it is
    # completed by A1/A5 source/provenance overlays.  The actual atomic
    # operation, outcome, ordering and dynamic multiplicity must already agree.
    assert lowering_signature(locals_["O0"]) == lowering_signature(locals_["O2"])
    operations = {opt: {item["operation"] for item in value["constructs"] if item["status"] == "exact"}
                  for opt, value in source_products.items()}
    assert operations["O0"] == operations["O2"]
    assert operations["O0"]


def test_real_cross_tu_fence_facts_are_preserved_without_linking(tmp_path):
    modules = []
    for name in ("c17-cross-producer.c", "c17-cross-consumer.c"):
        modules.append(compile_facts(tmp_path, FIXTURES / "sources" / name, "c17", "O2"))
    local = extract_local_facts(modules, scope_id="scope", language_standard="c17",
                                budgets=expected_advanced_atomic_protocol()["budgets"])
    fences = [item for item in local["events"] if item["kind"] == "fence"]
    assert {item["ordering"] for item in fences} == {"release", "acquire"}
    assert len({item["artifact_key"] for item in fences}) == 2


def test_real_r3_atomic_shard_matches_eager_demanded_function(tmp_path):
    source = FIXTURES / "sources" / "c17-advanced.c"
    bc = tmp_path / "r3-c17.bc"
    subprocess.run(["clang", "-std=c17", "-O2", "-emit-llvm", "-c", str(source),
                    "-o", str(bc), "-g"], check=True, capture_output=True, text=True)
    artifact = file_hash(bc)
    ir = subprocess.run(["llvm-dis", "-o", "-", str(bc)], check=True,
                        capture_output=True, text=True).stdout
    target = re.search(r'target triple = "([^"]+)"', ir).group(1)
    layout = re.search(r'target datalayout = "([^"]+)"', ir).group(1)
    function = f"{artifact}:symbol:c17_exchange"
    demand_protocol = json.loads((ROOT / "protocols/demand-driven-analysis-protocol.json").read_text(encoding="utf-8"))
    protocol = expected_advanced_atomic_protocol()
    request = {
        "protocol": protocol,
        "demand_protocol": demand_protocol,
        "jobs": [{
            "id": artifact, "path": str(bc), "artifact_key": artifact,
            "bc_digest": file_hash(bc), "physical_tu_id": artifact[:8],
            "profile_id": "clang-c17", "target": target, "data_layout": layout,
            "abi": "itanium", "language": "c", "budgets": demand_protocol["budgets"],
            "demands": [{"function_id": function, "function_name": "c17_exchange",
                         "context_id": "ctx", "layers": ["semantic"]}],
        }],
    }
    request_path = tmp_path / "r3-request.json"
    request_path.write_text(canonical(request), encoding="utf-8")
    result = subprocess.run([WORKER, "--advanced-atomic-batch", request_path], check=True,
                            capture_output=True, text=True)
    shard = json.loads(result.stdout)["results"][0]["shards"][0]
    shard = advanced_atomic_document(
        "AdvancedAtomicFunctionFacts",
        **{key: value for key, value in shard.items()
           if key not in {"schema_version", "kind", "analysis_version", "policy_id"}})
    eager = json.loads(subprocess.run([WORKER, bc, artifact], check=True,
                                      capture_output=True, text=True).stdout)
    demand_graph = {"nodes": [{"artifact_key": artifact, "function_id": function,
                                "context_id": "ctx"}]}
    relevant_ids = [event["id"] for event in eager["events"] if event["function"] == function]
    thread_graph = {"effects": [
        {"id": "effect:" + identifier,
         "source": {"artifact_key": artifact, "function_id": function, "id": identifier},
         "thread_context_id": "ctx", "thread_instance_id": None}
        for identifier in relevant_ids], "mhp": []}
    eager_local = extract_local_facts(
        [eager], scope_id="scope", language_standard="c17", thread_graph=thread_graph,
        budgets=expected_advanced_atomic_protocol()["budgets"], demand_documents=(demand_graph,))
    lazy_local = extract_local_facts(
        [shard], scope_id="scope", language_standard="c17", thread_graph=thread_graph,
        budgets=expected_advanced_atomic_protocol()["budgets"], demand_documents=(demand_graph,))
    eager_view = [item for item in normalize_for_equivalence(eager_local)
                  if item["kind"] != "initialization"]
    assert eager_view == normalize_for_equivalence(lazy_local)
