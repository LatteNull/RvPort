"""Real independent worker local evaluation and generation checks."""
from copy import deepcopy

from test_offline import collect, WORKER
from memory_order_analyzer.contracts import document, file_hash, identity
from memory_order_analyzer.effect_contracts import effect_document
from memory_order_analyzer.effect_inputs import EffectInputs
from memory_order_analyzer.effect_worker import analyze_metadata, evaluate_batch
from memory_order_analyzer.execution import OutputStore


def test_real_evaluation_worklist_and_local_generation(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {"main.c": "int f(int x){if(x) return x+1; return 0;}"})
    assert report["build_status"] == "complete"
    manifest = document("ScopeManifest", target_id="evaluation", members=sorted(artifacts),
                        evidence="explicit compile-only TU", closed=True, external_boundaries=[])
    inputs = EffectInputs(manifest, artifacts, modules)
    store = OutputStore(tmp_path / "p2")
    locals_ = {key: entry["result"] for key, entry in analyze_metadata(inputs, WORKER, store).items()}
    key = next(iter(artifacts))
    local = locals_[key]
    function = next(fn for fn in modules[key]["functions"] if fn["name"] == "f")
    source = dict(artifact_key=key, function_id=None, id=function["id"])
    context = "上下文\n\t\u0001\u001f\u2028/😀"
    invocation = dict(id="root", context_id=context, function=source, parent_id=None, callsite=None,
                      cardinality="single", reason=None)
    request = effect_document("LocalEvaluationRequest", scope_id=inputs.scope_id, context_id=context,
        function=source, invocation_id="root", invocations=[invocation], origins=[local["origin"]],
        arguments=[dict(state="unknown", candidates=[], reason="caller input")], adoptions=[], dependencies=[],
        local_dependencies=[dict(artifact_key=key, digest=identity(local))], budgets=local["budgets"], call_bindings=[])
    before = deepcopy(modules), file_hash(artifacts[key]["path"])
    actual = evaluate_batch(inputs, [request], WORKER, store, local_facts=locals_)
    assert actual == evaluate_batch(inputs, [request], WORKER, store, local_facts=locals_)
    entry = actual[identity(request)]
    assert entry["error"] is None, entry
    result = entry["result"]
    assert result["request_hash"] == identity(request) and result["request"] == request
    assert result["status"] in {"complete", "partial"} and result["steps"] > 0
    assert len(result["blocks"]) == len(function["blocks"])
    assert {item["state"] for item in result["blocks"]} <= {"reachable", "unreachable", "pending"}
    assert any(block["state"] == "reachable" for block in result["blocks"])
    assert result["returns"] and result["values"]
    assert all(effect["kind"] in {"read", "write", "rmw", "cas", "fence", "unknown"}
               for effect in result["effects"])
    assert (modules, file_hash(artifacts[key]["path"])) == before
    # A structurally valid but altered supplement cannot masquerade as LLVM output.
    local["diagnostics"][0]["detail"] += " changed"
    request["local_dependencies"][0]["digest"] = identity(local)
    failed = evaluate_batch(inputs, [request], WORKER, store, local_facts=locals_)
    assert failed[identity(request)]["result"] is None
    assert failed[identity(request)]["error"]["code"] == "inputs_changed"
