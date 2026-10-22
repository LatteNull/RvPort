"""R3 real-Clang compile-only fixtures and lazy worker acceptance."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from memory_order_analyzer.demand_graph import expand_demands, node_key
from memory_order_analyzer.demand_adapters import (
    compare_semantics,
    concurrent_access_view,
    eager_function_view,
    lazy_function_view,
)
from memory_order_analyzer import cli


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/demand-driven-analysis"
PROTOCOL = json.loads((ROOT / "protocols/demand-driven-analysis-protocol.json").read_text())
ARTIFACT = {"c11": "1" * 64, "c17-main": "2" * 64, "c17-helper": "3" * 64,
            "c++17": "4" * 64, "c++20-main": "5" * 64, "c++20-helper": "6" * 64}


def compile_bc(source, output, standard, debug=True):
    compiler = "clang++" if standard.startswith("c++") else "clang"
    command = [compiler, f"-std={standard}", "-O0", "-emit-llvm", "-c", str(source), "-o", str(output)]
    command.append("-g" if debug else "-g0")
    subprocess.run(command, check=True, capture_output=True, text=True)
    ir = subprocess.run(["llvm-dis", "-o", "-", str(output)], check=True,
                        capture_output=True, text=True).stdout
    target = re.search(r'target triple = "([^"]+)"', ir).group(1)
    layout = re.search(r'target datalayout = "([^"]+)"', ir).group(1)
    return target, layout


def job(path, artifact, standard, target, layout, demands):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    language = "c++" if standard.startswith("c++") else "c"
    return {"id": artifact, "path": str(path), "artifact_key": artifact,
            "bc_digest": digest, "physical_tu_id": artifact[:8],
            "profile_id": f"clang-{standard}", "target": target, "data_layout": layout,
            "abi": "itanium", "demands": demands, "budgets": PROTOCOL["budgets"],
            "language": language}


def demand(artifact, name="main", context="root"):
    return {"function_id": f"{artifact}:symbol:{name}", "function_name": name,
            "context_id": context, "layers": ["effect", "semantic", "thread"]}


def worker(jobs, tmp_path):
    request = tmp_path / (jobs[0]["id"][:8] + "-request.json")
    request.write_text(json.dumps({"protocol": PROTOCOL, "jobs": jobs}), encoding="utf-8")
    executable = Path(os.environ["MOA_WORKER"])
    result = subprocess.run([executable, "--demand-batch", request], check=True,
                            capture_output=True, text=True)
    return json.loads(result.stdout)["results"]


def test_checked_in_truth_has_separate_language_denominators_and_boundaries():
    suite = json.loads((FIXTURES / "validation-suite.json").read_text())
    truth = json.loads((FIXTURES / "validation-truth.json").read_text())
    assert suite["suite_version"] == truth["suite_version"] == "r3-demand-v1"
    assert [case["id"] for case in suite["cases"]] == [case["case_id"] for case in truth["cases"]]
    assert {case["language"] for case in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    for language in ("c11", "c17", "c++17", "c++20"):
        assert sum(case["language"] == language for case in suite["cases"]) == 2
    assert {case["mode"] for case in suite["cases"]} == {"ast+ir", "ir-only", "ast-only"}
    assert {case["scope"] for case in suite["cases"]} == {"closed", "open"}
    assert all(case["unreachable_materialized"] is False for case in truth["cases"])


def test_pre_r3_protocol_and_eager_cli_baseline_is_immutable():
    baseline = json.loads((FIXTURES / "pre-r3-baseline.json").read_text())
    for relative, expected in baseline["protocol_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    choices = cli.parser()._subparsers._group_actions[0].choices
    assert set(baseline["eager_cli"]) - {"collect"} <= set(choices)
    assert "collect" not in choices and "ingest-bc-bundle" in choices
    assert "analyze-demanded-functions" in choices


@pytest.mark.parametrize("standard,source,artifact,debug", [
    ("c11", "c11-single.c", ARTIFACT["c11"], True),
    ("c17", "c17-main.c", ARTIFACT["c17-main"], True),
    ("c++17", "cpp17-single.cpp", ARTIFACT["c++17"], False),
    ("c++20", "cpp20-main.cpp", ARTIFACT["c++20-main"], True),
])
def test_real_clang_lazy_index_materializes_only_demanded_main(tmp_path, standard, source, artifact, debug):
    bc = tmp_path / f"{artifact[:4]}.bc"
    target, layout = compile_bc(FIXTURES / source, bc, standard, debug)
    result = worker([job(bc, artifact, standard, target, layout, [demand(artifact)])], tmp_path)[0]
    assert result["error"] is None
    assert result["metrics"]["module_parses"] == 1
    assert result["metrics"]["materialized_functions"] == 1
    assert len(result["shards"]) == 3 and all(item["status"] == "completed" for item in result["shards"])
    unreachable = [item for item in result["index"]["symbols"] if "unreachable" in item["name"]]
    assert unreachable and all(item["materializable"] is True for item in unreachable)
    assert not any("unreachable" in item["function_name"] for item in result["shards"])


@pytest.mark.parametrize("standard,main_source,helper_source,main_artifact,helper_artifact", [
    ("c17", "c17-main.c", "c17-helper.c", ARTIFACT["c17-main"], ARTIFACT["c17-helper"]),
    ("c++20", "cpp20-main.cpp", "cpp20-helper.cpp", ARTIFACT["c++20-main"], ARTIFACT["c++20-helper"]),
])
def test_cross_tu_exact_direct_call_adds_only_the_bound_definition(
        tmp_path, standard, main_source, helper_source, main_artifact, helper_artifact):
    main_bc, helper_bc = tmp_path / "main.bc", tmp_path / "helper.bc"
    target, layout = compile_bc(FIXTURES / main_source, main_bc, standard)
    helper_target, helper_layout = compile_bc(FIXTURES / helper_source, helper_bc, standard)
    assert (target, layout) == (helper_target, helper_layout)
    results = worker([
        job(main_bc, main_artifact, standard, target, layout, [demand(main_artifact)]),
        job(helper_bc, helper_artifact, standard, target, layout, []),
    ], tmp_path)
    assert all(result["error"] is None for result in results)
    indexes = {result["index"]["artifact_key"]: result["index"] for result in results}
    parent = {"id": node_key(main_artifact, f"{main_artifact}:symbol:main", "root",
                             ["effect", "semantic", "thread"]),
              "artifact_key": main_artifact, "function_id": f"{main_artifact}:symbol:main",
              "function_name": "main", "context_id": "root", "physical_tu_id": main_artifact[:8],
              "layers": ["effect", "semantic", "thread"], "state": "completed", "root_ids": ["main"],
              "consumers": ["P2", "P3"], "reasons": ["execution-root"], "depth": 0}
    nodes, edges, frontier = {parent["id"]: parent}, [], []
    shards = [{"status": item["status"], "layer": item["layer"], "facts": item["facts"]}
              for item in results[0]["shards"]]
    request = {"layers": parent["layers"], "members": [
        {"artifact_key": main_artifact, "physical_tu_id": main_artifact[:8], "evidence_mode": "ir-only"},
        {"artifact_key": helper_artifact, "physical_tu_id": helper_artifact[:8], "evidence_mode": "ir-only"}],
        "budgets": PROTOCOL["budgets"]}
    inserted = expand_demands(request, parent, shards, indexes, nodes, edges, frontier)
    assert len(inserted) == 1
    assert "helper" in nodes[inserted[0]]["function_name"]
    assert not any("helper_unreachable" in node["function_name"] for node in nodes.values())
    assert frontier == []


def test_fixed_sparse_scale_indexes_all_but_materializes_one_function(tmp_path):
    artifact = "7" * 64
    bc = tmp_path / "sparse.bc"
    target, layout = compile_bc(FIXTURES / "sparse-scale.c", bc, "c17", False)
    result = worker([job(bc, artifact, "c17", target, layout, [demand(artifact)])], tmp_path)[0]
    assert result["error"] is None
    assert result["index"]["counts"]["defined_functions"] >= 65
    assert result["index"]["counts"]["materialized_functions"] == 0
    assert result["metrics"]["module_parses"] == 1
    assert result["metrics"]["materialized_functions"] == 1
    assert len(result["shards"]) == 3
    assert not any("unreachable_1" in item["function_name"] for item in result["shards"])


@pytest.mark.parametrize("standard,source,artifact,debug", [
    ("c11", "c11-single.c", ARTIFACT["c11"], True),
    ("c17", "c17-main.c", ARTIFACT["c17-main"], True),
    ("c++17", "cpp17-single.cpp", ARTIFACT["c++17"], False),
    ("c++20", "cpp20-main.cpp", ARTIFACT["c++20-main"], True),
])
def test_real_eager_lazy_demanded_function_semantics_are_normalized_equal(
        tmp_path, standard, source, artifact, debug):
    bc = tmp_path / "equivalence.bc"
    target, layout = compile_bc(FIXTURES / source, bc, standard, debug)
    lazy = worker([job(bc, artifact, standard, target, layout, [demand(artifact)])], tmp_path)[0]
    eager_result = subprocess.run([Path(os.environ["MOA_WORKER"]), bc, artifact], check=True,
                                  capture_output=True, text=True)
    eager = eager_function_view(json.loads(eager_result.stdout), f"{artifact}:symbol:main")
    projected = lazy_function_view(lazy["shards"], f"{artifact}:symbol:main", "root")
    assert projected["status"] == "complete"
    assert projected["view"].pop("layer_consistency") == {"effect_accesses": True, "thread_order": True}
    assert compare_semantics(eager, projected["view"])["exact"]
    # The C++ batch transport intentionally omits envelope lineage; the Python
    # orchestrator adds it before any P2/P3/R2 adapter consumes the shards.
    adapted_shards = [{**item, "artifact_key": artifact} for item in lazy["shards"]]
    r2_input = concurrent_access_view(adapted_shards)
    assert r2_input["status"] == "complete"
    assert r2_input["safety"] == "not_evaluated" and r2_input["findings"] is None
    assert sorted((item["source"], item["kind"]) for item in r2_input["accesses"]) == \
        sorted((item["id"], item["kind"]) for item in eager["accesses"])
