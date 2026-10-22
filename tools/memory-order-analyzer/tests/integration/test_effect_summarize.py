"""Compile-only P2 summaries across physical TUs; analyzed code is never linked or run."""

import json

from test_offline import collect, WORKER
from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol


def test_three_tu_direct_call_propagates_atomic_effect_and_keeps_static_scoped(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "entry.c": "extern void put(int*,int); static int same; void entry(int *p){same=1;put(p,7);}",
        "worker.c": "static int same; void put(int*p,int v){same=2;__atomic_store_n(p,v,__ATOMIC_RELEASE);}",
        "spare.c": "static int same; int spare(void){return same;}",
    }, "clang", "c17")
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="p2-three-tu", members=sorted(artifacts),
                     evidence="three explicit compile-only physical TUs", closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"
    scope_path.write_text(canonical(scope))
    entry_key, entry = next((key, fn) for key, module in modules.items() for fn in module["functions"]
                            if fn["name"] == "entry")
    parameter_id = entry["parameters"][0]
    argument = {"kind": "parameter", "source": {"artifact_key": entry_key,
                "function_id": entry["id"], "id": parameter_id}, "invocation_id": None}
    request = effect_document("EffectAnalysisRequest", scope=str(scope_path), mode="roots",
        roots=[{"artifact_key": entry_key, "function_id": entry["id"], "arguments": [argument]}],
        budgets=expected_analysis_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request))
    output = tmp_path / "summary-output"
    code = cli.main(["summarize", "--request", str(request_path), "--scope", str(scope_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    assert code == result["exit_code"] == 2
    assert result["raw_fact_extraction"] == "partial" and result["resolutions"]
    assert result["safety"] == "not_evaluated" and result["findings"] is None
    summary_path = next((output / "summaries").glob("*.json"))
    summary = json.loads(summary_path.read_text())
    atomic = [effect for effect in summary["effects"] if effect["atomic"]]
    assert atomic and any(effect["ordering"] == "release" for effect in atomic)
    assert any(effect["value"] == {"kind": "integer", "bits": 32, "hex": "7"} for effect in atomic)
    assert len({fn["id"] for module in modules.values() for fn in module["globals"]
                if fn["linkage"] == "internal" and fn["name"] == "same"}) == 3
    assert not list(tmp_path.glob("*.o"))


def test_atomic_wrapper_orders_are_specialized_and_unknown_boundary_is_partial(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "atomic.cpp": "#include <atomic>\nstd::atomic<int> x; __attribute__((noinline)) void wrapped(int v,std::memory_order o){x.store(v,o);} void rel(){wrapped(1,std::memory_order_release);} void rlx(){wrapped(2,std::memory_order_relaxed);} void seq(){wrapped(3,std::memory_order_seq_cst);}",
    }, "clang++", "c++20")
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="atomic-wrapper", members=sorted(artifacts),
                     evidence="locked Clang/libstdc++ compile-only input", closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key = next(iter(modules))
    roots = [{"artifact_key": key, "function_id": fn["id"], "arguments": []}
             for fn in modules[key]["functions"] if fn["name"] in {"_Z3relv", "_Z3rlxv", "_Z3seqv"}]
    assert len(roots) == 3
    request = effect_document("EffectAnalysisRequest", scope=str(scope_path), mode="roots", roots=roots,
                              budgets=expected_analysis_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request))
    output = tmp_path / "atomic-output"
    code = cli.main(["summarize", "--request", str(request_path), "--scope", str(scope_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output), "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    assert code in {0, 2} and result["exit_code"] == code
    orders = set()
    for path in (output / "summaries").glob("*.json"):
        summary = json.loads(path.read_text())
        orders |= {effect["ordering"] for effect in summary["effects"] if effect["atomic"]}
    assert orders >= {"monotonic", "release", "seq_cst"}
    assert all(item["toolchain"]["producer_attested"]["llvm_version"] == "21.1.8"
               for item in artifacts.values())


def test_returned_field_pointer_is_rebound_to_caller_parameter(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "field.c": "struct pair { int first; int second; }; int *field(struct pair *p){return &p->second;}",
        "caller.c": "struct pair { int first; int second; }; extern int *field(struct pair*); void publish(struct pair *p){int *q=field(p);__atomic_store_n(q,5,__ATOMIC_RELEASE);}",
    }, "clang", "c17")
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="returned-field", members=sorted(artifacts),
                     evidence="two explicit compile-only TUs with a returned field pointer",
                     closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items() for function in module["functions"]
                     if function["name"] == "publish")
    parameter = root["parameters"][0]
    argument = {"kind": "parameter", "source": {"artifact_key": key, "function_id": root["id"],
                "id": parameter}, "invocation_id": None}
    request = effect_document("EffectAnalysisRequest", scope=str(scope_path), mode="roots",
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": [argument]}],
        budgets=expected_analysis_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request))
    output = tmp_path / "field-output"
    code = cli.main(["summarize", "--request", str(request_path), "--scope", str(scope_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output), "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    assert code == result["exit_code"] == 2
    assert result["raw_fact_extraction"] == "partial" and result["resolutions"]
    summary = json.loads(next((output / "summaries").glob("*.json")).read_text())
    atomic = next(effect for effect in summary["effects"] if effect["atomic"])
    assert atomic["ordering"] == "release" and atomic["value"] == {"kind": "integer", "bits": 32, "hex": "5"}
    assert atomic["address"]["kind"] == "expression"
    assert atomic["address"]["operands"][0]["kind"] == "parameter"
    assert atomic["address"]["operands"][0]["source"] == argument["source"]
    assert atomic["address"]["operands"][0]["invocation_id"] == summary["root_invocation_id"]
    assert atomic["address"]["operands"][1] == {"kind": "integer", "bits": 64, "hex": "4"}
    assert not list(tmp_path.glob("*.o"))


def test_no_debug_recursive_and_external_unknown_keeps_known_atomic_effect(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "recursive.c": "extern int opaque(int*); int recur(int *p,int n){__atomic_store_n(p,n,__ATOMIC_RELEASE);if(n)return recur(p,n-1);return opaque(p);}",
    }, "clang", "c17", flags=("-g0",))
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="recursive-partial", members=sorted(artifacts),
                     evidence="no-debug recursive TU with an unresolved external boundary",
                     closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key = next(iter(modules)); root = next(fn for fn in modules[key]["functions"] if fn["name"] == "recur")
    pointer = {"kind": "parameter", "source": {"artifact_key": key, "function_id": root["id"],
               "id": root["parameters"][0]}, "invocation_id": None}
    count = {"kind": "integer", "bits": 32, "hex": "1"}
    request = effect_document("EffectAnalysisRequest", scope=str(scope_path), mode="roots",
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": [pointer, count]}],
        budgets={**expected_analysis_protocol()["budgets"], "scc_iterations": 1})
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(request))
    output = tmp_path / "recursive-output"
    code = cli.main(["summarize", "--request", str(request_path), "--scope", str(scope_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output), "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    assert code == result["exit_code"] == 2 and result["source_mapping"] in {"partial", "unavailable"}
    summary = json.loads(next((output / "summaries").glob("*.json")).read_text())
    assert any(effect["atomic"] and effect["ordering"] == "release" for effect in summary["effects"])
    assert any(effect["kind"] == "unknown" for effect in summary["effects"])
    assert summary["status"] == "partial" and summary["diagnostics"]
