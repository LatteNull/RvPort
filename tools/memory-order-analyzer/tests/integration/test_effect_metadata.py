"""Real BC-to-P2 transport regression, not effect-specialization acceptance."""

from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import document, file_hash
from memory_order_analyzer.effect_inputs import EffectInputs
from memory_order_analyzer.effect_worker import analyze_metadata
from memory_order_analyzer.execution import OutputStore
from test_offline import collect, WORKER


@pytest.mark.parametrize("standard", ["c++17", "c++20"])
def test_atomic_wrapper_metadata_preserves_raw_branches(tmp_path, standard):
    report, artifacts, modules, _ = collect(tmp_path, {"atomic.cpp":
        "#include <atomic>\nstd::atomic<int> x; void wrapped(std::atomic<int>* p,int v,std::memory_order o)"
        "{p->store(v,o);} void publish(){wrapped(&x,1,std::memory_order_release);}\n"}, "clang++", standard)
    assert report["build_status"] == "complete"
    manifest = document("ScopeManifest", target_id="atomic-metadata", members=sorted(artifacts),
                        evidence="one explicitly compiled physical TU", closed=True, external_boundaries=[])
    before = deepcopy(modules)
    hashes = {key: file_hash(a["path"]) for key, a in artifacts.items()}
    inputs = EffectInputs(manifest, artifacts, modules)
    first = analyze_metadata(inputs, WORKER, OutputStore(tmp_path / "p2"))
    assert first == analyze_metadata(inputs, WORKER, OutputStore(tmp_path / "p2-repeat"))
    key = next(iter(artifacts))
    local = first[key]["result"]
    assert first[key]["error"] is None and local["status"] == "partial"
    assert local["diagnostics"][0]["code"] == "local_evaluation_pending"
    raw_functions = {fn["id"]: fn for fn in modules[key]["functions"]}
    odr = [fn for fn in local["functions"] if fn["linkage"] == "linkonce_odr"]
    assert odr and all(raw_functions[fn["source"]["id"]]["linkage"] == "linkonce" for fn in odr)
    assert any(fn["selection"] == "any" for fn in odr)
    raw_calls = {call["id"] for call in modules[key]["calls"]}
    assert {call["source"]["id"] for call in local["calls"]} == raw_calls
    assert any(attr["status"] == "modeled" and "noundef" in attr["text"]
               for fn in local["functions"] for attr in fn["interface"]["attributes"])
    assert modules == before
    assert hashes == {k: file_hash(a["path"]) for k, a in artifacts.items()}
    assert {e.get("ordering") for e in modules[key]["events"]} >= {"monotonic", "release", "seq_cst"}
    assert not modules[key]["capabilities"]["callsite_specialization"]
    assert local["objects"] and local["ir_nodes"] and local["analysis_evidence"]
    assert all(":p2:" in e["ref"]["analysis_id"] for e in local["analysis_evidence"])
    assert any(e["kind"] == "aa_clobber" for e in local["analysis_evidence"])


def test_batch_multiple_physical_tus_and_unsupported_abi(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "caller.c": "extern void f(int*); void entry(int *p){f(p);}",
        "callee.c": "void f(int *p){*p=1;} float unsupported(float x){return x;}",
    }, "gcc", "c11")
    assert report["build_status"] == "complete"
    manifest = document("ScopeManifest", target_id="two-module-metadata", members=sorted(artifacts),
                        evidence="two explicit compile-only members", closed=True, external_boundaries=[])
    result = analyze_metadata(EffectInputs(manifest, artifacts, modules), WORKER, OutputStore(tmp_path / "p2"))
    assert len(result) == 2 and all(item["error"] is None for item in result.values())
    functions = [fn for item in result.values() for fn in item["result"]["functions"]]
    unsupported = next(fn for fn in functions if fn["source"]["id"].endswith(":symbol:unsupported"))
    assert unsupported["interface"]["status"] == "unsupported"
    assert all(item["result"]["status"] == "partial" for item in result.values())


def test_unused_alloca_survives_only_in_p2_and_budget_error_preserves_plan(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {"unused.c": "void f(void){ int unused; }"}, "clang", "c11")
    assert report["build_status"] == "complete"
    manifest = document("ScopeManifest", target_id="unused-alloca", members=sorted(artifacts),
                        evidence="explicit compile-only unused local", closed=True, external_boundaries=[])
    inputs = EffectInputs(manifest, artifacts, modules)
    result = analyze_metadata(inputs, WORKER, OutputStore(tmp_path / "p2"))
    key = next(iter(artifacts))
    local = result[key]["result"]
    raw_ids = {v["id"] for v in modules[key]["values"]}
    assert any(o["source"]["id"] not in raw_ids for o in local["objects"])
    tight = {**local["budgets"], "local_steps": 1}
    failed = analyze_metadata(inputs, WORKER, OutputStore(tmp_path / "tight"), budgets=tight)
    assert list(failed) == list(result)
    assert failed[key]["result"] is None and failed[key]["error"]["code"] == "local_budget_exceeded"
