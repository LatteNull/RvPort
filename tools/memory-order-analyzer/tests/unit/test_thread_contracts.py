"""P3 contract, identity, cache, model and report unit coverage."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
import memory_order_analyzer.thread_cache as cache_module

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.thread_cache import (
    ThreadCache, context_template_key, graph_key, local_thread_key,
)
from memory_order_analyzer.thread_contracts import (
    KINDS, diagnostic, expected_thread_protocol, read_thread_document,
    thread_context_id, thread_document, thread_instance_id,
    validate_thread_document,
)
from memory_order_analyzer.thread_models import MODELS, MODEL_ID, adopt_all, adopt_call
from memory_order_analyzer.thread_report import aggregate, build_thread_report, counts, failed_thread_report


A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


def ref(name, function="main", artifact=A):
    return {"artifact_key": artifact, "function_id": function, "id": name}


def origin(artifact=A):
    return {"artifact_key": artifact, "module_hash": B, "facts_hash": C,
            "profile": "source-preserving", "extractor_version": "0.2.0",
            "llvm_version": "21.1.8"}


def budgets(**changes):
    value = deepcopy(expected_thread_protocol()["budgets"])
    value.update(changes)
    return value


def request():
    return thread_document(
        "ThreadAnalysisRequest", scope="scope.json",
        roots=[{"artifact_key": A, "function_id": "main", "arguments": []}],
        model_id=MODEL_ID, budgets=budgets(),
    )


def call(symbol="pthread_create", **changes):
    source = ref("call")
    values = {
        "source": source, "function": ref("main", None), "symbol": symbol,
        "direct": True, "function_type": "i32 (ptr, ptr, ptr, ptr)",
        "calling_convention": 0, "arguments": [ref("tid"), None, ref("worker", None), None],
        "result": source, "normal_successor": ref("next"), "unwind_successor": None,
        "noreturn": False, "success_test": ref("ok"),
        "callback_metadata": [[2, 3, 0]], "callback_targets": [ref("worker", None)],
        "handle_source": ref("tid"), "mutex_source": None, "mutex_initializer": None,
        "status": "candidate", "reason": None,
    }
    values.update(changes)
    return values


def local(calls=(), *, status="complete", artifact=A):
    return thread_document(
        "ThreadLocalFacts", origin=origin(artifact), budgets=budgets(), calls=list(calls),
        provenance=[], analysis_evidence=[], diagnostics=[], frontier=[], status=status,
    )


def order(*, status="complete", artifact=A):
    return thread_document(
        "ExecutionOrderFacts", origin=origin(artifact), budgets=budgets(), nodes=[], edges=[],
        analysis_evidence=[], diagnostics=[], frontier=[], status=status,
    )


def graph(*, status="complete"):
    context = {"id": "context", "entry": ref("main", None), "arguments": [],
               "status": status, "reason": None if status == "complete" else "unit",
               "dependency": None}
    instance = {"id": "instance", "root_id": "root", "context_id": "context",
                "parent_id": None, "create": None, "cardinality": "single", "reason": None}
    lifecycle = {"id": "start", "kind": "root-start", "thread_instance_id": "instance",
                 "source": ref("main", None), "guards": [], "status": "must",
                 "proof": [ref("main", None)]}
    return thread_document(
        "ThreadContextGraph", scope_id=D, request_hash=C, model_id=MODEL_ID,
        budgets=budgets(), dependencies=[], contexts=[context], instances=[instance],
        lifecycles=[lifecycle], effects=[], anchors=[], order=[], mhp=[], synchronization=[],
        frontier=[], diagnostics=[], status=status,
    )


def report_sample():
    zero = {"planned": 0, "complete": 0, "partial": 0, "failed": 0,
            "not_run": 0, "complete_ratio": None}
    return thread_document(
        "ThreadAnalysisReport", request_hash=None, scope_id=None, model_id=MODEL_ID,
        budgets=budgets(), input_integrity="not_run", effect_analysis="not_run",
        local_thread_analysis="not_run", thread_modeling="not_run",
        synchronization_analysis="not_run", source_mapping="not_run", members=[], roots=[],
        contexts=[], member_counts=zero, root_counts=zero, context_counts=zero, graph=None,
        dependencies=[], frontier=[], diagnostics=[], assumptions=[], safety="not_evaluated",
        findings=None, exit_code=1,
    )


def samples():
    return {
        "ThreadAnalysisRequest": request(), "ThreadLocalFacts": local(),
        "ExecutionOrderFacts": order(), "ThreadContextGraph": graph(),
        "ThreadAnalysisReport": report_sample(),
    }


def test_protocol_schema_roundtrip_and_bilingual_pair(tmp_path):
    protocol = expected_thread_protocol()
    assert protocol["kinds"] == dict.fromkeys(KINDS, 1)
    assert protocol["model_id"] == MODEL_ID and protocol["budgets"]["graph_items"] == 100000
    for kind, value in samples().items():
        path = tmp_path / f"{kind}.json"
        path.write_text(canonical(value), encoding="utf-8")
        assert read_thread_document(path, kind) == value
        assert validate_thread_document(value, kind) is value
        invalid = deepcopy(value); invalid["extra"] = True
        with pytest.raises(AnalysisError, match="Additional properties"):
            validate_thread_document(invalid, kind)
    for value in (None, [], {"schema_version": True}):
        with pytest.raises(AnalysisError):
            validate_thread_document(value, "ThreadAnalysisRequest")
    with pytest.raises(AnalysisError, match="Unknown thread contract"):
        validate_thread_document(request(), "future")
    invalid = failed_thread_report("unit", "detail")
    invalid["diagnostics"][0]["suggestion_en"] = None
    with pytest.raises(AnalysisError):
        validate_thread_document(invalid, "ThreadAnalysisReport")
    item = diagnostic("unit", "中文", "English", source=ref("x"), context="c", instance="i")
    assert item["detail_en"] == "English" and item["suggestion"] is None


def test_protocol_and_json_failures(tmp_path, monkeypatch):
    missing = tmp_path / "missing.json"
    with pytest.raises(AnalysisError, match="Invalid or missing JSON"):
        expected_thread_protocol(missing)
    malformed = tmp_path / "bad.json"; malformed.write_text("[")
    with pytest.raises(AnalysisError):
        expected_thread_protocol(malformed)
    changed = deepcopy(expected_thread_protocol()); changed["analysis_version"] = "future"
    path = tmp_path / "changed.json"; path.write_text(json.dumps(changed))
    with pytest.raises(AnalysisError, match="does not match"):
        expected_thread_protocol(path)
    source = tmp_path / "request.json"; source.write_text("[]")
    with pytest.raises(AnalysisError):
        read_thread_document(source, "ThreadAnalysisRequest")


def test_semantic_reference_rejections():
    value = local([call()])
    duplicate = deepcopy(value); duplicate["calls"] *= 2
    with pytest.raises(AnalysisError, match="Duplicate thread call"):
        validate_thread_document(duplicate, "ThreadLocalFacts")
    foreign = deepcopy(value); foreign["calls"][0]["source"]["artifact_key"] = D
    with pytest.raises(AnalysisError, match="Foreign"):
        validate_thread_document(foreign, "ThreadLocalFacts")

    node1 = {"source": ref("one"), "block": ref("bb"), "index": 0,
             "kind": "load", "multiplicity": "single"}
    node2 = {**deepcopy(node1), "source": ref("two"), "index": 1}
    edge = {"id": "edge", "before": ref("one"), "after": ref("two"),
            "relation": "must-before", "guards": [], "proof": [ref("one")],
            "reason": "same-block-order"}
    ordered = thread_document("ExecutionOrderFacts", origin=origin(), budgets=budgets(),
                              nodes=[node1, node2], edges=[edge], analysis_evidence=[],
                              diagnostics=[], frontier=[],
                              status="complete")
    for mutate, match in [
        (lambda v: v["nodes"].append(deepcopy(v["nodes"][0])), "Duplicate execution"),
        (lambda v: v["edges"].append(deepcopy(v["edges"][0])), "Duplicate execution-order edge"),
        (lambda v: v["edges"][0].update(after=ref("absent")), "dangling endpoint"),
    ]:
        invalid = deepcopy(ordered); mutate(invalid)
        with pytest.raises(AnalysisError, match=match):
            validate_thread_document(invalid, "ExecutionOrderFacts")


def test_analysis_evidence_namespace_owner_closure_and_cycles():
    source = ref("call")
    analysis = {"artifact_key": A, "function_id": "main", "analysis_id": "proof"}
    evidence = {"ref": analysis, "kind": "pthread-call-eligibility", "source": source,
                "inputs": [source], "result": "candidate"}
    value = local([call()]); value["analysis_evidence"] = [evidence]
    value["provenance"] = [{"source": ref("load"), "kind": "load", "value": None,
                            "object": None, "proof": [analysis], "status": "unknown",
                            "reason": "unit"}]
    assert validate_thread_document(value, "ThreadLocalFacts") is value
    mutations = [
        lambda v: v["analysis_evidence"].append(deepcopy(v["analysis_evidence"][0])),
        lambda v: v["analysis_evidence"][0]["ref"].update(artifact_key=D),
        lambda v: v["analysis_evidence"][0]["ref"].update(function_id="other"),
        lambda v: v["analysis_evidence"][0].update(inputs=[{"artifact_key": A, "function_id": "main", "analysis_id": "missing"}]),
        lambda v: v["analysis_evidence"][0].update(inputs=[ref("foreign", artifact=D)]),
        lambda v: v["provenance"][0].update(proof=[{"artifact_key": A, "function_id": "main", "analysis_id": "missing"}]),
    ]
    for mutate in mutations:
        invalid = deepcopy(value); mutate(invalid)
        with pytest.raises(AnalysisError):
            validate_thread_document(invalid, "ThreadLocalFacts")

    before, after = ref("before"), ref("after")
    order_proof = {"artifact_key": A, "function_id": "main", "analysis_id": "edge"}
    evidence = {"ref": order_proof, "kind": "execution-order", "source": before,
                "inputs": [before, after], "result": "must-before"}
    ordered = thread_document(
        "ExecutionOrderFacts", origin=origin(), budgets=budgets(),
        nodes=[{"source": before, "block": ref("bb"), "index": 0, "kind": "load", "multiplicity": "single"},
               {"source": after, "block": ref("bb"), "index": 1, "kind": "store", "multiplicity": "single"}],
        edges=[{"id": "edge", "before": before, "after": after, "relation": "must-before",
                "guards": [], "proof": [order_proof], "reason": "same-block-order"}],
        analysis_evidence=[evidence], diagnostics=[], frontier=[], status="complete")
    assert validate_thread_document(ordered, "ExecutionOrderFacts") is ordered
    ordered["analysis_evidence"] = []
    with pytest.raises(AnalysisError, match="missing analysis evidence"):
        validate_thread_document(ordered, "ExecutionOrderFacts")


@pytest.mark.parametrize("mutation,match", [
    (lambda g: g["contexts"].append(deepcopy(g["contexts"][0])), "Duplicate thread context"),
    (lambda g: g["instances"][0].update(context_id="absent"), "dangling context"),
    (lambda g: g["instances"][0].update(parent_id="absent"), "parent is dangling"),
    (lambda g: g["instances"][0].update(cardinality="merged"), "abstraction reason"),
    (lambda g: g["lifecycles"][0].update(thread_instance_id="absent"), "dangling instance"),
    (lambda g: g.update(instances=[]), "dangling instance"),
])
def test_graph_semantic_rejections(mutation, match):
    value = graph(); mutation(value)
    with pytest.raises(AnalysisError, match=match):
        validate_thread_document(value, "ThreadContextGraph")


def test_graph_endpoint_pair_and_merged_rejections():
    value = graph()
    value["anchors"] = [{"id": "anchor", "kind": "function-entry", "source": ref("main", None),
                         "invocation_id": "inv", "thread_instance_id": "instance",
                         "status": "must", "proof": [ref("main", None)]}]
    value["order"] = [{"id": "edge", "kind": "intra-thread", "before": "anchor",
                       "after": "missing", "relation": "must-before", "guards": [],
                       "proof": [ref("main", None)]}]
    with pytest.raises(AnalysisError, match="dangling endpoint"):
        validate_thread_document(value, "ThreadContextGraph")
    value = graph(); value["instances"].append({**deepcopy(value["instances"][0]),
        "id": "second", "parent_id": "instance", "create": ref("call")})
    value["mhp"] = [{"id": "m", "left": "second", "right": "instance",
                     "left_endpoint": None, "right_endpoint": None, "relation": "may_parallel",
                     "guards": [], "proof": [], "reason": "unit"}]
    with pytest.raises(AnalysisError, match="not canonical"):
        validate_thread_document(value, "ThreadContextGraph")
    value = graph(); value["instances"][0].update(cardinality="merged", reason="loop")
    with pytest.raises(AnalysisError, match="Merged instances"):
        validate_thread_document(value, "ThreadContextGraph")


def test_stable_identity_keys_and_cache(tmp_path):
    entry, args, limits = ref("main", None), [], budgets()
    assert thread_context_id(D, entry, args, MODEL_ID, limits) == thread_context_id(D, entry, args, MODEL_ID, limits)
    assert thread_instance_id("root", "ctx", None, None, "single", None) != thread_instance_id("root", "ctx", "p", ref("c"), "single", None)
    assert local_thread_key(origin(), limits, MODEL_ID) != local_thread_key(origin(), {**limits, "local_steps": 2}, MODEL_ID)
    assert context_template_key(D, entry, args, limits, MODEL_ID, [B, A]) == context_template_key(D, entry, args, limits, MODEL_ID, [A, B])
    assert graph_key(request(), [B, A]) == graph_key(request(), [A, B])
    cache = ThreadCache(tmp_path / "cache")
    value = graph()
    assert cache.load("graphs", C, "ThreadContextGraph") is None
    path = cache.publish("graphs", C, value)
    assert cache.load("graphs", C, "ThreadContextGraph") == value
    assert cache.publish("graphs", C, value) == path
    path.write_text("{}")
    with pytest.raises(AnalysisError, match="Invalid thread cache"):
        cache.load("graphs", C, "ThreadContextGraph")
    path.write_text("different")
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("graphs", C, value)
    with pytest.raises(AnalysisError):
        cache.publish("graphs", D, None)
    with pytest.raises(AnalysisError, match="escapes root"):
        cache.load("../../../escape", C, "ThreadContextGraph")


def test_cache_publish_handles_atomic_create_races(tmp_path, monkeypatch):
    cache = ThreadCache(tmp_path / "cache")
    value = graph()
    real_link = cache_module.os.link

    def same_race(source, destination):
        real_link(source, destination)
        raise FileExistsError(destination)

    monkeypatch.setattr(cache_module.os, "link", same_race)
    path = cache.publish("graphs", A, value)
    assert json.loads(path.read_text()) == value

    def conflicting_race(source, destination):
        destination.write_text("different")
        raise FileExistsError(destination)

    monkeypatch.setattr(cache_module.os, "link", conflicting_race)
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("graphs", B, value)


@pytest.mark.parametrize("changes,kind,reason", [
    ({}, "adopted", None),
    ({"direct": False}, "unknown", "pthread-call-ineligible"),
    ({"status": "unknown"}, "unknown", "pthread-call-ineligible"),
    ({"arguments": []}, "unknown", "pthread-call-ineligible"),
    ({"callback_metadata": [[1, 2]]}, "unknown", "callback-metadata-conflict"),
    ({"callback_targets": []}, "unknown", "callback-target-unknown"),
])
def test_create_model_adoption(changes, kind, reason):
    result = adopt_call(call(**changes))
    assert result["kind"] == kind and result["reason"] == reason
    assert result["event"] == "create" and result["roles"] == MODELS["pthread_create"]["roles"]


def test_mutex_unknown_and_unsupported_models_are_diagnostic():
    mutex = call("pthread_mutex_lock", arguments=[ref("mutex")], callback_targets=[],
                 callback_metadata=[], handle_source=None, mutex_source=ref("mutex"),
                 mutex_initializer="zero-static:" + "a" * 64, function_type="i32 (ptr)")
    assert adopt_call(mutex)["kind"] == "adopted"
    assert adopt_call({**mutex, "mutex_initializer": None})["reason"] == "mutex-kind-unknown"
    assert adopt_call({**mutex, "mutex_initializer": "zero-static:" + "z" * 64})["kind"] == "unknown"
    unknown = adopt_call(call("custom_api", callback_targets=[]))
    assert unknown["kind"] == "unknown" and unknown["event"] is None and unknown["roles"] == {}
    create = call(callback_targets=[])
    detach = call("pthread_detach", source=ref("detach"), result=ref("detach"),
                  callback_targets=[], callback_metadata=[], arguments=[ref("tid")])
    future = call("pthread_future", source=ref("future"), result=ref("future"),
                  callback_targets=[], callback_metadata=[], arguments=[])
    facts = {A: local([create, detach, future])}
    adoptions, diagnostics = adopt_all(facts)
    assert len(adoptions) == 3
    assert {item["code"] for item in diagnostics} == {"callback-target-unknown", "pthread-api-unsupported"}
    assert all(item["detail"] and item["detail_en"] for item in diagnostics)


def test_report_counts_statuses_and_exit_codes():
    assert counts([])["complete_ratio"] is None
    assert counts([{"status": "complete"}, {"status": "partial"}])["complete_ratio"] == .5
    assert aggregate([]) == "not_run"
    assert aggregate([{"status": "complete"}]) == "complete"
    assert aggregate([{"status": "failed"}]) == "failed"
    assert aggregate([{"status": "complete"}, {"status": "failed"}]) == "partial"
    failed = failed_thread_report("unit", "x" * 5000)
    assert failed["exit_code"] == 1
    assert len(failed["frontier"][0]["detail"]) == 1024
    assert len(failed["frontier"][0]["detail_en"]) == 1024
    inputs = SimpleNamespace(scope={"members": [A]}, scope_id=D,
                             modules={A: {"source_mapping": "complete"}})
    value = graph()
    complete = build_thread_report(inputs, request(), value, {A: local()}, {A: order()},
                                   {"interprocedural_analysis": "complete"})
    assert complete["exit_code"] == 0 and complete["safety"] == "not_evaluated" and complete["findings"] is None
    partial_graph = deepcopy(value); partial_graph["status"] = "partial"
    partial_graph["contexts"][0].update(status="partial", reason="unit")
    partial = build_thread_report(inputs, request(), partial_graph, {A: local(status="partial")},
                                  {A: order()}, {"interprocedural_analysis": "partial"})
    assert partial["exit_code"] == 2 and partial["local_thread_analysis"] == "partial"
    inputs.modules[A]["source_mapping"] = "unavailable"
    assert build_thread_report(inputs, request(), value, {A: local()}, {A: order()}, {})["source_mapping"] == "unavailable"
    failed = failed_thread_report("unit", "broken", budgets=budgets())
    assert failed["exit_code"] == 1 and failed["diagnostics"][0]["detail_en"].startswith("Thread")
