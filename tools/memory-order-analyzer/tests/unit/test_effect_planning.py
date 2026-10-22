"""P2 adoption, summary, recursion, cache and report behavior."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.effect_adoption import adoption_digest, derive_adoptions
from memory_order_analyzer.effect_cache import DerivedCache, instance_key, local_key, scc_key, template_key
from memory_order_analyzer import effect_cache
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol
from memory_order_analyzer.effect_report import aggregate_status, build_report, counts
from memory_order_analyzer.effect_scheduler import Scheduler, run_scheduler, select_roots
from memory_order_analyzer.effect_summary import (
    compose, conservative_widen, context_id, finite, fixed_point, instantiate_child,
    make_request, public_arguments, strongly_connected, summary_from_result, unknown,
)


KEY, OTHER, SCOPE = "a" * 64, "b" * 64, "d" * 64


def interface(status="supported", signature="i32 (i32)"):
    return {"function_type": signature, "return_type": "i32", "parameter_types": ["i32"],
            "calling_convention": 0, "vararg": False, "attributes": [], "status": status,
            "nounwind": False, "noreturn": False}


def raw_function(key, name="f", ident="f", linkage="external", declaration=False):
    return {"id": ident, "name": name, "linkage": linkage, "declaration": declaration,
            "comdat": linkage in {"linkonce", "linkonce_odr", "weak", "weak_odr"},
            "parameters": [f"{ident}:arg0"], "return_type": "i32", "vararg": False,
            "blocks": []}


def raw_call(function="caller", ident="call", target="f", kind="direct"):
    return {"id": ident, "kind": kind, "target": target if kind == "direct" else None,
            "function": function, "source": {"inline_chain": []}, "called_ref": "called",
            "arguments": [], "result_ref": None, "function_type": "i32 (i32)",
            "calling_convention": 0, "normal": None, "unwind": None, "tail": "none",
            "attributes": "", "bundles": [], "status": "known", "attribute_status": "not_applicable"}


def local_function(key, ident="f", linkage="external", *, fingerprint="1" * 64,
                   selection=None, supported="supported", exact=True, interposable=False, dso=True):
    return {"source": {"artifact_key": key, "function_id": None, "id": ident},
            "linkage": linkage, "visibility": "default", "dso_local": dso,
            "declaration": False, "interposable": interposable, "exact_definition": exact,
            "comdat": "x" if selection else None, "selection": selection,
            "interface": interface(supported), "body_fingerprint": fingerprint}


def local_call(key, function="caller", ident="call", supported="supported"):
    return {"source": {"artifact_key": key, "function_id": function, "id": ident},
            "interface": interface(supported), "target": {"artifact_key": key, "function_id": None, "id": "f"},
            "tail": "none", "bundles": []}


def fake_inputs(*, odr=False, duplicate=False, open_scope=False):
    callee = raw_function(KEY, linkage="linkonce_odr" if odr else "external")
    caller = raw_function(KEY, "caller", "caller")
    modules = {KEY: {"functions": [caller, callee], "calls": [raw_call()], "events": [], "globals": [],
                     "values": [], "protocol": {"extractor_version": "0.2.0", "llvm_version": "21.1.8"},
                     "source_mapping": "unavailable"}}
    locals_ = {KEY: {"functions": [local_function(KEY, "caller"),
                                    local_function(KEY, linkage="linkonce_odr" if odr else "external",
                                                   selection="any" if odr else None)],
                     "calls": [local_call(KEY)]}}
    members = [KEY]
    if duplicate:
        modules[OTHER] = {"functions": [raw_function(OTHER)], "calls": [], "events": [], "globals": [],
                          "values": [], "protocol": modules[KEY]["protocol"], "source_mapping": "complete"}
        locals_[OTHER] = {"functions": [local_function(OTHER)], "calls": []}; members.append(OTHER)
    return SimpleNamespace(scope={"members": members, "closed": not open_scope,
                                  "external_boundaries": ["plugin"] if open_scope else []},
                           modules=modules, scope_id=SCOPE), locals_


@pytest.mark.parametrize("variant,expected", [
    ({}, "unique-definition"), ({"odr": True}, "odr-body-under-contract"),
    ({"duplicate": True}, "unknown"), ({"open_scope": True}, "unknown")])
def test_adoption_exact_odr_and_ambiguous_boundaries(variant, expected):
    inputs, local = fake_inputs(**variant)
    result = derive_adoptions(inputs, local)
    assert result[0]["kind"] == expected
    assert inputs.modules[KEY]["calls"][0]["id"] == "call"  # old ScopeIndex/raw facts untouched
    if expected == "odr-body-under-contract":
        assert "llvm-odr-contract" in result[0]["assumptions"]


def test_adoption_rejects_abi_weak_linkonce_and_conflicting_odr():
    inputs, local = fake_inputs()
    local[KEY]["calls"][0]["interface"] = interface(signature="i64 (i64)")
    assert derive_adoptions(inputs, local)[0]["reason"] == "unsupported_or_mismatched_abi"
    for linkage in ("weak", "weak_odr", "linkonce"):
        inputs, local = fake_inputs()
        inputs.modules[KEY]["functions"][1]["linkage"] = linkage
        local[KEY]["functions"][1].update(linkage=linkage, selection="any", comdat="x")
        assert derive_adoptions(inputs, local)[0]["kind"] == "unknown"
    inputs, local = fake_inputs(odr=True, duplicate=True)
    inputs.modules[OTHER]["functions"][0]["linkage"] = "linkonce_odr"
    local[OTHER]["functions"][0].update(linkage="linkonce_odr", selection="any", comdat="x",
                                         body_fingerprint="2" * 64)
    assert derive_adoptions(inputs, local)[0]["kind"] == "unknown"
    inputs.modules[KEY]["calls"][0].update(kind="indirect", target=None)
    assert derive_adoptions(inputs, local)[0]["reason"] == "indirect_call"
    inputs.modules[KEY]["calls"][0].update(kind="direct", target="missing")
    assert derive_adoptions(inputs, local)[0]["reason"] == "missing_definition"
    assert adoption_digest(derive_adoptions(inputs, local)) == adoption_digest(derive_adoptions(inputs, local))


def origin(key=KEY):
    return {"artifact_key": key, "module_hash": "2" * 64, "facts_hash": "3" * 64,
            "extractor_version": "0.2.0", "llvm_version": "21.1.8", "profile": "source-preserving"}


def request_and_result(*, known_call=False, status="complete"):
    budgets = expected_analysis_protocol()["budgets"]
    function = {"artifact_key": KEY, "function_id": None, "id": "f"}
    request = effect_document("LocalEvaluationRequest", scope_id=SCOPE, context_id="ctx", function=function,
        invocation_id="inv", invocations=[{"id": "inv", "context_id": "ctx", "function": function,
            "parent_id": None, "callsite": None, "cardinality": "single", "reason": None}],
        origins=[origin()], arguments=[finite({"kind": "integer", "bits": 32, "hex": "1"})],
        adoptions=[{"call": {"artifact_key": KEY, "function_id": "f", "id": "call"},
                    "target": {"artifact_key": OTHER, "function_id": None, "id": "g"},
                    "kind": "unique-definition", "reason": "exact", "assumptions": []}] if known_call else [],
        dependencies=[], call_bindings=[], local_dependencies=[{"artifact_key": KEY, "digest": "4" * 64}], budgets=budgets)
    call_source = {"artifact_key": KEY, "function_id": "f", "id": "call"}
    effect = {"id": "raw-effect", "source": call_source, "context_id": "ctx", "invocation_id": "inv",
              "kind": "unknown", "address": None, "size_bytes": None, "value": None, "atomic": False,
              "volatile": False, "ordering": None, "failure_ordering": None, "syncscope": None,
              "visibility": "unknown", "guards": [], "occurrence": "may", "multiplicity": "single",
              "proof": [], "call_path": []}
    diagnostic = {"code": "unknown_call_effect", "detail": "pending", "source": call_source, "context_id": "ctx"}
    result = effect_document("LocalEvaluationResult", request=request, request_hash=identity(request),
        scope_id=SCOPE, context_id="ctx", budgets=budgets, values=[], blocks=[], call_requests=[],
        effects=[effect], order=[], returns=[], escape=[], resolutions=[], frontier=[diagnostic] if status != "complete" else [],
        diagnostics=[diagnostic] if status != "complete" else [], status=status, steps=1)
    return request, result


def test_domains_context_summary_and_known_call_replacement():
    value = {"kind": "integer", "bits": 32, "hex": "A"}
    assert public_arguments([finite(value), unknown("x")]) == [value, {"kind": "unknown", "reason": "x"}]
    assert context_id(SCOPE, {"id": "f"}, [finite(value)], {"x": 1}) == context_id(SCOPE, {"id": "f"}, [finite(value)], {"x": 1})
    _, complete = request_and_result(status="complete")
    summary = summary_from_result(complete)
    assert summary["status"] == "complete" and summary["effects"][0]["id"] != "raw-effect"
    _, resolved = request_and_result(known_call=True, status="partial")
    summary = summary_from_result(resolved)
    assert summary["status"] == "complete" and not summary["effects"] and not summary["diagnostics"]


def child_summary():
    _, result = request_and_result(status="complete")
    result["request"]["context_id"] = result["context_id"] = "child"
    result["request"]["invocation_id"] = "child-inv"
    result["request"]["invocations"][0].update(id="child-inv", context_id="child")
    result["request_hash"] = identity(result["request"])
    result["effects"][0].update(context_id="child", invocation_id="child-inv")
    return summary_from_result(result)


def test_summary_instance_rebinding_composition_and_conservative_widening():
    _, parent_result = request_and_result(status="complete")
    parent = summary_from_result(parent_result)
    call = {"artifact_key": KEY, "function_id": "f", "id": "call"}
    replacements, payload = instantiate_child(child_summary(), "inv", call, "inv")
    assert replacements["child-inv"]["parent_id"] == "inv"
    assert payload["effects"][0]["invocation_id"] == replacements["child-inv"]["id"]
    combined = compose(parent, child_summary(), call)
    assert len(combined["invocations"]) == 2 and len(combined["dependencies"]) == 1
    assert len({effect["id"] for effect in combined["effects"]}) == 2
    widened = conservative_widen(parent, call)
    assert widened["status"] == "partial" and widened["effects"][-1]["kind"] == "unknown"
    assert widened["effects"][-1]["multiplicity"] == "unknown"


def test_scc_fixed_point_converges_and_reports_iteration_cutoff():
    graph = {"a": {"b"}, "b": {"a"}, "c": set()}
    assert strongly_connected(graph) == [("a", "b"), ("c",)]
    values, converged, turns = fixed_point(graph, {"a": {"seed"}},
        lambda node, state: set().union(*(state[target] for target in graph[node])), 4)
    assert converged and values["b"] == {"seed"} and turns >= 1
    values, converged, turns = fixed_point({"a": {"a"}}, {},
        lambda node, state: {str(len(state[node]))}, 1)
    assert not converged and values["a"] and turns == 1


def test_cache_keys_consumption_corruption_and_collision(tmp_path):
    budgets = expected_analysis_protocol()["budgets"]
    keys = [local_key(origin(), budgets), template_key(SCOPE, {"f": 1}, budgets, [], []),
            instance_key("x", [{"id": "i"}]), scc_key(SCOPE, ["a"], ["k"], budgets)]
    assert len(set(keys)) == 4
    cache = DerivedCache(tmp_path / "derived")
    assert cache.load("summaries", keys[0], "EffectSummary") is None
    summary = child_summary(); key = keys[1]
    path = cache.publish("summaries", key, summary)
    assert cache.load("summaries", key, "EffectSummary") == summary
    assert cache.publish("summaries", key, summary) == path
    path.write_text("broken")
    with pytest.raises(AnalysisError) as caught:
        cache.load("summaries", key, "EffectSummary")
    assert caught.value.code == "cache_invalid"
    path.write_text("{}")
    with pytest.raises(AnalysisError) as caught:
        cache.publish("summaries", key, summary)
    assert caught.value.code == "cache_collision"


def test_cache_rejects_escape_and_handles_publish_races(tmp_path, monkeypatch):
    cache = DerivedCache(tmp_path / "derived")
    summary = child_summary()
    with pytest.raises(AnalysisError, match="escapes"):
        cache.load("summaries", "../../../outside", "EffectSummary")

    def same_content_race(source, destination):
        destination.write_text(source.read_text())
        raise FileExistsError

    monkeypatch.setattr(effect_cache.os, "link", same_content_race)
    assert cache.publish("summaries", "race", summary).is_file()
    assert not list((tmp_path / "derived" / "summaries").glob("*.tmp"))

    def conflicting_race(source, destination):
        destination.write_text("{}")
        raise FileExistsError

    monkeypatch.setattr(effect_cache.os, "link", conflicting_race)
    with pytest.raises(AnalysisError) as caught:
        cache.publish("summaries", "conflict", summary)
    assert caught.value.code == "cache_collision"


def test_counts_report_and_zero_denominator():
    assert counts([])["complete_ratio"] is None
    assert aggregate_status([]) == "not_run"
    assert aggregate_status([{"status": "complete"}]) == "complete"
    assert aggregate_status([{"status": "failed"}]) == "failed"
    assert aggregate_status([{"status": "complete"}, {"status": "partial"}]) == "partial"
    inputs, local = fake_inputs()
    inputs.artifacts = {KEY: {"sha256": "2" * 64, "profile": "source-preserving"}}
    local[KEY].update(kind="LocalAnalysisFacts", schema_version=1, analysis_version="0.1.0",
        policy_id="scoped-effects-v1", origin=origin(), budgets=expected_analysis_protocol()["budgets"],
        objects=[], ir_nodes=[], analysis_evidence=[], resolutions=[], diagnostics=[], status="partial")
    request = effect_document("EffectAnalysisRequest", scope="scope.json", mode="all-defined", roots=[],
                              budgets=expected_analysis_protocol()["budgets"])
    report = build_report(inputs, request, local, {"roots": [child_summary()],
        "contexts": {"child": child_summary()}, "failures": [], "cache_hits": 0}, [])
    assert report["safety"] == "not_evaluated" and report["findings"] is None
    assert report["input_integrity"] == "complete" and report["local_analysis"] == "partial"
    assert report["raw_fact_extraction"] == "complete" and report["exit_code"] == 2

    inputs.modules[KEY]["extraction"] = {"status": "partial", "diagnostics": [
        {"id": "call", "reason": "uninterpreted_abi_attributes"},
        {"id": "other", "reason": "unsupported_value"}]}
    context = child_summary()
    context["root"]["function_id"] = "caller"
    explained = build_report(inputs, request, local, {"roots": [context],
        "contexts": {"child": context}, "failures": [], "cache_hits": 0}, [])
    assert explained["raw_fact_extraction"] == "partial"
    assert {item["code"] for item in explained["diagnostics"]} >= {
        "uninterpreted_abi_attributes", "unsupported_value"}
    assert explained["resolutions"][0]["reason"] == "uninterpreted_abi_attributes"
    assert explained["resolutions"][0]["rule"] == "supported-c-call-interface-v1"


def test_select_roots_modes_argument_validation_and_scheduler_budget_summary():
    inputs, local = fake_inputs()
    budgets = expected_analysis_protocol()["budgets"]
    request = effect_document("EffectAnalysisRequest", scope="scope.json", mode="roots",
        roots=[{"artifact_key": KEY, "function_id": "f", "arguments": [{"kind": "integer", "bits": 32, "hex": "1"}]}], budgets=budgets)
    selected = select_roots(inputs, request)
    assert selected[0][1][0]["state"] == "finite"
    all_defined = effect_document("EffectAnalysisRequest", scope="scope.json", mode="all-defined", roots=[], budgets=budgets)
    assert len(select_roots(inputs, all_defined)) == 2
    invalid = deepcopy(request); invalid["roots"][0]["function_id"] = "missing"
    with pytest.raises(AnalysisError):
        select_roots(inputs, invalid)
    local[KEY].update(origin=origin(), budgets=budgets)
    inputs.artifacts = {KEY: {"sha256": "2" * 64, "profile": "source-preserving"}}
    inputs.scope_id = SCOPE
    scheduler = Scheduler(inputs, local, [], "worker", SimpleNamespace(), {**budgets, "contexts_per_function": 1},
                          evaluator=lambda *a, **k: {})
    function = {"artifact_key": KEY, "function_id": None, "id": "f"}
    scheduler.per_function[KEY, "f"] = 1
    summary = scheduler.analyze(function, [unknown("x")])
    assert summary["status"] == "failed" and summary["diagnostics"][0]["code"] == "contexts_per_function_budget"
    wrong = deepcopy(request); wrong["roots"][0]["arguments"] = []
    selected = select_roots(inputs, wrong)
    assert selected[0][1][0]["state"] == "unknown"
    empty = deepcopy(all_defined)
    for function in inputs.modules[KEY]["functions"]:
        function["declaration"] = True
    with pytest.raises(AnalysisError, match="selected no"):
        select_roots(inputs, empty)


def scheduler_fixture(tmp_path):
    inputs, local = fake_inputs()
    inputs.artifacts = {KEY: {"sha256": "2" * 64, "profile": "source-preserving"}}
    inputs.scope_id = SCOPE
    values = []
    for function in inputs.modules[KEY]["functions"]:
        parameter = function["parameters"][0]
        values.append({"id": parameter, "kind": "argument", "type": "i32", "type_kind": "integer",
                       "function": function["id"], "block": None, "operands": [],
                       "details": {"position": 0}, "status": "known"})
    inputs.modules[KEY]["values"] = values
    local[KEY].update(origin=origin(), budgets=expected_analysis_protocol()["budgets"])
    adoption = {"call": {"artifact_key": KEY, "function_id": "caller", "id": "call"},
                "target": {"artifact_key": KEY, "function_id": None, "id": "f"},
                "kind": "unique-definition", "reason": "exact", "assumptions": []}
    store = SimpleNamespace(root=tmp_path)
    return inputs, local, adoption, store


def fake_evaluator(inputs, requests, worker, store, *, local_facts, summaries):
    request = requests[0]
    call_source = {"artifact_key": KEY, "function_id": "caller", "id": "call"}
    is_caller = request["function"]["id"] == "caller"
    diagnostic = {"code": "unknown_call_effect", "detail": "pending", "source": call_source,
                  "context_id": request["context_id"]}
    effect_source = call_source if is_caller else {"artifact_key": KEY, "function_id": "f", "id": "event"}
    effect = {"id": "effect", "source": effect_source, "context_id": request["context_id"],
              "invocation_id": request["invocation_id"], "kind": "unknown" if is_caller else "write",
              "address": None, "size_bytes": "4", "value": {"kind": "integer", "bits": 32, "hex": "7"},
              "atomic": False, "volatile": False, "ordering": None, "failure_ordering": None,
              "syncscope": None, "visibility": "unknown", "guards": [], "occurrence": "may",
              "multiplicity": "single", "proof": [], "call_path": []}
    calls = [{"source": call_source, "arguments": [finite({"kind": "integer", "bits": 32, "hex": "7"})],
              "guards": []}] if is_caller else []
    result = effect_document("LocalEvaluationResult", request=request, request_hash=identity(request),
        scope_id=SCOPE, context_id=request["context_id"], budgets=request["budgets"], values=[], blocks=[],
        call_requests=calls, effects=[effect], order=[], returns=[], escape=[], resolutions=[],
        frontier=[diagnostic] if is_caller else [], diagnostics=[diagnostic] if is_caller else [],
        status="partial" if is_caller else "complete", steps=1)
    return {identity(request): {"id": identity(request), "result": result, "error": None}}


def test_scheduler_composes_calls_cache_errors_recursion_and_request_budgets(tmp_path):
    inputs, local, adoption, store = scheduler_fixture(tmp_path)
    budgets = expected_analysis_protocol()["budgets"]
    scheduler = Scheduler(inputs, local, [adoption], "worker", store, budgets, evaluator=fake_evaluator)
    root = {"artifact_key": KEY, "function_id": None, "id": "caller"}
    summary = scheduler.analyze(root, [finite({"kind": "integer", "bits": 32, "hex": "1"})])
    assert summary["status"] == "complete" and len(summary["invocations"]) == 2
    assert any(effect["kind"] == "write" for effect in summary["effects"])
    assert scheduler.analyze(root, [finite({"kind": "integer", "bits": 32, "hex": "1"})]) == summary
    assert scheduler._template_arguments(root, [finite({"kind": "integer", "bits": 32, "hex": "1"})])[0]["state"] == "finite"

    unknown_adoption = deepcopy(adoption)
    unknown_adoption.update(kind="unknown", target=None, reason="indirect_call")
    unknown_scheduler = Scheduler(inputs, local, [unknown_adoption], "worker", store, budgets,
                                  evaluator=fake_evaluator)
    assert unknown_scheduler.graph[KEY, "caller"] == set()

    recursive = deepcopy(adoption); recursive["target"]["id"] = "caller"
    recursion = Scheduler(inputs, local, [recursive], "worker", store, budgets, evaluator=fake_evaluator)
    widened = recursion.analyze(root, [unknown("x")])
    assert widened["status"] == "partial" and widened["effects"][-1]["kind"] == "unknown"

    def failed(*args, **kwargs):
        request = args[1][0]
        return {identity(request): {"id": identity(request), "result": None,
                                    "error": {"code": "worker_failed", "detail": "no result"}}}
    failure = Scheduler(inputs, local, [], "worker", store, budgets, evaluator=failed)
    assert failure.analyze(root, [unknown("x")])["status"] == "failed"
    assert failure.failures[0]["code"] == "worker_failed"

    clock_values = iter([0, budgets["request_seconds"] + 1])
    timed = Scheduler(inputs, local, [], "worker", store, budgets, evaluator=fake_evaluator,
                      clock=lambda: next(clock_values))
    with pytest.raises(AnalysisError) as caught:
        timed.analyze(root, [unknown("x")])
    assert caught.value.code == "request_timed_out"
    for field, value, code in [("bytes", budgets["request_output_bytes"] + 1, "request_output_limit")]:
        limited = Scheduler(inputs, local, [], "worker", store, budgets, evaluator=fake_evaluator)
        setattr(limited, field, value)
        with pytest.raises(AnalysisError) as caught:
            limited.analyze(root, [unknown("x")])
        assert caught.value.code == code
    limited = Scheduler(inputs, local, [], "worker", store, {**budgets, "contexts_per_request": 1}, evaluator=fake_evaluator)
    limited.contexts["existing"] = summary
    with pytest.raises(AnalysisError) as caught:
        limited.analyze(root, [unknown("x")])
    assert caught.value.code == "context_budget"

    pointer_inputs, pointer_local, pointer_adoption, pointer_store = scheduler_fixture(tmp_path / "pointer")
    for value in pointer_inputs.modules[KEY]["values"]:
        if value["id"] == "f:arg0":
            value.update(type="ptr", type_kind="pointer", address_space=0)
    pointer_scheduler = Scheduler(pointer_inputs, pointer_local, [pointer_adoption], "worker", pointer_store,
                                  budgets, evaluator=fake_evaluator)
    templated = pointer_scheduler._template_arguments(
        {"artifact_key": KEY, "function_id": None, "id": "f"}, [unknown("actual")])
    assert templated[0]["candidates"][0]["value"]["kind"] == "parameter"


def test_scheduler_child_budget_failure_and_scc_cutoff_are_conservative(tmp_path):
    inputs, local, adoption, store = scheduler_fixture(tmp_path)
    budgets = expected_analysis_protocol()["budgets"]

    def child_fails(inputs_, requests, worker, output, **kwargs):
        if requests[0]["function"]["id"] == "f":
            raise AnalysisError("context_budget", "child limit")
        return fake_evaluator(inputs_, requests, worker, output, **kwargs)

    scheduler = Scheduler(inputs, local, [adoption], "worker", store, budgets, evaluator=child_fails)
    result = scheduler.analyze({"artifact_key": KEY, "function_id": None, "id": "caller"}, [unknown("root")])
    assert result["status"] == "partial"
    assert any(item["code"] == "context_budget" for item in result["diagnostics"])

    request = effect_document("EffectAnalysisRequest", scope="scope.json", mode="roots",
        roots=[{"artifact_key": KEY, "function_id": "caller", "arguments": []}],
        budgets={**budgets, "scc_iterations": 1})
    cutoff = run_scheduler(inputs, request, local, [adoption], "worker", store, evaluator=fake_evaluator)
    assert cutoff["scc"]["converged"] is False
    assert cutoff["roots"][0]["status"] == "partial"
    assert any(item["code"] == "scc_iteration_budget" for item in cutoff["roots"][0]["diagnostics"])


def test_run_scheduler_catches_root_failure_and_uses_cache(tmp_path):
    inputs, local, adoption, store = scheduler_fixture(tmp_path)
    request = effect_document("EffectAnalysisRequest", scope="scope.json", mode="roots",
        roots=[{"artifact_key": KEY, "function_id": "caller", "arguments": [{"kind": "integer", "bits": 32, "hex": "1"}]}],
        budgets=expected_analysis_protocol()["budgets"])
    result = run_scheduler(inputs, request, local, [adoption], "worker", store,
                           cache_root=tmp_path / "cache", evaluator=fake_evaluator)
    assert result["roots"] and not result["failures"]
    cached = run_scheduler(inputs, request, local, [adoption], "worker", store,
                           cache_root=tmp_path / "cache", evaluator=lambda *a, **k: pytest.fail("cache miss"))
    assert cached["cache_hits"] == 1

    def raises(*args, **kwargs):
        raise AnalysisError("unexpected", "broken evaluator")
    failed = run_scheduler(inputs, request, local, [], "worker", store, evaluator=raises)
    assert failed["failures"][0]["code"] == "unexpected"


def test_summary_order_nested_rebinding_duplicate_dependencies_and_dag_paths():
    _, result = request_and_result(status="complete")
    second = deepcopy(result["effects"][0]); second["id"] = "second"
    result["effects"].append(second)
    result["order"] = [{"before": "raw-effect", "after": "second", "guards": []}]
    summary = summary_from_result(result)
    assert summary["order"][0]["before"] != "raw-effect"

    child = child_summary()
    child["root"]["arguments"][0] = {"kind": "parameter", "source": {
        "artifact_key": KEY, "function_id": "f", "id": "f:arg0"}, "invocation_id": None}
    nested = deepcopy(child["invocations"][0])
    nested.update(id="nested", parent_id="child-inv",
                  callsite={"artifact_key": KEY, "function_id": "f", "id": "nested-call"})
    child["invocations"].append(nested)
    foreign = {"kind": "parameter", "source": {"artifact_key": OTHER, "function_id": "outer", "id": "p"},
               "invocation_id": "child-inv"}
    child["escape"].append(foreign)
    multi = {"state": "finite", "candidates": [finite({"kind": "integer", "bits": 32, "hex": "1"})["candidates"][0],
                                                   finite({"kind": "integer", "bits": 32, "hex": "2"})["candidates"][0]],
             "reason": None}
    replacements, payload = instantiate_child(child, "inv", {"artifact_key": KEY, "function_id": "f", "id": "call"},
                                               "inv", arguments=[multi])
    assert replacements["nested"]["parent_id"] == replacements["child-inv"]["id"]
    assert payload["escape"][0]["invocation_id"] == "inv"

    _, parent_result = request_and_result(status="complete")
    parent = summary_from_result(parent_result)
    partial = conservative_widen(child_summary(), {"artifact_key": KEY, "function_id": "f", "id": "call"})
    combined = compose(parent, partial, {"artifact_key": KEY, "function_id": "f", "id": "call"})
    combined_again = compose(combined, child_summary(), {"artifact_key": KEY, "function_id": "f", "id": "call2"})
    assert combined_again["status"] == "partial"
    assert len(combined_again["local_dependencies"]) == len({identity(item) for item in combined_again["local_dependencies"]})
    assert strongly_connected({"a": {"b"}, "b": set()}) == [("b",), ("a",)]
    values, converged, turns = fixed_point({"a": set()}, {}, lambda node, state: set(), 2)
    assert converged and values == {"a": set()} and turns == 1
