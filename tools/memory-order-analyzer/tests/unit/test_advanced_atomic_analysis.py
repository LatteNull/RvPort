from copy import deepcopy

import pytest

import memory_order_analyzer.advanced_atomic_analysis as atomic

from memory_order_analyzer.advanced_atomic_analysis import (
    build_communication_graph,
    build_overlay,
    build_report,
    classify_source_constructs,
    extract_local_facts,
    normalize_for_equivalence,
    release_sequence_policy,
)
from memory_order_analyzer.advanced_atomic_contracts import expected_advanced_atomic_protocol


ARTIFACT = "a" * 64


def budgets(**updates):
    value = dict(expected_advanced_atomic_protocol()["budgets"])
    value.update(updates)
    return value


def scalar(identifier, value, bits=32):
    return {"id": identifier, "kind": "integer", "type": f"i{bits}", "type_kind": "integer",
            "bits": bits, "function": "f", "block": "f:b0", "operands": [],
            "details": {"hex": f"{value:X}"}, "status": "known"}


def raw_event(identifier, kind, ordering, *, block="f:b0", operation=None, weak=False,
              success=None, failure=None, value="v1"):
    result = {"id": identifier, "kind": kind, "function": "f", "block": block,
              "source": {"inline_chain": []}, "address": {"kind": "global", "symbol": "flag"},
              "inputs": {}, "result_ref": identifier + ":result",
              "ranges": [{"role": "read_write", "address_ref": identifier + ":address",
                          "address_space": 0, "alignment": 4,
                          "size": {"status": "exact", "bytes": "4"}}],
              "range_status": "available", "ordering": ordering, "syncscope": "system"}
    if kind == "store":
        result["inputs"] = {"value": value}
    if kind == "atomicrmw":
        result.update(operation=operation or "add")
        result["inputs"] = {"value": value}
    if kind == "cmpxchg":
        result.pop("ordering")
        result.update(success_ordering=success or "acq_rel", failure_ordering=failure or "acquire",
                      weak=weak)
        result["inputs"] = {"compare": "v0", "new": value}
    if kind == "fence":
        result.pop("address")
        result["ranges"] = []
        result["range_status"] = "not_applicable"
    return result


def module(events):
    return {"schema_version": 2, "kind": "ModuleFacts", "artifact_key": ARTIFACT,
            "module_hash": "b" * 64, "target": "x86_64", "layout": "e-p:64:64",
            "producer": [], "functions": [], "globals": [], "events": events, "calls": [],
            "capabilities": {}, "source_mapping": "unavailable",
            "values": [scalar("v0", 0), scalar("v1", 1)], "protocol": {},
            "extraction": {"status": "complete", "roots": 0, "nodes": 2,
                           "references": 0, "unknown": 0, "diagnostics": []}}


def thread_graph(events, instances):
    unique = sorted(set(instances))
    return {
        "effects": [{"id": "effect:" + item["id"],
                     "source": {"artifact_key": ARTIFACT, "function_id": "f", "id": item["id"]},
                     "thread_context_id": "context:" + instances[index],
                     "thread_instance_id": instances[index]}
                    for index, item in enumerate(events)],
        "mhp": [{"id": f"mhp:{left}:{right}", "left": left, "right": right,
                 "relation": "may_parallel"}
                for index, left in enumerate(unique) for right in unique[index + 1:]],
    }


def test_release_policy_is_language_specific():
    for standard in ("c11", "c17", "c++17"):
        assert release_sequence_policy(standard) == "c11-c17-cpp17-v1"
    assert release_sequence_policy("c++20") == "cpp20-v1"
    with pytest.raises(ValueError):
        release_sequence_policy("c++23")


@pytest.mark.parametrize("standard,policy", [("compiler-default", "unresolved-standard-v1"),
                                          ("c99", "legacy-no-iso-atomics-v1"),
                                          ("c++03", "legacy-no-iso-atomics-v1")])
def test_unknown_or_legacy_standard_has_explicit_schema_valid_boundary(standard, policy):
    raw = [raw_event("f:b0:i0", "store", "release"), raw_event("f:b0:i1", "load", "acquire")]
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard=standard,
                                thread_graph=thread_graph(raw, ["writer", "reader"]), budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard=standard, budgets=budgets())
    assert graph["release_sequence_policy"] == policy
    assert graph["status"] == "partial"
    assert any(item["code"] == "atomic-standard-unsupported" for item in graph["frontier"])
    assert all(item["assessment"] == "unknown" for item in graph["assessments"])


def test_extracts_rmw_cas_outcomes_and_signal_fence_frontier():
    raw = [raw_event("f:b0:i0", "atomicrmw", "monotonic", operation="add"),
           raw_event("f:b0:i1", "cmpxchg", None, weak=True),
           raw_event("f:b0:i2", "fence", "release")]
    raw[-1]["syncscope"] = "singlethread"
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11",
                                thread_graph=thread_graph(raw, ["t", "t", "t"]), budgets=budgets())
    assert [item["kind"] for item in local["events"]].count("cas") == 3
    success = next(item for item in local["events"] if item["kind"] == "cas" and item["outcome"] == "success")
    failure = next(item for item in local["events"] if item["kind"] == "cas" and item["outcome"] == "failure")
    assert success["mo_member"] and success["write_effect"]
    assert failure["read_effect"] and not failure["mo_member"]
    assert any(item["outcome"] == "spurious-failure" for item in local["events"])
    assert any(item["code"] == "weak-cas-spurious-path" for item in local["frontier"])
    assert any(item["code"] == "signal-fence-interthread-unsupported" for item in local["frontier"])


def test_source_classifier_accepts_canonical_and_rejects_name_only():
    facts = {"physical_tu_id": "c" * 64, "nodes": [
        {"id": "call", "kind": "call-expression", "canonical_type": "int", "attributes": []},
        {"id": "std", "kind": "function", "qualified_name": "std::atomic<int>::load"},
        {"id": "c", "kind": "atomic-expression", "canonical_type": "int", "attributes": ["atomic-operation:__c11_atomic_load"]},
        {"id": "user", "kind": "function", "qualified_name": "atomic_user::atomic_load"},
    ], "relations": [
        {"id": "r1", "kind": "atomic-cpp-load", "from": "call", "to": "std"},
        {"id": "r2", "kind": "atomic", "from": "call", "to": "user"},
    ]}
    cpp = classify_source_constructs([facts], scope_id="scope", language_standard="c++17")
    assert [item["status"] for item in cpp["constructs"]] == ["exact", "candidate"]
    c_facts = deepcopy(facts)
    c_facts["relations"] = [{"id": "r3", "kind": "atomic-c-load", "from": "c", "to": None}]
    c = classify_source_constructs([c_facts], scope_id="scope", language_standard="c17")
    assert c["constructs"][0]["status"] == "exact"


def test_release_acquire_and_fence_pair_are_discharged():
    raw = [raw_event("f:b0:i0", "fence", "release"),
           raw_event("f:b0:i1", "store", "monotonic"),
           raw_event("f:b1:i0", "load", "monotonic", block="f:b1"),
           raw_event("f:b1:i1", "fence", "acquire", block="f:b1")]
    mapping = thread_graph(raw, ["producer", "producer", "consumer", "consumer"])
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11",
                                thread_graph=mapping,
                                budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=True, thread_graph=mapping)
    assert graph["fence_pairings"]
    read = next(item for item in graph["assessments"] if item["read_event"] ==
                next(event["id"] for event in graph["events"] if event["source_id"] == "f:b1:i0"))
    assert read["assessment"] == "discharged-within-bounded-model"


def test_release_sequence_differs_between_cpp17_and_cpp20():
    raw = [raw_event("f:b0:i0", "store", "release"),
           raw_event("f:b0:i1", "store", "monotonic"),
           raw_event("f:b1:i0", "load", "acquire", block="f:b1")]
    mapping = thread_graph(raw, ["producer", "producer", "consumer"])
    results = {}
    for standard in ("c++17", "c++20"):
        local = extract_local_facts([module(raw)], scope_id="scope", language_standard=standard,
                                    thread_graph=mapping, budgets=budgets())
        graph = build_communication_graph(local, scope_id="scope", language_standard=standard,
                                          budgets=budgets(), closed_scope=True, thread_graph=mapping)
        results[standard] = {item["assessment"] for item in graph["assessments"]}
    assert "discharged-within-bounded-model" in results["c++17"]
    assert "risk" in results["c++20"]


def test_open_scope_budget_and_unknown_object_cannot_discharge():
    raw = [raw_event("f:b0:i0", "store", "release"), raw_event("f:b1:i0", "load", "acquire", block="f:b1")]
    raw[1]["ranges"][0]["size"] = {"status": "unknown", "reason": "dynamic"}
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11", budgets=budgets(atomic_events=1))
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=False)
    assert graph["status"] == "partial"
    codes = {item["code"] for item in graph["frontier"]}
    assert "atomic-event-budget-exhausted" in codes
    assert "reads-from-candidate-set-open" in codes


def test_overlay_report_and_normalized_equivalence():
    raw = [raw_event("f:b0:i0", "store", "monotonic"),
           raw_event("f:b1:i0", "load", "monotonic", block="f:b1")]
    mapping = thread_graph(raw, ["p", "c"])
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c17",
                                thread_graph=mapping, budgets=budgets())
    clone = deepcopy(local)
    clone["events"] = list(reversed(clone["events"]))
    assert normalize_for_equivalence(local) == normalize_for_equivalence(clone)
    graph = build_communication_graph(local, scope_id="scope", language_standard="c17",
                                      budgets=budgets(), closed_scope=True, thread_graph=mapping)
    overlay = build_overlay(graph)
    report = build_report(graph, overlay)
    assert report["exit_code"] == 3
    assert report["safety"] == "not_established"


def test_publication_overlay_preserves_p4_and_reports_unresolved_binding():
    raw = [raw_event("f:b0:i0", "store", "release"), raw_event("f:b1:i0", "load", "acquire", block="f:b1")]
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11",
                                thread_graph=thread_graph(raw, ["p", "c"]), budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=True)
    p4 = {"scope_id": "p4-scope", "protocols": [{"id": "protocol", "flag_read": "missing"}]}
    original = deepcopy(p4)
    overlay = build_overlay(graph, p4)
    assert p4 == original
    assert overlay["protocols"][0]["assessment"] == "unknown"
    report = build_report(graph, overlay)
    assert report["exit_code"] == 2


def test_value_address_range_and_provenance_boundaries_are_explicit():
    assert atomic._value({}, "missing")["reason"] == "missing-value-node"
    assert atomic._value({"v": {"kind": "float", "reason": "not-integer"}}, "v")["state"] == "unknown"
    assert atomic._address_key(None, ARTIFACT, "f") == (None, None)
    assert atomic._address_key({"kind": "alloca", "object": "slot"}, ARTIFACT, "f")[0].endswith(":slot")
    assert atomic._address_key({"kind": "argument", "object": "arg"}, ARTIFACT, "f")[0].endswith(":arg")
    assert atomic._address_key({"kind": "unknown"}, ARTIFACT, "f") == (None, None)
    base, offset = atomic._address_key(
        {"kind": "constant_gep", "base": {"kind": "global", "symbol": "g"}, "indices": [0, 1]},
        ARTIFACT, "f")
    assert base == "global:g" and offset == 0
    assert atomic._address_key(
        {"kind": "constant_gep", "base": {"kind": "unknown"}, "indices": [1]}, ARTIFACT, "f") == (None, None)

    malformed = raw_event("f:b0:i0", "load", "acquire")
    malformed["address"] = None
    malformed["ranges"][0]["size"] = {"status": "exact", "bytes": "bad"}
    assert atomic._range(malformed, ARTIFACT)[:3] == (f"{ARTIFACT}:f:f:b0:i0:address", 0, None)

    provenance = atomic._provenance_map({"nodes": [
        {"value_id": "global:flag", "certainty": "must", "candidates": [{"object_id": "runtime:flag"}]},
        {"source_object": "source", "resolution": "may", "candidates": ["left", {"id": "right"}, {}]},
    ]})
    assert provenance["global:flag"] == {"resolution": "must", "candidates": ["runtime:flag"]}
    assert provenance["source"]["candidates"] == ["left", "right"]

    store = raw_event("f:b0:i0", "store", "release")
    exact = extract_local_facts([module([store])], scope_id="scope", language_standard="c11",
                                provenance_graph={"bindings": [{"value_id": "global:flag", "resolution": "must",
                                                                 "candidates": ["runtime:flag"]}]}, budgets=budgets())
    assert exact["events"][0]["object_key"] == "runtime:flag"
    partial = extract_local_facts([module([store])], scope_id="scope", language_standard="c11",
                                  provenance_graph={"nodes": [{"value_id": "global:flag", "certainty": "may",
                                                               "candidates": ["left", "right"]}]}, budgets=budgets())
    assert partial["status"] == "partial"


def test_extraction_skips_irrelevant_events_and_covers_unknown_rmw_and_syncscope():
    irrelevant = raw_event("f:b0:i0", "call", "not_atomic")
    unknown_rmw = raw_event("f:b0:i1", "atomicrmw", "monotonic", operation="fadd")
    target_fence = raw_event("f:b0:i2", "fence", "release")
    target_fence["syncscope"] = "device"
    facts = module([irrelevant, unknown_rmw, target_fence])
    facts["values"].append({"id": "float", "kind": "float", "reason": "floating", "details": {}})
    unknown_rmw["inputs"]["value"] = "float"
    local = extract_local_facts([facts], scope_id="scope", language_standard="c17", budgets=budgets())
    assert len(local["events"]) == 2
    assert {item["reason"] for item in local["events"]} == {
        "rmw-value-transition-unknown", "atomic-syncscope-unsupported"}


def test_source_classifier_ignores_unrelated_and_keeps_c_candidate():
    facts = {"physical_tu_id": "p" * 64,
             "nodes": [{"id": "call", "kind": "call-expression", "canonical_type": "int", "attributes": []}],
             "relations": [{"id": "skip", "kind": "call", "from": "call", "to": None},
                           {"id": "candidate", "kind": "atomic", "from": "call", "to": None}]}
    result = classify_source_constructs([facts], scope_id="scope", language_standard="c11")
    assert len(result["constructs"]) == 1
    assert result["constructs"][0]["status"] == "candidate"


def test_solver_helpers_cover_disjoint_unknown_transitive_and_cas_cases():
    left = {"object_key": "a", "offset_bytes": 0, "size_bytes": 4}
    assert not atomic._overlap(left, {**left, "object_key": "b"})
    assert not atomic._overlap(left, {**left, "size_bytes": None})
    assert atomic._overlap(left, {**left, "offset_bytes": 2})
    closure = atomic._before_closure([
        {"before": "a", "after": "b"}, {"before": "b", "after": "c"}])
    assert "c" in closure["a"]

    exact = {"state": "exact", "bits": 32, "hex": "1"}
    write = {**left, "id": "w", "kind": "store", "write_effect": True, "mo_member": True,
             "value": exact, "thread_instance_id": "producer"}
    failure = {**left, "id": "r", "read_effect": True, "kind": "cas", "outcome": "failure",
               "guards": [{"kind": "cas-failure", "compare": exact}],
               "thread_instance_id": "consumer"}
    assert not atomic._compatible(write, failure)
    failure["outcome"] = "spurious-failure"
    assert atomic._compatible(write, failure)

    same_instance = {**failure, "kind": "load", "thread_instance_id": "producer"}
    assert not atomic._compatible(write, same_instance)
    unknown_compare = {**failure, "guards": [], "outcome": "success"}
    assert atomic._compatible(write, unknown_compare)
    success = {**failure, "outcome": "success"}
    assert atomic._compatible(write, success)

    frontier = []
    initialization = {**write, "kind": "initialization"}
    assert atomic._communication_relation(initialization, failure, {}, frontier)
    not_parallel = {"mhp": [{"id": "ordered", "left": "producer", "right": "consumer",
                              "relation": "not_parallel"}]}
    assert not atomic._communication_relation(write, failure, not_parallel, frontier)
    read = {"id": "read", "source_id": "source", "object_key": "object"}
    edge = {"id": "edge", "write_event": "write", "read_event": "read"}
    by_id = {"write": {"source_id": "write-source", "object_key": "object"},
             "read": read}
    assert not atomic._frontier_affects(read, [edge], [
        {"relevant": False, "references": []}, {"relevant": True, "references": ["other"]}], by_id)
    assert atomic._frontier_affects(read, [edge], [{"relevant": True, "references": ["edge"]}], by_id)
    assert atomic._frontier_affects(read, [], [{"relevant": True, "references": []}], by_id)


def test_mo_release_and_fence_budget_boundaries_are_conservative():
    raw = [raw_event("f:b0:i0", "store", "release"),
           raw_event("f:b0:i1", "atomicrmw", "monotonic", operation="add"),
           raw_event("f:b1:i0", "load", "acquire", block="f:b1")]
    mapping = thread_graph(raw, ["p", "q", "c"])
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11",
                                thread_graph=mapping, budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(mo_nodes=1), closed_scope=True,
                                      thread_graph=mapping)
    assert any(item["code"] == "modification-order-search-incomplete" for item in graph["frontier"])
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(mo_branches=1, assignments=1, rf_edges=1), closed_scope=True,
                                      thread_graph=mapping)
    assert graph["status"] == "partial"

    many = [raw_event(f"f:b0:i{index}", "store", "release" if index == 0 else "monotonic")
            for index in range(9)]
    many_local = extract_local_facts([module(many)], scope_id="scope", language_standard="c17", budgets=budgets())
    many_graph = build_communication_graph(many_local, scope_id="scope", language_standard="c17",
                                           budgets=budgets(), closed_scope=True)
    assert any("bounded v1 enumerator" in item["detail_en"] for item in many_graph["frontier"])

    normalized = local["events"]
    by_id = {item["id"]: item for item in normalized}
    order = [next(item["id"] for item in normalized if item["kind"] == kind)
             for kind in ("store", "rmw")]
    sequences = atomic._release_sequences(order, by_id, "cpp20-v1")
    assert len(sequences[0]["members"]) == 2


def test_object_and_rf_budgets_and_missing_candidates_produce_frontier():
    first_store = raw_event("f:b0:i0", "store", "release")
    second_store = raw_event("f:b0:i1", "store", "release")
    second_store["address"] = {"kind": "global", "symbol": "other"}
    read = raw_event("f:b1:i0", "load", "acquire", block="f:b1")
    local = extract_local_facts([module([first_store, second_store, read])], scope_id="scope",
                                language_standard="c11", budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(objects=1, rf_edges=1), closed_scope=True)
    codes = {item["code"] for item in graph["frontier"]}
    assert "atomic-object-budget-exhausted" in codes

    lonely = raw_event("f:b0:i0", "load", "acquire")
    lonely_local = extract_local_facts([module([lonely])], scope_id="scope",
                                       language_standard="c11", budgets=budgets())
    lonely_graph = build_communication_graph(lonely_local, scope_id="scope", language_standard="c11",
                                             budgets=budgets(), closed_scope=True)
    assert lonely_graph["assessments"][0]["assessment"] == "unknown"
    assert any(item["code"] == "reads-from-candidate-set-open" for item in lonely_graph["frontier"])


def test_overlay_covers_discharged_risk_and_incomplete_protocol_branches():
    raw = [raw_event("f:b0:i0", "store", "release"),
           raw_event("f:b1:i0", "load", "acquire", block="f:b1")]
    mapping = thread_graph(raw, ["p", "c"])
    local = extract_local_facts([module(raw)], scope_id="scope", language_standard="c11",
                                thread_graph=mapping, budgets=budgets())
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), closed_scope=True, thread_graph=mapping)
    read_source = raw[1]["id"]
    flag_write, flag_read = "effect:" + raw[0]["id"], "effect:" + read_source
    mapping["effects"].extend([
        {"id": "payload-write", "source": {"artifact_key": ARTIFACT, "id": "payload:write"},
         "thread_instance_id": "p"},
        {"id": "payload-read", "source": {"artifact_key": ARTIFACT, "id": "payload:read"},
         "thread_instance_id": "c"},
    ])
    mapping["order"] = [
        {"before": "payload-write", "after": flag_write},
        {"before": flag_read, "after": "payload-read"},
    ]
    p4 = {"scope_id": "p4", "protocols": [{
        "id": "p", "flag_write": flag_write, "flag_read": flag_read,
        "payload_write": "payload-write", "payload_read": "payload-read", "chain": [],
    }]}
    discharged = build_overlay(graph, p4, mapping)
    assert discharged["protocols"][0]["assessment"] == "discharged-within-bounded-model"

    risk_graph = deepcopy(graph)
    risk_graph["assessments"] = [{**item, "assessment": "risk", "evidence": []}
                                 for item in graph["assessments"]]
    # build_overlay only consumes immutable fields and deliberately does not revalidate its input.
    risk = build_overlay(risk_graph, p4, mapping)
    assert risk["protocols"][0]["assessment"] == "risk"

    unknown_graph = deepcopy(graph)
    unknown_graph["assessments"] = [{**item, "assessment": "unknown", "evidence": []}
                                    for item in graph["assessments"]]
    unknown = build_overlay(unknown_graph, p4, mapping)
    assert unknown["protocols"][0]["frontier"] == ["advanced-atomic-assignment-incomplete"]


def test_ast_only_constructs_remain_partial_without_runtime_proof():
    source = classify_source_constructs([{
        "physical_tu_id": "c" * 64,
        "nodes": [{"id": "atomic", "kind": "atomic-expression", "canonical_type": "_Atomic(int)",
                   "attributes": ["atomic-profile:c"]}],
        "relations": [{"id": "relation", "kind": "atomic-c-rmw", "from": "atomic", "to": None}],
    }], scope_id="scope", language_standard="c11")
    local = extract_local_facts([], scope_id="scope", language_standard="c11",
                                budgets=budgets(), source_constructs=source)
    assert local["status"] == "partial" and not local["events"]
    assert any(item["code"] == "ast-only-runtime-binding-unavailable" for item in local["frontier"])


def test_demand_filter_and_r3_shard_do_not_materialize_unreachable_events():
    reachable = raw_event("f:b0:i0", "store", "release")
    unreachable = raw_event("g:b0:i0", "store", "release")
    unreachable["function"] = "g"
    facts = module([reachable, unreachable])
    demand = {"nodes": [{"artifact_key": ARTIFACT, "function_id": "f", "context_id": "ctx"}]}
    local = extract_local_facts([facts], scope_id="scope", language_standard="c17",
                                budgets=budgets(), demand_documents=(demand,))
    assert {item["function_id"] for item in local["events"]} == {"f"}

    shard = {
        "kind": "AdvancedAtomicFunctionFacts", "artifact_key": ARTIFACT, "function_id": "f",
        "context_id": "ctx", "status": "completed", "semantic_digest": "d" * 64,
        "facts": {"atomic_events": [{
            "id": "f:b0:i0", "kind": "rmw", "function": "f", "block": "f:b0",
            "object": "@flag", "size_bytes": 4, "address_space": 0,
            "ordering": "acq_rel", "failure_ordering": None, "syncscope": "system",
            "operation": "add", "weak": False, "inputs": {"value": "1"},
            "result_ref": "f:b0:i0", "guards": [], "multiplicity": "single",
            "location": {"inline_chain": []},
        }]},
    }
    r3 = extract_local_facts([shard], scope_id="scope", language_standard="c17",
                             budgets=budgets(), demand_documents=(demand,))
    assert len(r3["events"]) == 1
    assert r3["events"][0]["kind"] == "rmw" and r3["events"][0]["context_id"] == "ctx"
    assert normalize_for_equivalence(r3)[0]["operation"] == "add"


def test_initial_modification_rmw_transition_and_mhp_are_required():
    rmw = raw_event("f:b0:i0", "atomicrmw", "acq_rel", operation="add")
    load = raw_event("f:b1:i0", "load", "acquire", block="f:b1")
    facts = module([rmw, load])
    facts["globals"] = [{"id": "flag", "name": "flag",
                         "initializer": {"state": "value", "value_ref": "v0"}}]
    mapping = thread_graph([rmw, load], ["producer", "consumer"])
    local = extract_local_facts([facts], scope_id="scope", language_standard="c11",
                                budgets=budgets(), thread_graph=mapping)
    assert any(item["kind"] == "initialization" for item in local["events"])
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), thread_graph=mapping)
    assert any(transition["new"]["hex"] == "1" for assignment in graph["assignments"]
               for transition in assignment["transitions"])

    no_mhp = deepcopy(mapping)
    no_mhp["mhp"] = []
    incomplete = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                           budgets=budgets(), thread_graph=no_mhp)
    assert incomplete["status"] == "partial"
    assert any(item["code"] == "mhp-unknown" for item in incomplete["frontier"])


def test_global_seq_cst_and_libatomic_runtime_are_explicit_frontiers():
    first = raw_event("f:b0:i0", "store", "seq_cst")
    second = raw_event("f:b0:i1", "store", "seq_cst")
    second["address"] = {"kind": "global", "symbol": "other"}
    facts = module([first, second])
    facts["calls"] = [{"id": "runtime", "target": "__atomic_store_16"}]
    local = extract_local_facts([facts], scope_id="scope", language_standard="c11",
                                budgets=budgets(), thread_graph={"effects": [], "mhp": []})
    assert any(item["code"] == "atomic-runtime-call-unsupported" for item in local["frontier"])
    graph = build_communication_graph(local, scope_id="scope", language_standard="c11",
                                      budgets=budgets(), thread_graph={"mhp": []})
    assert any(item["code"] == "seq-cst-global-order-unsupported" for item in graph["frontier"])


def test_integer_rmw_and_source_location_helpers_cover_invalid_and_nested_inputs():
    assert atomic._integer(None) is None
    assert atomic._integer({"state": "unknown"}) is None
    assert atomic._integer({"state": "exact", "hex": "not-hex", "bits": "bad"}) is None
    old = {"state": "exact", "hex": "3", "bits": 8}
    operand = {"state": "exact", "hex": "1", "bits": 16}
    assert {operation: atomic._rmw_transition(operation, old, operand)["hex"]
            for operation in ("xchg", "add", "sub", "and", "or", "xor")} == {
                "xchg": "1", "add": "4", "sub": "2", "and": "1", "or": "3", "xor": "2"}
    assert atomic._rmw_transition("nand", old, operand) is None
    assert atomic._rmw_transition("add", {"state": "unknown"}, operand) is None

    nested = {"spelling": {"file": r"C:\src\a.c", "line": 4},
              "children": [{"file": "src/b.c", "line": 9}, "ignored"]}
    assert ("C:/src/a.c", 4) in atomic._location_keys(nested)
    assert ("src/b.c", 9) in atomic._location_keys(nested)
    assert atomic._location_keys("not-a-location") == set()
    event = {"source": {"spelling": {"file": "a.c", "line": 2}}, "function": "f"}
    assert atomic._source_matches(event, {"source": {"spelling": {"file": "a.c", "line": 2}}})
    assert not atomic._source_matches(event, {
        "source": {"spelling": {"file": "a.c", "line": 3}}, "enclosing_symbol": "f"})
    assert atomic._source_matches({"source": {}, "function": "x:symbol:f"}, {
        "source": {}, "enclosing_symbol": "f"})
    assert not atomic._source_matches({"source": {}, "function": 1}, {
        "source": {}, "enclosing_symbol": "f"})


def test_source_point_and_enclosing_symbol_choose_smallest_valid_function_range():
    expression = {"source": {"expansion": {"file": "unit.c", "line": 8}}}
    nodes = {
        "variable": {"kind": "variable", "source": {"spelling": {"file": "unit.c", "line": 1}}},
        "other": {"kind": "function", "name": "other", "source": {
            "spelling": {"file": "other.c", "line": 1}, "spelling_end": {"file": "other.c", "line": 20}}},
        "missing": {"kind": "function", "name": "missing", "source": {"spelling": {"file": "unit.c"}}},
        "outer": {"kind": "function", "name": "outer", "source": {
            "spelling": {"file": "unit.c", "line": 1}, "spelling_end": {"file": "unit.c", "line": 20}}},
        "inner": {"kind": "method", "mangled_name": "_Z5innerv", "source": {
            "spelling": {"file": "unit.c", "line": 6}, "spelling_end": {"file": "unit.c", "line": 10}}},
    }
    assert atomic._source_point(expression) == ("unit.c", 8)
    assert atomic._source_point({"source": {}}) is None
    assert atomic._source_point(None) is None
    assert atomic._enclosing_symbol(expression, nodes) == "_Z5innerv"
    assert atomic._enclosing_symbol({"source": {}}, nodes) is None
    assert atomic._enclosing_symbol({"source": {"spelling": {"file": "none.c", "line": 1}}}, nodes) is None
    name_only = {"function": {"kind": "function", "qualified_name": "ns::f", "source": {
        "spelling": {"file": "unit.c", "line": 1}, "spelling_end": {"file": "unit.c", "line": 2}}}}
    assert atomic._enclosing_symbol(
        {"source": {"spelling": {"file": "unit.c", "line": 1}}}, name_only) == "ns::f"


def test_demand_mhp_and_r3_adapters_cover_nested_and_non_global_objects():
    found = set()
    atomic._walk_demand_keys({"artifact_key": ARTIFACT, "function": "f", "children": [
        {"artifact_key": ARTIFACT, "function_id": "g", "context_id": "ctx"}, None]}, found)
    assert (ARTIFACT, "f", None) in found and (ARTIFACT, "g", "ctx") in found
    assert atomic._demand_keys((None, {"nodes": []})) == set()
    assert atomic._is_demanded(found, ARTIFACT, "f", "different")
    assert not atomic._is_demanded(found, "other", "f", None)
    assert atomic._mhp_relation({}, None, "t") == (None, None)
    assert atomic._mhp_relation({}, "t", "t") == ("same-instance", None)
    mhp = {"mhp": [
        {"id": "skip", "left": "a", "right": "b", "relation": "may_parallel"},
        {"id": "hit", "left": "p", "right": "c", "disposition": "parallel-possible"},
        {"id": "fallback", "left": "u", "right": "v", "relation": "new-relation"},
    ]}
    assert atomic._mhp_relation(mhp, "c", "p") == ("may-parallel", "hit")
    assert atomic._mhp_relation(mhp, "u", "v") == ("unknown", "fallback")
    assert atomic._mhp_relation(mhp, "x", "y") == (None, None)

    shard = {"artifact_key": ARTIFACT, "function_id": "f", "context_id": None,
             "status": "partial", "facts": {"values": [], "atomic_events": [
                 {"id": "at", "kind": "load", "object": "@g", "size_bytes": 4},
                 {"id": "symbol", "kind": "store", "object": "a:symbol:h", "size_bytes": 4},
                 {"id": "local", "kind": "rmw", "object": "slot", "size_bytes": 4},
                 {"id": "none", "kind": "fence", "object": None},
             ]}}
    adapted = atomic._function_shard_module(shard)
    assert [item["_a6_object_key"] for item in adapted["events"]] == [
        "global:g", "global:h", "slot", None]


def test_source_classification_defaults_signal_and_ambiguous_dispatcher_are_conservative():
    source_node = {"id": "source", "kind": "atomic-expression", "canonical_type": "_Atomic(int)",
                   "attributes": ["atomic-operation:__c11_atomic_load"],
                   "source": {"spelling": {"file": "a.c", "line": 3}}}
    facts = {"physical_tu_id": "p" * 64, "nodes": [source_node], "relations": [
        {"id": "load", "kind": "atomic-c-load", "from": "source", "to": None},
        {"id": "signal", "kind": "atomic-c-signal-fence", "from": "source", "to": None},
    ]}
    classified = classify_source_constructs([facts], scope_id="scope", language_standard="c11")
    load = next(item for item in classified["constructs"] if item["operation"] == "atomic-c-load")
    signal = next(item for item in classified["constructs"] if "signal-fence" in item["operation"])
    assert load["ordering"] == "seq_cst"
    assert signal["status"] == "candidate"

    duplicated = deepcopy(classified)
    duplicated["constructs"] = [deepcopy(load), {**deepcopy(load), "id": "second"}]
    event = raw_event("f:b0:i0", "load", "seq_cst")
    event["source"] = {}
    duplicated["constructs"][0]["source"] = {}
    duplicated["constructs"][1]["source"] = {}
    duplicated["constructs"][0]["enclosing_symbol"] = "f"
    duplicated["constructs"][1]["enclosing_symbol"] = "f"
    local = extract_local_facts([module([event])], scope_id="scope", language_standard="c11",
                                budgets=budgets(), source_constructs=duplicated)
    assert any(item["code"] == "source-dispatcher-binding-ambiguous" for item in local["frontier"])


def test_extraction_budget_and_event_reason_branches_are_reported(monkeypatch):
    consume = raw_event("f:b0:i0", "load", "consume")
    device = raw_event("f:b0:i1", "store", "release")
    device["syncscope"] = "device"
    repeated = raw_event("f:b0:i2", "cmpxchg", None)
    repeated["multiplicity"] = "repeated"
    repeated["guards"] = [{"kind": "g1"}, {"kind": "g2"}]
    facts = module([consume, device, repeated])
    local = extract_local_facts([facts], scope_id="scope", language_standard="c11",
                                budgets=budgets(guards=1, worker_output_bytes=1))
    codes = {item["code"] for item in local["frontier"]}
    assert {"consume-ordering-unsupported", "atomic-syncscope-unsupported", "guard-budget-exhausted",
            "worker-output-budget-exhausted"}.issubset(codes)
    empty_demand = extract_local_facts([facts], scope_id="scope", language_standard="c11",
                                       budgets=budgets(), demand_documents=({},))
    assert any(item["code"] == "analysis-demand-incomplete" for item in empty_demand["frontier"])

    wall_ticks = iter((0.0, 5.0))
    monkeypatch.setattr(atomic.time, "monotonic", lambda: next(wall_ticks))
    monkeypatch.setattr(atomic.time, "process_time", lambda: 0.0)
    timed = extract_local_facts([module([raw_event("f:b0:i0", "store", "release")])],
                                scope_id="scope", language_standard="c11",
                                budgets=budgets(worker_seconds=1))
    assert any(item["code"] in {"worker-time-budget-exhausted", "worker-cpu-budget-exhausted"}
               for item in timed["frontier"])
