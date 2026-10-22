"""Finite thread graph semantics, boundaries and conservative candidates."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.thread_contracts import thread_document, validate_thread_document
from memory_order_analyzer.thread_graph import (
    ThreadGraphBuilder, _argument, _object_range, _ranges_disjoint, build_thread_graph,
)
from test_thread_contracts import A, B, budgets, call, local, order, ref, request


def invocation(identifier, function, parent=None, callsite=None):
    return {"id": identifier, "context_id": f"ctx-{function}",
            "function": ref(function, None), "parent_id": parent,
            "callsite": deepcopy(callsite), "cardinality": "single", "reason": None}


def effect(identifier, source, invocation_id, kind, address, *, atomic=False, value=None):
    return {"id": identifier, "source": deepcopy(source), "context_id": f"ctx-{invocation_id}",
            "invocation_id": invocation_id, "kind": kind, "address": deepcopy(address),
            "size_bytes": None if kind == "fence" else "4", "value": deepcopy(value),
            "atomic": atomic, "volatile": False,
            "ordering": "release" if kind in {"write", "rmw", "cas"} and atomic else
                        "acquire" if kind == "read" and atomic else None,
            "failure_ordering": "monotonic" if kind == "cas" else None,
            "syncscope": "system" if atomic else None, "visibility": "observable",
            "guards": [], "occurrence": "may", "multiplicity": "single",
            "proof": [], "call_path": []}


def summary(function, effects=(), invocations=None, *, status="complete", order_edges=()):
    invocations = invocations or [invocation(f"{function}-inv", function)]
    return {"context_id": f"summary-{function}",
            "root": {"artifact_key": A, "function_id": function, "arguments": []},
            "invocations": deepcopy(invocations), "effects": deepcopy(list(effects)),
            "order": deepcopy(list(order_edges)), "status": status}


def call_for(symbol, source_name, function="main", **changes):
    source = ref(source_name, function)
    defaults = {"source": source, "result": source,
                "function": ref(function, None), "callback_targets": [],
                "callback_metadata": [], "success_test": ref(source_name + "-ok", function)}
    if symbol == "pthread_create":
        defaults.update(arguments=[ref("tid", function), None, ref("worker", None), ref("arg", function)],
                        callback_targets=[ref("worker", None)], callback_metadata=[[2, 3, 0]],
                        handle_source=ref("tid", function))
    elif symbol == "pthread_join":
        defaults.update(arguments=[ref("loaded-tid", function), None],
                        handle_source=ref("loaded-tid", function), function_type="i32 (i64, ptr)")
    elif symbol.startswith("pthread_mutex_"):
        defaults.update(arguments=[ref("mutex", None)], mutex_source=ref("mutex", None),
                        mutex_initializer="zero-static:" + "a" * 64, function_type="i32 (ptr)")
    else:
        defaults.update(arguments=[], function_type="void ()", status="unknown", reason="unmodeled-direct-call")
    defaults.update(changes)
    return call(symbol, **defaults)


def node(source, index=0, multiplicity="single"):
    return {"source": deepcopy(source), "block": ref("bb", source["function_id"]),
            "index": index, "kind": "call", "multiplicity": multiplicity}


def edge(identifier, before, after, relation="must-before"):
    return {"id": identifier, "before": deepcopy(before), "after": deepcopy(after),
            "relation": relation, "guards": [], "proof": [deepcopy(before)],
            "reason": "unit-order"}


def scenario(*, request_changes=None, recursive=False, include_clobber=False):
    create = call_for("pthread_create", "create")
    if recursive:
        create["callback_targets"] = [ref("main", None)]
        create["arguments"][2] = ref("main", None)
    join = call_for("pthread_join", "join")
    main_lock = call_for("pthread_mutex_lock", "main-lock")
    main_unlock = call_for("pthread_mutex_unlock", "main-unlock")
    worker_lock = call_for("pthread_mutex_lock", "worker-lock", "worker")
    worker_unlock = call_for("pthread_mutex_unlock", "worker-unlock", "worker")
    helper = call_for("helper", "helper-call", unwind_successor=ref("helper-unwind"))
    calls = [create, main_lock, main_unlock, join, helper, worker_lock, worker_unlock]
    provenance = [{"source": ref("loaded-tid"), "kind": "load", "value": ref("loaded-tid"),
                   "object": ref("tid"), "proof": [ref("loaded-tid")],
                   "status": "candidate", "reason": None}]
    if include_clobber:
        provenance.append({"source": ref("clobber"), "kind": "clobber", "value": None,
                           "object": None, "proof": [ref("clobber")],
                           "status": "unknown", "reason": "indirect-call"})
    local_facts = {A: thread_document("ThreadLocalFacts", origin=local()["origin"], budgets=budgets(),
        calls=calls, provenance=provenance, analysis_evidence=[], diagnostics=[], frontier=[], status="complete")}
    after, worker_read = ref("after"), ref("worker-read", "worker")
    sources = [create["source"], main_lock["source"], main_unlock["source"], join["source"],
               helper["source"], after, worker_lock["source"], worker_unlock["source"], worker_read]
    nodes = [node(source, index) for index, source in enumerate(sources)]
    order_edges = [edge("create-join", create["source"], join["source"]),
                   edge("join-after", join["source"], after),
                   edge("main-lock-unlock", main_lock["source"], main_unlock["source"]),
                   edge("worker-lock-unlock", worker_lock["source"], worker_unlock["source"]),
                   edge("exclusive", helper["source"], after, "mutually-exclusive")]
    order_facts = {A: thread_document("ExecutionOrderFacts", origin=local()["origin"], budgets=budgets(),
        nodes=nodes, edges=order_edges, analysis_evidence=[], diagnostics=[], frontier=[], status="complete")}
    address = {"kind": "object", "source": ref("shared", None), "offset": "0",
               "address_space": 0, "allocation": None}
    main_effect = effect("main-write", after, "main-inv", "write", address, atomic=True,
                         value={"kind": "integer", "bits": 32, "hex": "1"})
    worker_effect = effect("worker-read", worker_read, "worker-inv", "read", address, atomic=True)
    helper_inv = invocation("helper-inv", "helper", "main-inv", helper["source"])
    summaries = {
        "main": summary("main", [main_effect], [invocation("main-inv", "main"), helper_inv],
                        order_edges=[{"before": "made-up", "after": "main-write", "guards": []}]),
        "worker": summary("worker", [worker_effect]),
    }
    modules = {A: {"functions": [{"id": "main", "declaration": False},
                                  {"id": "worker", "declaration": False},
                                  {"id": "helper", "declaration": False}],
                   "source_mapping": "complete"}}
    inputs = SimpleNamespace(scope_id=B, modules=modules, scope={"members": [A]})
    req = request()
    if request_changes:
        req = deepcopy(req)
        for key, value in request_changes.items():
            if key == "budgets":
                req["budgets"].update(value)
            else:
                req[key] = value
    return inputs, req, local_facts, order_facts, summaries


def test_graph_builds_contexts_instances_order_mhp_mutex_and_reads_from():
    graph = build_thread_graph(*scenario())
    assert validate_thread_document(graph, "ThreadContextGraph") is graph
    assert graph["status"] == "complete"
    assert len(graph["contexts"]) == 2 and len(graph["instances"]) == 2
    assert {item["kind"] for item in graph["lifecycles"]} >= {
        "root-start", "create-attempt", "thread-start", "thread-exit", "join-attempt", "join-complete"}
    assert {item["kind"] for item in graph["order"]} >= {"create", "join", "call-entry", "call-exit"}
    assert any(item["kind"] == "unwind-successor" for item in graph["anchors"])
    assert any(item["relation"] == "not_parallel" for item in graph["mhp"])
    assert any(item["kind"] == "mutex" and item["status"] == "candidate" for item in graph["synchronization"])
    assert any(item["kind"] == "reads-from" and item["status"] == "candidate" for item in graph["synchronization"])
    assert not any(item["kind"] == "happens-before" for item in graph["synchronization"])
    # P2 summary order is intentionally not consumed as an execution proof.
    assert "made-up" not in {item["before"] for item in graph["order"]}
    assert graph == build_thread_graph(*scenario())


def test_source_overlay_is_an_explicit_identity_dependency_not_an_order_proof():
    assistance = {
        "binding": {"status": "complete", "kind": "SourceIRBinding"},
        "overlay": {"status": "complete", "kind": "CanonicalObjectOverlay",
                    "mappings": [{"program_object_id": "program-shared", "resolution": "exact",
                                  "artifact_objects": [{"artifact_key": A, "id": "shared"}]}]},
    }
    graph = build_thread_graph(*scenario(), source_assistance=assistance)
    assert graph["status"] == "complete"
    assert {item["kind"] for item in graph["dependencies"]} >= {
        "SourceIRBinding", "CanonicalObjectOverlay"}
    assert {item["object_key"] for item in graph["effects"]} == {"program-shared"}
    assert not any(item["kind"] == "happens-before" for item in graph["synchronization"])
    partial = deepcopy(assistance); partial["binding"]["status"] = "partial"
    assert build_thread_graph(*scenario(), source_assistance=partial)["status"] == "partial"

    values = list(scenario())
    values[4]["worker"]["effects"][0]["address"] = None
    event_source = values[4]["worker"]["effects"][0]["source"]
    assistance["overlay"]["mappings"][0]["program_entity_id"] = "entity-shared"
    assistance["binding"]["expression_bindings"] = [{
        "program_entity_id": "entity-shared",
        "targets": [{"artifact_key": event_source["artifact_key"], "id": event_source["id"]}],
    }]
    graph = build_thread_graph(*values, source_assistance=assistance)
    resolved = next(item for item in graph["effects"] if item["effect_id"] == "worker-read")
    assert resolved["object_key"] == "program-shared" and resolved["offset_bytes"] == "0"


def test_missing_summary_unknown_model_and_partial_inputs_are_explicit():
    inputs, req, locals_, orders, summaries = scenario()
    summaries.pop("worker")
    locals_[A]["calls"][0]["callback_targets"] = [ref("worker", None)]
    graph = build_thread_graph(inputs, req, locals_, orders, summaries)
    assert graph["status"] == "partial"
    assert "effect-summary-missing" in {item["code"] for item in graph["frontier"]}
    locals_[A]["calls"][0]["callback_targets"] = []
    graph = build_thread_graph(inputs, req, locals_, orders, summaries)
    assert "callback-target-unknown" in {item["code"] for item in graph["diagnostics"]}
    locals_[A]["status"] = "partial"
    assert build_thread_graph(inputs, req, locals_, orders, summaries)["status"] == "partial"


def test_recursive_and_loop_create_merge_without_infinite_expansion():
    graph = build_thread_graph(*scenario(recursive=True))
    assert graph["status"] == "partial"
    assert any(item["cardinality"] == "merged" and item["reason"] == "recursive-thread-create"
               for item in graph["instances"])
    assert "thread-instance-merged" in {item["code"] for item in graph["frontier"]}
    values = scenario()
    values[3][A]["nodes"][0]["multiplicity"] = "repeated"
    graph = build_thread_graph(*values)
    assert any(item["reason"] == "repeated-thread-create" for item in graph["instances"])


def test_context_instance_and_graph_item_budgets_are_conservative():
    graph = build_thread_graph(*scenario(request_changes={"budgets": {"thread_contexts": 1}}))
    assert graph["status"] == "partial" and graph["frontier"][0]["code"] == "thread-context-budget"
    graph = build_thread_graph(*scenario(request_changes={"budgets": {"thread_instances": 1}}))
    assert graph["status"] == "partial" and any(item["code"] == "thread-instance-budget" for item in graph["frontier"])
    with pytest.raises(AnalysisError, match="cannot represent"):
        build_thread_graph(*scenario(request_changes={"budgets": {"graph_items": 1}}))


def test_join_clobber_or_no_reachable_handle_stays_unknown():
    graph = build_thread_graph(*scenario(include_clobber=True))
    assert graph["status"] == "partial"
    assert "join-handle-ambiguous" in {item["code"] for item in graph["frontier"]}
    values = scenario()
    values[2][A]["provenance"] = []
    graph = build_thread_graph(*values)
    assert not any(item["kind"] == "join-complete" for item in graph["lifecycles"])


def test_invalid_roots_and_private_builder_branches():
    values = scenario(); values[1]["roots"] = []
    with pytest.raises(AnalysisError, match="explicit roots"):
        build_thread_graph(*values)
    values = scenario(); values[1]["roots"][0]["function_id"] = "absent"
    with pytest.raises(AnalysisError, match="not a defined"):
        build_thread_graph(*values)
    values = scenario(); values[0].modules[A]["functions"][0]["declaration"] = True
    with pytest.raises(AnalysisError):
        build_thread_graph(*values)
    builder = ThreadGraphBuilder(*scenario())
    assert builder._summary(ref("absent", None)) is None
    assert builder._provenance_reaches(A, None, ref("x"), set()) == (False, True)
    assert builder._graph_edge("intra-thread", "same", "same", "unknown") is None
    builder.instances = [
        {"id": "a", "root_id": "r", "cardinality": "single"},
        {"id": "b", "root_id": "r", "cardinality": "unknown"},
        {"id": "c", "root_id": "other", "cardinality": "single"},
    ]
    builder._mhp()
    assert any(item["relation"] == "unknown" for item in builder.mhp)


def test_disjoint_atomic_objects_are_only_excluded_candidates():
    values = scenario()
    values[4]["worker"]["effects"][0]["address"]["source"] = ref("other", None)
    graph = build_thread_graph(*values)
    candidates = [item for item in graph["synchronization"] if item["kind"] == "reads-from"]
    assert candidates and candidates[0]["status"] == "excluded" and candidates[0]["object_key"] is None


def test_private_finite_domain_and_budget_branches():
    assert _argument()["kind"] == "unknown"
    assert _object_range(None) == (None, None)
    assert _object_range({"kind": "unknown"}) == (None, None)
    assert _object_range({"kind": "expression", "value": 1})[1] is None
    assert not _ranges_disjoint({"offset_bytes": None, "size_bytes": "4"},
                                {"offset_bytes": "0", "size_bytes": "4"})
    values = scenario()
    builder = ThreadGraphBuilder(*values)
    entry = ref("main", None)
    context = builder._context(entry, [])
    assert builder._context(entry, []) is context
    instance = builder._instance("root", context, None, None)
    assert builder._instance("root", context, None, None) is instance
    assert builder._calls_for_summary(None) == []
    assert builder._local_relation(ref("missing"), ref("other")) is None
    first = builder._graph_edge("intra-thread", "one", "two", "unknown")
    assert builder._graph_edge("intra-thread", "one", "two", "unknown")["id"] == first["id"]

    limited = ThreadGraphBuilder(*scenario())
    limited.limit = 0
    assert not limited._append(limited.effects, {})
    assert not limited._append(limited.effects, {})
    assert limited._anchor("function-entry", entry, "inv", {"id": "i", "context_id": "c"}) is None
    limited._bind_summary({"id": "i", "context_id": "c"}, None)

    provenance = ThreadGraphBuilder(*scenario())
    provenance.local_facts[A]["provenance"] = [
        {"source": ref("store"), "kind": "store", "value": ref("a"), "object": ref("b")},
        {"source": ref("cast"), "kind": "cast", "value": ref("b"), "object": None},
        {"source": ref("cycle"), "kind": "cast", "value": ref("cycle"), "object": None},
    ]
    assert provenance._provenance_reaches(A, ref("a"), ref("cast"), set()) == (True, False)
    assert provenance._provenance_reaches(A, ref("cycle"), ref("absent"), set()) == (False, False)

    pairs = ThreadGraphBuilder(*scenario())
    pairs.instances = [
        {"id": "a", "root_id": "r", "cardinality": "single"},
        {"id": "b", "root_id": "r", "cardinality": "single"},
        {"id": "c", "root_id": "other", "cardinality": "single"},
    ]
    pairs._mhp(); before = len(pairs.mhp); pairs._mhp()
    assert len(pairs.mhp) == before

    pairs.mutex_records = [
        {"thread": {"id": "a"}, "call": {"mutex_source": None, "source": ref("none")}, "event": "mutex-lock", "guard": "g"},
        {"thread": {"id": "a"}, "call": {"mutex_source": ref("m"), "source": ref("alock")}, "event": "mutex-lock", "guard": "g"},
        {"thread": {"id": "b"}, "call": {"mutex_source": ref("m"), "source": ref("block")}, "event": "mutex-lock", "guard": "g"},
    ]
    pairs._mutex()
    assert not pairs.synchronization

    base = {"id": "e", "atomic": True, "kind": "write", "thread_instance_id": "a",
            "object_key": "object", "offset_bytes": "0", "size_bytes": "4",
            "syncscope": "system", "guards": [], "source": ref("e")}
    pairs.effects = [base, {**base, "id": "same", "kind": "read"},
                     {**base, "id": "other-root", "kind": "read", "thread_instance_id": "c"},
                     {**base, "id": "unknown-object", "kind": "read", "thread_instance_id": "b", "object_key": None}]
    pairs._atomics()
    assert not pairs.synchronization


def test_each_explicit_root_requires_structural_budget():
    for change, match in [({"thread_contexts": 0}, "every explicit root"),
                          ({"graph_items": 1}, "every explicit root"),
                          ({"graph_items": 2}, "every explicit root")]:
        values = scenario()
        values[1]["budgets"].update(change)
        with pytest.raises(AnalysisError, match=match):
            ThreadGraphBuilder(*values).build()


def test_cross_tu_callback_resolution_requires_unique_closed_scope():
    values = scenario()
    other = "e" * 64
    values[0].scope.update(closed=True, external_boundaries=[])
    values[0].modules[A]["functions"].append(
        {"id": "worker-decl", "name": "worker", "declaration": True,
         "linkage": "external", "comdat": None})
    values[0].modules[other] = {"functions": [
        {"id": "worker-def", "name": "worker", "declaration": False,
         "linkage": "external", "comdat": None}], "source_mapping": "complete"}
    builder = ThreadGraphBuilder(*values)
    target = {"artifact_key": A, "function_id": None, "id": "worker-decl"}
    assert builder._resolve_callback_target(target) == {
        "artifact_key": other, "function_id": None, "id": "worker-def"}
    values[0].scope["closed"] = False
    assert ThreadGraphBuilder(*values)._resolve_callback_target(target) is None
    values[0].scope["closed"] = True
    values[0].modules["f" * 64] = deepcopy(values[0].modules[other])
    assert ThreadGraphBuilder(*values)._resolve_callback_target(target) is None


def test_atomic_range_and_syncscope_incompatibility_are_excluded():
    values = scenario()
    values[4]["worker"]["effects"][0]["address"]["offset"] = "8"
    graph = build_thread_graph(*values)
    candidate = next(item for item in graph["synchronization"] if item["kind"] == "reads-from")
    assert candidate["status"] == "excluded" and candidate["reason"] == "disjoint-atomic-range"
    values = scenario()
    values[4]["worker"]["effects"][0]["syncscope"] = "singlethread"
    graph = build_thread_graph(*values)
    candidate = next(item for item in graph["synchronization"] if item["kind"] == "reads-from")
    assert candidate["status"] == "excluded" and candidate["reason"] == "incompatible-syncscope"
