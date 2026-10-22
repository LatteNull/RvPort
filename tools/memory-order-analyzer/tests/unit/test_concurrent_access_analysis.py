from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import identity
from memory_order_analyzer.concurrent_access_analysis import (
    _dedupe, build_candidate_graph, build_execution_overlay, build_projection, build_protection_overlay,
    build_report, failed_report, normalize_operation, object_overlap, pair_accesses,
)
from memory_order_analyzer.concurrent_access_contracts import (
    concurrent_access_document, diagnostic, expected_concurrent_access_protocol,
)
from memory_order_analyzer.demand_adapters import compare_semantics, effect_summary_views


A, B = "a" * 64, "b" * 64


def request(*, closed_scope=True, source_digest=A, bc_digest=B, binding_digest=A, **limits):
    budgets = deepcopy(expected_concurrent_access_protocol()["budgets"])
    budgets.update(limits)
    return concurrent_access_document(
        "ConcurrentAccessCandidateRequest", scope_id="scope", closed_scope=closed_scope,
        target="x86_64-linux-gnu", data_layout="e-p:64:64", abi="itanium",
        members=[{"physical_tu_id": "tu", "profile_id": A, "language": "c", "standard": "c17",
                  "source_digest": source_digest, "bc_digest": bc_digest,
                  "source_ir_binding_digest": binding_digest}],
        evidence=[
            {"kind": "EffectSummary", "id": "summary", "digest": A, "path": "summary.json",
             "schema_version": 1, "producer": "scoped-effects-v1"},
            {"kind": "RootDrivenAnalysisPlan", "id": "scope", "digest": A, "path": "plan.json",
             "schema_version": 1, "producer": "execution-root-driven-analysis-v1"},
            {"kind": "ThreadEntryRootOverlay", "id": "scope", "digest": A, "path": "overlay.json",
             "schema_version": 1, "producer": "thread-entry-discovery-v1"},
        ], budgets=budgets, semantic_digest=None)


def plan(status="complete"):
    return {"kind": "RootDrivenAnalysisPlan", "scope_id": "scope", "status": status,
            "semantic_digest": A,
            "contexts": [{"id": "ctx-main", "entry": {"artifact_key": A, "function_id": "main"},
                          "root_ids": ["main"]}],
            "demands": [
                {"id": "d-main", "root_id": "main", "context": "ctx-main",
                 "function": {"artifact_key": A, "function_id": "main"}, "physical_tu_id": "tu"},
                {"id": "d-worker", "root_id": "worker", "context": "ctx-worker",
                 "function": {"artifact_key": A, "function_id": "worker"}, "physical_tu_id": "tu"},
            ],
            "reachable_functions": [
                {"id": "r-main", "root_id": "main", "entry": {"artifact_key": A, "function_id": "main"}},
                {"id": "r-worker", "root_id": "worker", "entry": {"artifact_key": A, "function_id": "worker"}},
            ], "frontier": [] if status == "complete" else [diagnostic("plan-gap", "缺失", "missing")]}


def root_overlay(status="complete", cardinality="single"):
    return {"kind": "ThreadEntryRootOverlay", "scope_id": "scope", "status": status,
            "semantic_digest": A,
            "roots": [{"id": "worker", "kind": "posix-pthread",
                       "entry": {"artifact_key": A, "function_id": "worker"},
                       "creation_site_id": "site", "source_site_id": "call",
                       "context_id": "ctx-worker", "cardinality": cardinality, "guard": "success"}],
            "contexts": [{"id": "ctx-worker", "entry": {"artifact_key": A, "function_id": "worker"}}],
            "demands": [{"id": "overlay-demand", "root_id": "worker", "context_id": "ctx-worker",
                         "entry": {"artifact_key": A, "function_id": "worker"},
                         "physical_tu_id": "tu"}],
            "frontier": [] if status == "complete" else [diagnostic("entry-gap", "缺失", "missing")]}


def root_index():
    return {"kind": "ExecutionRootIndex", "scope_id": "scope", "semantic_digest": A,
            "roots": [{"id": "main", "kind": "program", "status": "complete",
                       "entry": {"artifact_key": A, "function_id": "main"},
                       "thread_context_key": "ctx-main", "thread_instance_key": "main-instance",
                       "creation_site_id": None, "source_site_id": None, "arguments": []}]}


def object_value(object_id="object", storage="storage", offset=0, size=4, *, kind="global", union=None):
    return {"id": object_id, "storage": {"id": storage, "kind": kind},
            "path": ([{"field_id": object_id, "union_group": union}] if union else []),
            "byte_range": {"offset": offset, "size": size}, "address_space": 0}


def domain(state="must", objects=None, reason=None):
    return {"state": state, "candidates": [{"object": item, "guards": [], "proof": [], "opposed": []}
                                             for item in (objects or [])], "reason": reason}


def provenance(domains=None, status="complete"):
    domains = domains or [("shared", domain(objects=[object_value()]))]
    return {"kind": "BoundedObjectProvenanceGraph", "scope_id": "scope", "status": status,
            "semantic_digest": A, "domains": [{"id": key, "domain": value} for key, value in domains],
            "frontier": []}


def thread_graph(*, relation="may_parallel", second_cardinality="single", effects=True):
    items = []
    if effects:
        items = [
            {"id": "bound-main", "effect_id": "read", "source": {"id": "read"},
             "invocation_id": "inv-main", "thread_instance_id": "p3-main", "kind": "read",
             "object_key": "shared", "offset_bytes": "0", "size_bytes": "4", "atomic": False,
             "ordering": None, "failure_ordering": None, "guards": []},
            {"id": "bound-worker", "effect_id": "write", "source": {"id": "write"},
             "invocation_id": "inv-worker", "thread_instance_id": "p3-worker", "kind": "write",
             "object_key": "shared", "offset_bytes": "0", "size_bytes": "4", "atomic": False,
             "ordering": None, "failure_ordering": None, "guards": [],
             "protection_access_ids": ["a4-worker"]},
        ]
    return {"kind": "ThreadContextGraph", "scope_id": "scope", "model_id": "posix-pthread-v1",
            "semantic_digest": A, "status": "complete", "contexts": [
                {"id": "ctx-main", "entry": {"artifact_key": A, "function_id": "main"}},
                {"id": "ctx-worker", "entry": {"artifact_key": A, "function_id": "worker"}}],
            "instances": [
                {"id": "p3-main", "semantic_key": "main-instance", "root_id": "main",
                 "context_id": "ctx-main", "parent_id": None, "create": None, "cardinality": "single"},
                {"id": "p3-worker", "semantic_key": "worker-instance", "root_id": "main",
                 "context_id": "ctx-worker", "parent_id": "p3-main", "create": {"id": "call"},
                 "cardinality": second_cardinality}],
            "mhp": [{"id": "mhp", "left": "p3-main", "right": "p3-worker",
                     "relation": relation, "guards": [], "proof": ["lifecycle"], "reason": "test"}],
            "effects": items, "frontier": []}


def summary(context="ctx-worker", function="worker", effect_id="write", kind="write", demanded=True):
    context = context if demanded else "ctx-dead"
    function = function if demanded else "dead"
    return {"kind": "EffectSummary", "scope_id": "scope", "context_id": context,
            "semantic_digest": A, "status": "complete",
            "root": {"artifact_key": A, "function_id": function},
            "effects": [{"id": effect_id, "source": {"id": effect_id}, "context_id": context,
                         "invocation_id": f"inv-{function}", "kind": kind,
                         "address": {"domain_id": "shared"}, "size_bytes": "4", "atomic": False,
                         "volatile": False, "ordering": None, "failure_ordering": None,
                         "guards": [], "multiplicity": "single", "proof": []}]}


def test_operation_normalization_covers_memory_atomic_and_unknown_kinds():
    expected = {"load": "read", "atomic_load": "read", "store": "write", "memset": "write",
                "atomicrmw": "rmw", "cmpxchg": "cas-success",
                "cmpxchg_failure": "cas-failure", "fence": "fence", "call": "unknown"}
    assert {key: normalize_operation({"kind": key}) for key in expected} == expected
    assert _dedupe([{"id": "x", "evidence": ["a"]},
                    {"id": "x", "evidence": ["b"], "guards": ["g"]}]) == [
        {"id": "x", "evidence": ["a", "b"], "guards": ["g"]}]


def test_execution_overlay_unifies_p3_a3_roots_and_preserves_unknown_cross_root():
    lifecycle = {"kind": "CppThreadLifecycleGraph", "scope_id": "scope", "semantic_digest": A,
                 "status": "complete", "contexts": [{"id": "ctx-cpp"}],
                 "instances": [{"id": "cpp", "semantic_key": "cpp-instance", "context_id": "ctx-cpp",
                                "parent_id": None, "construct_operation_id": "construct",
                                "cardinality": "single", "status": "complete", "guard": None}],
                 "relations": [{"id": "cpp-mhp", "relation": "may-parallel", "from": "root",
                                "to": "cpp", "guard": None, "evidence": ["construct"]}], "frontier": []}
    result = build_execution_overlay(request(), plan(), root_overlay(), root_indexes=[root_index()],
                                     thread_graphs=[thread_graph()], lifecycle_graphs=[lifecycle])
    assert {item["id"] for item in result["instances"]} >= {"main-instance", "worker-instance", "cpp-instance"}
    assert any(item["disposition"] == "parallel-possible" for item in result["mhp"])
    assert any(item["disposition"] == "unknown" for item in result["mhp"])
    assert result["status"] == "partial" and any(item["code"] == "mhp-unknown" for item in result["frontier"])


def test_execution_overlay_handles_repeated_self_mhp_conflicts_and_budgets():
    repeated = thread_graph(second_cardinality="repeated")
    repeated["instances"][1]["semantic_key"] = repeated["instances"][0]["semantic_key"]
    limited = request(roots=1, contexts=1, instances=1, mhp_queries=1)
    overlay = root_overlay(cardinality="repeated")
    overlay["roots"].append({**overlay["roots"][0], "id": "worker2", "creation_site_id": "site2"})
    result = build_execution_overlay(limited, plan(), overlay, root_indexes=[root_index()],
                                     thread_graphs=[repeated])
    codes = {item["code"] for item in result["frontier"]}
    assert result["status"] == "partial"
    assert codes & {"root-binding-conflict", "roots-budget-exhausted", "contexts-budget-exhausted",
                    "instances-budget-exhausted", "mhp-query-budget-exhausted"}
    full = build_execution_overlay(request(), plan(), root_overlay(cardinality="repeated"),
                                   root_indexes=[root_index()], thread_graphs=[thread_graph(second_cardinality="repeated")])
    assert any(item["left"] == item["right"] == "worker-instance" for item in full["mhp"])


def test_execution_root_adapter_deduplicates_physical_site_and_open_scope_is_frontier():
    index = root_index()
    index["roots"] = [{"id": "base-worker", "kind": "posix-pthread", "status": "complete",
                       "entry": {"artifact_key": A, "function_id": "worker"},
                       "thread_context_key": "ctx-worker", "thread_instance_key": None,
                       "creation_site_id": "site", "source_site_id": "call", "cardinality": "single",
                       "guard": "success", "arguments": []}]
    result = build_execution_overlay(request(closed_scope=False), plan(), root_overlay(), root_indexes=[index])
    assert len(result["roots"]) == 1
    assert result["roots"][0]["adopted_from"] == ["base-worker", "worker"]
    assert result["status"] == "partial" and any(item["code"] == "open-scope" for item in result["frontier"])
    conflict = deepcopy(index); conflict["roots"][0]["thread_context_key"] = "other"
    result = build_execution_overlay(request(), plan(), root_overlay(), root_indexes=[conflict])
    assert any(item["code"] == "root-binding-conflict" for item in result["frontier"])


def test_exact_entry_roots_create_distinct_instances_and_bounded_parent_parallelism():
    overlay = root_overlay(); overlay["roots"][0]["kind"] = "c11-thrd"
    overlay["roots"].append({**deepcopy(overlay["roots"][0]), "id": "worker-two",
                             "creation_site_id": "site-two", "source_site_id": "call-two"})
    result = build_execution_overlay(request(), plan(), overlay, root_indexes=[root_index()])
    children = [item for item in result["instances"] if item.get("model") == "c11-thrd"]
    assert len(children) == 2 and len({item["id"] for item in children}) == 2
    assert all(item["parent_id"] == "main-instance" for item in children)
    parallel = [item for item in result["mhp"] if item["disposition"] == "parallel-possible"]
    assert len(parallel) == 2 and all("exact-thread-entry-creation" == item["reason"] for item in parallel)
    projection = build_projection(request(), plan(), overlay, [summary()], result,
                                  provenance_graph=provenance())
    assert len(projection["accesses"]) == 2
    assert len({item["execution_instance_id"] for item in projection["accesses"]}) == 2


def test_execution_lifecycle_root_ambiguity_and_not_parallel_are_conservative():
    index = root_index()
    index["roots"].append({**index["roots"][0], "id": "export", "thread_instance_key": "export-instance"})
    lifecycle = {"kind": "CppThreadLifecycleGraph", "scope_id": "scope", "semantic_digest": A,
                 "status": "partial", "contexts": [],
                 "instances": [{"id": "cpp", "context_id": "ctx", "cardinality": "single"}],
                 "relations": [{"id": "join", "relation": "not-parallel", "from": "cpp", "to": "root",
                                "guard": None, "evidence": []}],
                 "frontier": [diagnostic("life-gap", "缺失", "missing")]}
    result = build_execution_overlay(request(), plan(), root_overlay(), root_indexes=[index],
                                     lifecycle_graphs=[lifecycle])
    assert any(item["code"] == "lifecycle-root-ambiguous" for item in result["frontier"])


def test_execution_edge_evidence_invocations_ambiguous_context_and_query_budget():
    graph = thread_graph(); graph["invocations"] = [{"id": "invoke", "callee": "worker"}]
    graph["mhp"] = []
    index = root_index()
    index["roots"].extend([
        {**index["roots"][0], "entry": {"artifact_key": A, "function_id": "other"},
         "thread_context_key": "other", "status": "complete"},
        {**index["roots"][0], "id": "incomplete", "status": "partial"},
    ])
    lifecycle = {"kind": "CppThreadLifecycleGraph", "scope_id": "scope", "semantic_digest": A,
                 "status": "complete", "contexts": [],
                 "instances": [{"id": "cpp-a", "context_id": "ctx-worker", "cardinality": "single",
                                "construct_operation_id": "site"},
                               {"id": "cpp-b", "context_id": "ctx-worker", "cardinality": "single",
                                "construct_operation_id": "site"}],
                 "relations": [{"id": "ignored", "relation": "joined", "from": "root", "to": "cpp-a"},
                               {"id": "parallel", "relation": "may-parallel", "from": "root",
                                "to": "cpp-a", "guard": "normal", "evidence": ["construct"]}],
                 "frontier": []}
    overlay = root_overlay(); overlay["roots"][0]["kind"] = "std-thread"
    result = build_execution_overlay(request(mhp_queries=1), plan(), overlay,
                                     root_indexes=[index], thread_graphs=[graph],
                                     lifecycle_graphs=[lifecycle])
    codes = {item["code"] for item in result["frontier"]}
    assert {"root-binding-conflict", "root-evidence-incomplete",
            "root-instance-binding-ambiguous", "mhp-query-budget-exhausted"} <= codes
    assert result["invocations"][0]["id"] == "invoke"


def test_projection_uses_demand_p3_and_a5_deduplicates_and_keeps_unknown_frontier():
    execution = build_execution_overlay(request(), plan(), root_overlay(), root_indexes=[root_index()],
                                        thread_graphs=[thread_graph()])
    result = build_projection(request(), plan(), root_overlay(), [summary(), summary(demanded=False)],
                              execution, thread_graphs=[thread_graph()], provenance_graph=provenance())
    assert len(result["accesses"]) == 2
    assert result["counts"]["observed_not_demanded"] == 1
    assert {item["operation"] for item in result["accesses"]} == {"read", "write"}
    assert all(item["object_domain"]["state"] == "must" for item in result["accesses"])
    unknown = build_projection(request(), plan(), root_overlay(), [summary(kind="fence")], execution,
                               provenance_graph=None)
    codes = {item["code"] for item in unknown["frontier"]}
    assert {"advanced-atomic-semantics-unsupported"} <= codes


def test_r3_effect_adapter_preserves_full_r2_candidate_semantics():
    r3_shards = []
    for function, context, effect_id, kind in (
            ("main", "ctx-main", "read", "read"),
            ("worker", "ctx-worker", "write", "write")):
        r3_shards.append({
            "layer": "effect", "status": "completed", "artifact_key": A,
            "function_id": function, "context_id": context, "frontier": [],
            "facts": {"effects": [{"source": effect_id, "kind": kind,
                                      "object": "shared", "size_bytes": "4",
                                      "guard": None, "atomic_order": "not_atomic"}]},
        })
    adapted = effect_summary_views(r3_shards)
    assert adapted["status"] == "complete" and len(adapted["summaries"]) == 2
    eager = [summary("ctx-main", "main", "read", "read"), summary()]
    for value in eager:
        value["effects"][0]["invocation_id"] = identity({
            "function": value["root"]["function_id"], "context": value["context_id"]})

    req = request()
    execution = build_execution_overlay(req, plan(), root_overlay(), root_indexes=[root_index()],
                                        thread_graphs=[thread_graph(effects=False)])
    eager_projection = build_projection(req, plan(), root_overlay(), eager, execution,
                                        provenance_graph=provenance())
    lazy_projection = build_projection(req, plan(), root_overlay(), adapted["summaries"], execution,
                                       provenance_graph=provenance())
    assert compare_semantics(
        {key: eager_projection[key] for key in ("status", "accesses", "observed_not_demanded",
                                                  "counts", "frontier")},
        {key: lazy_projection[key] for key in ("status", "accesses", "observed_not_demanded",
                                                 "counts", "frontier")})["exact"]
    eager_pairs = pair_accesses(req, eager_projection, execution)
    lazy_pairs = pair_accesses(req, lazy_projection, execution)
    eager_protection = build_protection_overlay(req, eager_projection, execution, eager_pairs)
    lazy_protection = build_protection_overlay(req, lazy_projection, execution, lazy_pairs)
    eager_graph = build_candidate_graph(req, eager_projection, execution, eager_protection, eager_pairs)
    lazy_graph = build_candidate_graph(req, lazy_projection, execution, lazy_protection, lazy_pairs)
    assert compare_semantics(
        {key: eager_protection[key] for key in ("status", "protections", "counts", "frontier")},
        {key: lazy_protection[key] for key in ("status", "protections", "counts", "frontier")})["exact"]
    graph_fields = ("status", "accesses", "candidates", "exclusions", "atomic_handoff",
                    "completeness", "counts", "frontier")
    assert compare_semantics({key: eager_graph[key] for key in graph_fields},
                             {key: lazy_graph[key] for key in graph_fields})["exact"]
    assert len(lazy_graph["candidates"]) == 1


def test_projection_covers_unknown_instance_object_and_effect_access_budgets():
    empty_execution = concurrent_access_document(
        "ExecutionInstanceBindingOverlay", scope_id="scope", request_hash=A, status="complete",
        roots=[], contexts=[], instances=[], invocations=[], mhp=[], exclusions=[], counts={},
        dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    limited = request(effects=1, accesses=1)
    summaries = [summary(effect_id="one"), summary(effect_id="two", kind="read")]
    result = build_projection(limited, plan(), root_overlay(), summaries, empty_execution)
    codes = {item["code"] for item in result["frontier"]}
    assert {"effects-budget-exhausted", "object-domain-unknown", "execution-instance-unknown"} <= codes
    duplicate = thread_graph()
    duplicate["effects"].append(deepcopy(duplicate["effects"][0]))
    execution = build_execution_overlay(request(), plan(), root_overlay(), root_indexes=[root_index()],
                                        thread_graphs=[duplicate])
    result = build_projection(request(), plan(), root_overlay(), [], execution,
                              thread_graphs=[duplicate], provenance_graph=provenance())
    assert len(result["accesses"]) == 2


def test_projection_lineage_dependency_and_missing_demand_degrade_nonempty():
    execution = build_execution_overlay(request(), plan(), root_overlay())
    ast_request = request(bc_digest=None, binding_digest=None)
    result = build_projection(ast_request, plan(), root_overlay(), [], execution)
    codes = {item["code"] for item in result["frontier"]}
    assert {"ast-only-access-evidence", "demanded-effect-missing"} <= codes
    ir_request = request(source_digest=None, binding_digest=None)
    partial_summary = summary(); partial_summary["status"] = "partial"; partial_summary["frontier"] = []
    partial_provenance = provenance(status="partial")
    result = build_projection(ir_request, plan(), root_overlay(), [partial_summary], execution,
                              provenance_graph=partial_provenance)
    codes = {item["code"] for item in result["frontier"]}
    assert {"ir-only-source-evidence", "effect-summary-incomplete",
            "object-provenance-incomplete"} <= codes
    invalid = summary(); invalid["effects"][0]["size_bytes"] = "bad"
    invalid["effects"][0]["address"]["byte_range"] = {"offset": 3, "size": 2}
    invalid["effects"].append({**deepcopy(invalid["effects"][0]), "id": "second",
                               "source": {"id": "second"}})
    result = build_projection(request(accesses=1), plan(), root_overlay(), [invalid], execution,
                              provenance_graph=provenance())
    assert result["accesses"][0]["byte_range"] == {"offset": 3, "size": 2}
    assert any(item["code"] == "accesses-budget-exhausted" for item in result["frontier"])


def access(access_id, instance, operation, objects, *, state="must", atomic=False, source_ids=()):
    return {"id": access_id, "execution_instance_id": instance, "operation": operation,
            "atomic": atomic, "volatile": False, "ordering": "relaxed" if atomic else None,
            "failure_ordering": None, "guards": [], "object_domain_id": "d",
            "object_domain": domain(state, objects, "unknown" if state == "unknown" else None),
            "byte_range": {"offset": 0, "size": 4}, "evidence": [access_id],
            "source_access_ids": list(source_ids)}


def execution_document(instances, mhp, status="complete"):
    return concurrent_access_document(
        "ExecutionInstanceBindingOverlay", scope_id="scope", request_hash=A, status=status,
        roots=[], contexts=[], instances=sorted(instances, key=lambda item: item["id"]), invocations=[],
        mhp=sorted(mhp, key=lambda item: item["id"]), exclusions=[], counts={"instances": len(instances)},
        dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)


def projection_document(accesses, status="complete", frontier=None):
    return concurrent_access_document(
        "ConcurrentAccessProjectionFacts", scope_id="scope", request_hash=A, status=status,
        accesses=sorted(accesses, key=lambda item: item["id"]), observed_not_demanded=[],
        counts={"effects": len(accesses), "accesses": len(accesses)}, dependencies=[],
        diagnostics=frontier or [], frontier=frontier or [], semantic_digest=None)


def mhp(left, right, disposition="parallel-possible"):
    pair = sorted((left, right))
    return {"id": f"{pair[0]}:{pair[1]}:{disposition}", "left": pair[0], "right": pair[1],
            "disposition": disposition, "guards": [], "proof": ["proof"], "reason": "test"}


@pytest.mark.parametrize("left,right,expected", [
    (domain("must", [object_value("a")]), domain("must", [object_value("b")]), "must-overlap"),
    (domain("may", [object_value("a"), object_value("b", "other")]),
     domain("must", [object_value("a")]), "may-overlap"),
    (domain("must", [object_value("a", offset=0, size=4)]),
     domain("must", [object_value("b", offset=8, size=4)]), "must-disjoint"),
    (domain("unknown", [], "missing"), domain("must", [object_value("a")]), "unknown"),
])
def test_object_overlap_lattice(left, right, expected):
    a = access("a", "i1", "read", []); a["object_domain"] = left
    b = access("b", "i2", "write", []); b["object_domain"] = right
    assert object_overlap(a, b)[0] == expected
    union_a = access("ua", "i1", "read", [object_value("u1", union="u")])
    union_b = access("ub", "i2", "write", [object_value("u2", union="u")])
    assert object_overlap(union_a, union_b)[0] == "must-overlap"
    unknown_storage = access("x", "i1", "read", [object_value("x", kind="unknown")])
    assert object_overlap(unknown_storage, b)[0] == "unknown"


def test_pairing_generates_candidates_read_read_disjoint_not_parallel_and_self_repeated():
    shared = object_value()
    accesses = [
        access("a-read", "i1", "read", [shared]), access("b-write", "i2", "write", [shared]),
        access("c-read", "i2", "read", [shared]),
        access("d-write", "i3", "write", [object_value("far", offset=8)]),
        access("e-write", "rep", "write", [shared]),
    ]
    instances = [{"id": "i1", "cardinality": "single"}, {"id": "i2", "cardinality": "single"},
                 {"id": "i3", "cardinality": "single"}, {"id": "rep", "cardinality": "repeated"}]
    relations = [mhp("i1", "i2"), mhp("i1", "i3", "not-parallel"), mhp("rep", "rep")]
    result = pair_accesses(request(), projection_document(accesses), execution_document(instances, relations))
    assert any({item["left"], item["right"]} == {"a-read", "b-write"} for item in result["candidates"])
    assert any(item["left"] == item["right"] == "e-write" for item in result["candidates"])
    reasons = {item["reason"] for item in result["exclusions"]}
    assert {"read-read", "proven-not-parallel", "must-disjoint"} & reasons


def test_pairing_unknowns_do_not_cartesian_expand_and_budgets_are_frontier():
    shared = object_value()
    accesses = [access("unknown", "i1", "write", [], state="unknown"),
                access("a", "i1", "write", [shared]), access("b", "i2", "write", [shared])]
    instances = [{"id": "i1", "cardinality": "single"}, {"id": "i2", "cardinality": "single"}]
    result = pair_accesses(request(), projection_document(accesses), execution_document(instances, []))
    assert not result["candidates"] and any(item["code"] == "object-bucket-unknown" for item in result["frontier"])
    limits = request(object_candidates=1, buckets=1, alias_comparisons=1, mhp_queries=1,
                     candidate_pairs=1, exclusions=1)
    result = pair_accesses(limits, projection_document(accesses[1:]),
                           execution_document(instances, [mhp("i1", "i2")]))
    assert result["frontier"]


def test_pairing_all_budget_exclusions_unknown_overlap_and_multi_bucket_dedup():
    first, second = object_value("one", "s1"), object_value("two", "s2")
    many = [access("a", "i1", "write", [first, second], state="may"),
            access("b", "i2", "write", [first, second], state="may"),
            access("c", "i3", "write", [first, second], state="may")]
    instances = [{"id": name, "cardinality": "single"} for name in ("i1", "i2", "i3")]
    relations = [mhp("i1", "i2"), mhp("i1", "i3"), mhp("i2", "i3")]
    result = pair_accesses(request(candidate_pairs=1, alias_comparisons=2),
                           projection_document(many), execution_document(instances, relations))
    codes = {item["code"] for item in result["frontier"]}
    assert "candidate-pair-budget-exhausted" in codes or "alias-comparison-budget-exhausted" in codes
    assert len(result["candidates"]) <= 1

    reads = [access("r1", "i1", "read", [first]), access("r2", "i2", "read", [first]),
             access("r3", "i3", "read", [first])]
    result = pair_accesses(request(exclusions=1), projection_document(reads),
                           execution_document(instances, relations))
    assert any(item["code"] == "exclusions-budget-exhausted" for item in result["frontier"])

    missing = access("missing", None, "write", [first])
    known = access("known", "i1", "write", [first])
    result = pair_accesses(request(), projection_document([missing, known]),
                           execution_document(instances[:1], []))
    assert any(item["code"] == "execution-instance-unknown" for item in result["frontier"])
    unknown_range = object_value("range", "s1"); unknown_range["byte_range"] = {"offset": None, "size": None}
    result = pair_accesses(request(), projection_document([
        access("u1", "i1", "write", [unknown_range]), access("u2", "i2", "write", [unknown_range])]),
        execution_document(instances[:2], [mhp("i1", "i2")]))
    assert any(item["code"] == "object-overlap-unknown" for item in result["frontier"])


def test_pairing_scale_uses_object_buckets_not_global_cartesian_product():
    accesses = [access(f"a-{number}", f"i-{number}", "write",
                       [object_value(f"o-{number}", f"storage-{number}")]) for number in range(200)]
    instances = [{"id": f"i-{number}", "cardinality": "single"} for number in range(200)]
    result = pair_accesses(request(), projection_document(accesses),
                           execution_document(instances, []))
    assert result["counts"]["buckets"] == 200
    assert result["counts"]["alias_comparisons"] == 0
    assert not result["candidates"]


def raii_graph(*, exact=True, both=True, partial=False):
    regions = [
        {"id": "r1", "status": "complete", "access_ids": ["a4-left"], "thread_id": "i1",
         "owner_id": "owner-1", "mutex_ids": ["mutex"], "guard": None},
        {"id": "r2", "status": "complete", "access_ids": ["a4-right"] if both else [], "thread_id": "i2",
         "owner_id": "owner-2", "mutex_ids": ["mutex"], "guard": None},
    ]
    return {"kind": "CppRaiiSynchronizationGraph", "scope_id": "scope", "semantic_digest": A,
            "status": "partial" if partial else "complete",
            "mutexes": [{"id": "mutex", "object_id": "mutex-object",
                         "resolution": "exact" if exact else "unknown",
                         "mutex_kind": "plain"}], "held_regions": regions,
            "proofs": [{"id": "proof", "proof_kind": "mutual-exclusion", "status": "complete",
                        "mutex_id": "mutex", "region_ids": ["r1", "r2"], "thread_ids": ["i1", "i2"],
                        "evidence": ["lock", "unlock"],
                        "limitations": ["bounded-same-plain-mutex"]}], "frontier": []}


def candidate_fixture(atomic=False, operation="write"):
    shared = object_value()
    accesses = [access("left", "i1", "read", [shared], source_ids=["a4-left"]),
                access("right", "i2", operation, [shared], atomic=atomic, source_ids=["a4-right"])]
    projection = projection_document(accesses)
    execution = execution_document([{"id": "i1", "cardinality": "single"},
                                    {"id": "i2", "cardinality": "single"}], [mhp("i1", "i2")])
    pairs = pair_accesses(request(), projection, execution)
    return projection, execution, pairs


def test_protection_requires_complete_exact_access_regions_and_budget():
    projection, execution, pairs = candidate_fixture()
    protected = build_protection_overlay(request(), projection, execution, pairs,
                                         raii_graphs=[raii_graph()])
    assert protected["protections"][0]["status"] == "protected-within-bounded-model"
    ambiguous = build_protection_overlay(request(), projection, execution, pairs,
                                         raii_graphs=[raii_graph(exact=False)])
    assert ambiguous["status"] == "partial" and ambiguous["frontier"][0]["code"] == "protection-unknown"
    outside = build_protection_overlay(request(), projection, execution, pairs,
                                       raii_graphs=[raii_graph(both=False)])
    assert not outside["protections"] and outside["frontier"]
    limited = build_protection_overlay(request(protection_queries=1), projection, execution,
                                       {"candidates": pairs["candidates"] * 2}, raii_graphs=[])
    assert any(item["code"] == "protection-query-budget-exhausted" for item in limited["frontier"])
    incomplete = raii_graph(partial=True); incomplete["frontier"] = []
    result = build_protection_overlay(request(), projection, execution, pairs,
                                      raii_graphs=[incomplete])
    assert any(item["code"] == "synchronization-evidence-incomplete" for item in result["frontier"])
    invalid = raii_graph(); invalid["proofs"].insert(0, {"id": "other", "proof_kind": "ordering",
                                                         "status": "complete"})
    invalid["proofs"].insert(1, {"id": "missing-region", "proof_kind": "mutual-exclusion",
                                  "status": "complete", "region_ids": ["absent"],
                                  "thread_ids": [], "mutex_id": "mutex"})
    assert build_protection_overlay(request(), projection, execution, pairs,
                                    raii_graphs=[invalid])["protections"]


def test_graph_report_atomic_boundary_partial_and_failure_semantics():
    projection, execution, pairs = candidate_fixture(atomic=True, operation="rmw")
    protection = build_protection_overlay(request(), projection, execution, pairs,
                                          raii_graphs=[raii_graph()])
    graph = build_candidate_graph(request(), projection, execution, protection, pairs)
    assert graph["status"] == "partial"
    assert graph["candidates"][0]["protection"] == "protected-within-bounded-model"
    assert graph["atomic_handoff"][0]["consumer"] == "A6"
    assert any(item["code"] == "advanced-atomic-semantics-unsupported" for item in graph["frontier"])
    report = build_report(request(), graph, hits=2, misses=3)
    assert report["exit_code"] == 2 and report["safety"] == "not_evaluated" and report["findings"] is None
    assert report["cache"] == {"hits": 2, "misses": 3}
    failed = failed_report("bad", "失败", "failed")
    assert failed["exit_code"] == 1 and failed["frontier"][0]["detail_en"].endswith("failed")


def test_complete_graph_with_atomic_read_write_has_exit_zero_but_no_findings():
    projection, execution, pairs = candidate_fixture(atomic=True)
    protection = build_protection_overlay(request(), projection, execution, pairs)
    graph = build_candidate_graph(request(), projection, execution, protection, pairs)
    assert graph["status"] == "complete" and graph["atomic_handoff"][0]["consumer"] == "P4-or-A6"
    report = build_report(request(), graph)
    assert report["exit_code"] == 0 and report["counts"]["candidates"] == 1
    assert report["findings"] is None and report["safety"] == "not_evaluated"
