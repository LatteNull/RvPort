from copy import deepcopy

from memory_order_analyzer.contracts import canonical, identity
from memory_order_analyzer.root_analysis import (
    _entry, _exact_call_edges, adapt_cpp_candidates, adapt_ir_candidates, adapt_source_candidates, align_creation_sites,
    build_analysis_plan, build_root_report, discover_execution_roots, failed_root_report,
)
from memory_order_analyzer.root_contracts import expected_root_protocol, root_document


A, B, C = "a" * 64, "b" * 64, "c" * 64


def member(language="c"):
    return {"physical_tu_id": "tu", "profile_id": A, "language": language,
            "standard": "c11" if language == "c" else "c++20", "evidence": [{
                "kind": "ModuleFacts", "id": A, "digest": B, "path": f"facts/{A}.json"}]}


def request(language="c", **changes):
    fields = dict(scope_id="scope", closed_scope=True, discover_main=True,
                  members=[member(language)], global_evidence=[], explicit_roots=[],
                  budgets=deepcopy(expected_root_protocol()["budgets"]), semantic_digest=None)
    fields.update(changes)
    return root_document("ExecutionRootDiscoveryRequest", **fields)


def source_facts(callback="worker", *, status="candidate"):
    return {"nodes": [{"id": "create", "source": {"line": 2}}, {"id": callback}],
            "relations": [
                {"id": "r-create", "kind": "pthread_create", "from": "create", "to": "pthread",
                 "source": {"line": 2}, "status": status, "reason": None},
                {"id": "r-callback", "kind": "callback", "from": "create", "to": callback,
                 "source": {"line": 2}, "status": status, "reason": None}]}


def binding(callback="worker", callback_ir="worker"):
    return {"expression_bindings": [{"source_id": "create", "resolution": "exact",
              "targets": [{"artifact_key": A, "function_id": "main", "id": "call"}]}],
            "entity_bindings": [{"source_id": callback, "resolution": "exact",
              "targets": [{"artifact_key": A, "function_id": None, "id": callback_ir}]}]}


def thread_facts(callback="worker", *, direct=True, count=1):
    targets = [{"artifact_key": A, "function_id": None, "id": callback}]
    if count == 2:
        targets.append({"artifact_key": A, "function_id": None, "id": "other"})
    return {"origin": {"artifact_key": A}, "calls": [{
        "source": {"artifact_key": A, "function_id": "main", "id": "call"},
        "function": {"artifact_key": A, "function_id": None, "id": "main"},
        "symbol": "pthread_create", "direct": direct, "status": "candidate" if direct else "unknown",
        "callback_targets": targets, "arguments": [None, None, None, None], "reason": None}]}


def module(calls=()):
    return {"artifact_key": A, "functions": [
        {"id": "main", "name": "main", "declaration": False, "linkage": "external"},
        {"id": "worker", "name": "worker", "declaration": False, "linkage": "internal"},
        {"id": "leaf", "name": "leaf", "declaration": False, "linkage": "internal"}],
        "calls": list(calls)}


def evidence(*, source=True, ir=True, bind=True):
    values = {"ModuleFacts": {A: module()}, "dependencies": [], "by_member": {"tu": {}}}
    if source:
        values["SourceSemanticFacts"] = {"tu": source_facts()}; values["by_member"]["tu"]["SourceSemanticFacts"] = source_facts()
    if ir:
        values["ThreadLocalFacts"] = {A: thread_facts()}; values["by_member"]["tu"]["ThreadLocalFacts"] = thread_facts()
    if bind:
        values["SourceIRBinding"] = {"scope": binding()}
    return values


def test_source_and_ir_adapters_preserve_proof_boundaries():
    assert _entry(None) is None and _entry({"artifact_key": A}) is None
    src = adapt_source_candidates(member(), source_facts(), binding())
    assert src[0]["status"] == "candidate" and src[0]["callback_entry"]["function_id"] == "worker"
    assert adapt_source_candidates(member(), source_facts(status="unknown"), binding())[0]["status"] == "unknown"
    ir = adapt_ir_candidates(member(), thread_facts())
    assert ir[0]["status"] == "exact" and ir[0]["arguments"] == [{"kind": "null"}]
    assert adapt_ir_candidates(member(), thread_facts(direct=False))[0]["status"] == "unsupported"
    assert adapt_ir_candidates(member(), thread_facts(count=2))[0]["status"] == "ambiguous"
    assert adapt_source_candidates(member(), None) == [] and adapt_ir_candidates(member(), None) == []
    unrelated = thread_facts(); unrelated["calls"].append({"symbol": "pthread_join"})
    assert len(adapt_ir_candidates(member(), unrelated)) == 1


def test_cpp_adapter_requires_cpp_exact_callable_wrapper_and_binding():
    local = {"callables": [{"id": "cb", "resolution": "exact", "source_nodes": ["worker"],
                            "targets": ["worker"], "ir_nodes": ["ir-worker"]}],
             "operations": [{"id": "op", "operation": "construct", "callable_id": "cb",
                             "outcome": "success", "wrapper_role": "construct-attempt",
                             "source_nodes": ["construct"], "ir_nodes": ["ir-call"]}]}
    assert adapt_cpp_candidates(member("c"), local, binding()) == []
    exact = adapt_cpp_candidates(member("c++"), local, binding())
    assert exact[0]["status"] == "exact" and exact[0]["callback_entry"]["function_id"] == "worker"
    broken = deepcopy(local); broken["operations"][0]["outcome"] = "unknown"
    assert adapt_cpp_candidates(member("c++"), broken, binding())[0]["status"] == "unsupported"
    ambiguous = deepcopy(local); ambiguous["callables"][0]["resolution"] = "ambiguous"
    assert adapt_cpp_candidates(member("c++"), ambiguous, binding())[0]["status"] == "ambiguous"
    skipped = deepcopy(local); skipped["operations"].append({"id": "join", "operation": "join"})
    assert len(adapt_cpp_candidates(member("c++"), skipped, binding())) == 1


def test_union_alignment_classifications_and_zero_diagnostic():
    dual = align_creation_sites(request(), evidence())
    assert dual["counts"]["dual-exact"] == 1 and dual["status"] == "complete"
    ir_only = align_creation_sites(request(), evidence(source=False, bind=False))
    assert ir_only["sites"][0]["classification"] == "ir-exact"
    source_only = align_creation_sites(request(), evidence(ir=False))
    assert source_only["sites"][0]["classification"] == "source-candidate" and source_only["status"] == "partial"
    mismatch = evidence(); mismatch["by_member"]["tu"]["ThreadLocalFacts"] = thread_facts("other")
    assert align_creation_sites(request(), mismatch)["sites"][0]["classification"] == "ambiguous"
    empty = align_creation_sites(request(), {"ModuleFacts": {A: module()}, "dependencies": [], "by_member": {"tu": {}}})
    assert empty["status"] == "complete" and empty["diagnostics"][0]["code"] == "thread-creation-site-zero"
    failed = align_creation_sites(request(), {"ModuleFacts": {A: module()}, "dependencies": [],
        "by_member": {"tu": {"ThreadLocalFacts": {"status": "failed", "calls": []}}}})
    assert failed["sites"][0]["classification"] == "failed"


def test_alignment_multiple_bindings_cpp_and_candidate_budgets():
    facts = source_facts(); second = deepcopy(facts["relations"])
    for item in second:
        item["id"] += "-2"; item["from"] = "create-2"
    facts["relations"].extend(second)
    bind = binding(); bind["expression_bindings"].append({"source_id": "create-2", "resolution": "exact",
        "targets": [{"artifact_key": A, "function_id": "main", "id": "call"}]})
    ev = evidence(); ev["by_member"]["tu"]["SourceSemanticFacts"] = facts; ev["SourceIRBinding"] = {"scope": bind}
    assert any(item["reason"] == "multiple-source-candidates-for-ir-call"
               for item in align_creation_sites(request(), ev)["sites"])
    req = request(); req["budgets"]["source_candidates"] = 1
    req["semantic_digest"] = None
    req = root_document("ExecutionRootDiscoveryRequest", **{k: v for k, v in req.items()
                        if k not in {"schema_version", "kind", "analysis_version", "policy_id"}})
    result = align_creation_sites(req, ev)
    assert any(item["code"] == "source_candidates-budget-exhausted" for item in result["frontier"])

    local = {"callables": [{"id": "cb", "resolution": "exact", "source_nodes": ["worker"],
                             "targets": ["worker"], "ir_nodes": ["ir-worker"]}],
             "operations": [{"id": "op", "operation": "construct", "callable_id": "cb",
                             "outcome": "success", "wrapper_role": "construct-attempt",
                             "source_nodes": ["construct"], "ir_nodes": ["ir-call"]}]}
    cpp_ev = {"ModuleFacts": {A: module()}, "SourceIRBinding": {"scope": binding()},
              "dependencies": [], "by_member": {"tu": {"CppThreadLocalFacts": local}}}
    cpp_sites = align_creation_sites(request("c++"), cpp_ev)
    assert cpp_sites["sites"][0]["mechanism"] == "std-thread"


def test_discovery_main_explicit_thread_context_and_instance_separation():
    req = request(explicit_roots=[{"id": "export", "kind": "exported",
        "entry": {"artifact_key": A, "function_id": "leaf"}, "source_entity_id": None, "arguments": []}])
    ev = evidence(); sites = align_creation_sites(req, ev)
    roots = discover_execution_roots(req, sites, ev)
    assert {item["kind"] for item in roots["roots"]} == {"main", "exported", "pthread"}
    thread = next(item for item in roots["roots"] if item["kind"] == "pthread")
    assert thread["thread_context_key"] != thread["thread_instance_key"]
    duplicate = deepcopy(sites["sites"][0]); duplicate["id"] = C
    more = root_document("ThreadCreationSiteIndex", scope_id="scope", request_hash=identity(req), status="complete",
        sites=sorted([sites["sites"][0], duplicate], key=lambda x: x["id"]), counts={}, dependencies=[],
        diagnostics=[], frontier=[], semantic_digest=None)
    repeated = discover_execution_roots(req, more, ev)
    thread_roots = [item for item in repeated["roots"] if item["kind"] == "pthread"]
    assert len({item["thread_context_key"] for item in thread_roots}) == 1
    assert len({item["thread_instance_key"] for item in thread_roots}) == 2


def test_main_ambiguity_missing_explicit_and_zero_roots_are_conservative():
    ev = evidence(ir=False, source=False, bind=False)
    ev["ModuleFacts"] = {A: module(), B: {**module(), "artifact_key": B}}
    sites = align_creation_sites(request(), {**ev, "by_member": {"tu": {}}})
    roots = discover_execution_roots(request(), sites, ev)
    assert roots["status"] == "partial" and any(x["code"] == "main-root-ambiguous" for x in roots["frontier"])
    req = request(discover_main=False, explicit_roots=[{"id": "bad", "kind": "program",
        "entry": {"artifact_key": A, "function_id": "missing"}, "source_entity_id": None, "arguments": []}])
    roots = discover_execution_roots(req, sites, evidence(ir=False, source=False, bind=False))
    assert roots["roots"][0]["status"] == "partial"
    partial_plan = build_analysis_plan(req, sites, roots, evidence(ir=False, source=False, bind=False))
    assert partial_plan["status"] == "partial"
    assert {item["code"] for item in partial_plan["frontier"]} >= {
        "execution-root-incomplete", "execution-root-plan-empty"}
    zero = discover_execution_roots(request(discover_main=False), sites, evidence(ir=False, source=False, bind=False))
    assert any(x["code"] == "execution-root-zero" for x in zero["frontier"])
    zero_plan = build_analysis_plan(request(discover_main=False), sites, zero,
                                    evidence(ir=False, source=False, bind=False))
    assert any(x["code"] == "execution-root-plan-empty" for x in zero_plan["frontier"])
    absent_ev = evidence(ir=False, source=False, bind=False); absent_ev["ModuleFacts"][A]["functions"] = [
        item for item in absent_ev["ModuleFacts"][A]["functions"] if item["name"] != "main"]
    absent = discover_execution_roots(request(), sites, absent_ev)
    assert any(x["code"] == "main-root-absent" for x in absent["diagnostics"])
    budget = deepcopy(expected_root_protocol()["budgets"]); budget["roots"] = 1
    limited = discover_execution_roots(request(budgets=budget), align_creation_sites(request(budgets=budget), evidence()), evidence())
    assert any(x["code"] == "roots-budget-exhausted" for x in limited["frontier"])


def test_plan_reachability_demands_subrequests_overlay_and_report():
    req = request("c++")
    ev = evidence(); ev["ModuleFacts"][A] = module([{"id": "c", "kind": "direct", "function": "main", "target": "leaf"}])
    sites = align_creation_sites(req, ev); roots = discover_execution_roots(req, sites, ev)
    plan = build_analysis_plan(req, sites, roots, ev)
    entries = {item["entry"]["function_id"] for item in plan["reachable_functions"]}
    assert entries >= {"main", "worker", "leaf"}
    assert plan["p2_requests"] and plan["p3_requests"] and plan["demands"]
    report = build_root_report(req, sites, roots, plan, hits=1, misses=2)
    assert report["safety"] == "not_evaluated" and report["findings"] is None
    assert report["cache"] == {"hits": 1, "misses": 2}
    failed = failed_root_report("bad", "坏", "bad")
    assert failed["exit_code"] == 1 and failed["diagnostics"][0]["detail_en"]


def test_plan_open_scope_missing_definition_and_budgets_produce_frontier():
    budgets = deepcopy(expected_root_protocol()["budgets"]); budgets["functions"] = 1; budgets["call_edges"] = 1
    req = request(closed_scope=False, budgets=budgets)
    ev = evidence(); ev["ModuleFacts"][A] = module([{"id": "c", "kind": "direct", "function": "main", "target": "leaf"}])
    sites = align_creation_sites(req, ev); roots = discover_execution_roots(req, sites, ev)
    plan = build_analysis_plan(req, sites, roots, ev)
    codes = {item["code"] for item in plan["frontier"]}
    assert "open-scope-frontier" in codes and "functions-budget-exhausted" in codes


def test_cross_tu_edges_recursion_relevant_unknown_overlay_reconciliation_and_frontier_limit():
    relation = {"id": "r", "kind": "call", "from": "call-source", "to": "leaf-source"}
    source = {"relations": [relation]}
    bind = {"expression_bindings": [{"source_id": "call-source", "resolution": "exact",
             "targets": [{"artifact_key": A, "function_id": "main", "id": "call-a1"}]}],
            "entity_bindings": [{"source_id": "leaf-source", "resolution": "exact",
             "targets": [{"artifact_key": A, "function_id": None, "id": "leaf"}]}]}
    summary = {"adoptions": [
        {"kind": "unique-definition", "call": {"artifact_key": A, "function_id": "leaf", "id": "call-p2"},
         "target": {"artifact_key": A, "function_id": None, "id": "worker"}},
        {"kind": "unknown", "call": {}, "target": {}}],
        "invocations": [{"function": {"artifact_key": A, "function_id": None, "id": "main"}}]}
    ev = {"ModuleFacts": {A: module([{"id": "self", "kind": "direct", "function": "main", "target": "main"}])},
          "SourceIRBinding": {"scope": bind}, "SourceSemanticFacts": {"tu": source},
          "EffectSummary": {"ctx": summary}, "ThreadLocalFacts": {A: thread_facts()},
          "dependencies": [], "by_member": {"tu": {"ThreadLocalFacts": thread_facts()}}}
    edges = _exact_call_edges(ev)
    assert {item["proof"] for item in edges} == {"p1-local-direct", "a1-exact-binding", "p2-adoption"}
    req = request("c++", closed_scope=False)
    sites = align_creation_sites(req, ev)
    # Add a source-only relevant site and an exact std::thread site.
    candidate = deepcopy(sites["sites"][0]); candidate["id"] = B; candidate["classification"] = "source-candidate"
    candidate["callsite"]["caller_entry"] = {"artifact_key": A, "function_id": "main"}
    std = deepcopy(sites["sites"][0]); std["id"] = C; std["mechanism"] = "std-thread"; std["classification"] = "dual-exact"
    sites = root_document("ThreadCreationSiteIndex", scope_id="scope", request_hash=identity(req), status="partial",
        sites=sorted([*sites["sites"], candidate, std], key=lambda x: x["id"]), counts={}, dependencies=[],
        diagnostics=[], frontier=[], semantic_digest=None)
    roots = discover_execution_roots(req, sites, ev)
    plan = build_analysis_plan(req, sites, roots, ev)
    assert any(item["proof"] == "p2-adoption" for item in plan["call_edges"])
    assert plan["a3_overlays"] and plan["reconciliation"]["deep_observed_functions"] == 1
    assert any(item["code"] == "candidate-relevant-thread-creation-incomplete" for item in plan["frontier"])

    # Two roots share a context, one points outside the inventory, and budgets force call/frontier cuts.
    budget = deepcopy(expected_root_protocol()["budgets"]); budget["call_edges"] = 1
    budget["frontier_items"] = 1; budget["contexts"] = 1; budget["wrapper_depth"] = 0
    req2 = request("c++", closed_scope=False, budgets=budget)
    duplicate_roots = deepcopy(roots); duplicate = deepcopy(duplicate_roots["roots"][0]); duplicate["id"] = "z" * 64
    duplicate_roots["roots"].append(duplicate)
    duplicate_roots["roots"].append({**deepcopy(duplicate), "id": "y" * 64,
        "entry": {"artifact_key": A, "function_id": "missing"},
        "thread_context_key": identity({"missing": True})})
    duplicate_roots["roots"] = sorted(duplicate_roots["roots"], key=lambda x: x["id"])
    duplicate_roots["semantic_digest"] = None
    duplicate_roots = root_document("ExecutionRootIndex", **{k: v for k, v in duplicate_roots.items()
        if k not in {"schema_version", "kind", "analysis_version", "policy_id"}})
    cut = build_analysis_plan(req2, sites, duplicate_roots, ev)
    assert any(item["code"] == "frontier-budget-exhausted" for item in cut["frontier"])
    assert any(len(item["root_ids"]) > 1 for item in cut["contexts"])
