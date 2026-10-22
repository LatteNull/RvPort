from copy import deepcopy

from memory_order_analyzer.contracts import identity
from memory_order_analyzer.thread_entry_analysis import (
    _anchor, _broker_paths, _cpp_local_candidates, _entry, _matches, _module_broker_candidates,
    _thread_local_candidates, build_local_facts, build_report, build_root_overlay, build_site_index,
    failed_report, source_candidates,
)
from memory_order_analyzer.thread_entry_contracts import expected_thread_entry_protocol, thread_entry_document
from memory_order_analyzer.thread_entry_profiles import c_api_profile, model_profile


A, B, C = "a" * 64, "b" * 64, "c" * 64
ENTRY = {"artifact_key": A, "function_id": "worker"}


def profiles():
    common = dict(vendor="test", version="1", language="c++", target="x86_64-pc-linux-gnu",
                  data_layout="e-p:64:64", abi="itanium")
    return sorted([
        c_api_profile("pthread", "x86_64-pc-linux-gnu", "e-p:64:64"),
        c_api_profile("c11-thread", "x86_64-pc-linux-gnu", "e-p:64:64"),
        model_profile(api_family="std-thread", standards=("c++17", "c++20"), **common),
        model_profile(api_family="std-jthread", standards=("c++20",), **common),
        model_profile(api_family="std-async", standards=("c++17", "c++20"), **common),
    ], key=lambda item: item["id"])


def request(language="c", standard="c11", **updates):
    fields = {
        "scope_id": "scope", "closed_scope": True,
        "members": [{"physical_tu_id": "tu", "profile_id": A, "language": language,
                     "standard": standard, "evidence": []}],
        "global_evidence": [], "model_profiles": profiles(), "framework_descriptors": [],
        "budgets": deepcopy(expected_thread_entry_protocol()["budgets"]), "semantic_digest": None,
    }
    fields.update(updates)
    return thread_entry_document("ThreadEntryDiscoveryRequest", **fields)


def candidate(layer, *, api="pthread", site="site", status="exact", operation="create",
              entry=ENTRY, policy="not-applicable", evidence=None, reason=None, metadata=None):
    return {
        "id": identity({"layer": layer, "api": api, "site": site, "status": status, "policy": policy}),
        "layer": layer, "physical_tu_id": "tu", "profile_id": A, "api_family": api,
        "model_id": next(item["id"] for item in profiles() if item["api_family"] == api),
        "callsite_id": site, "operation": operation,
        "callback": {"entry": entry, "source_entity_id": "worker", "candidates": [entry] if entry else []},
        "launch_policy": policy, "guard": {"normal": True},
        "evidence": sorted(evidence or [f"{layer}-evidence"]), "status": status,
        "reason": reason, "metadata": metadata or {},
    }


def local(source=(), ir=(), *, status="complete"):
    return thread_entry_document("ThreadEntryLocalFacts", scope_id="scope", request_hash=A,
        physical_tu_id="tu", profile_id=A, language="c", standard="c11", status=status,
        source_candidates=sorted(source, key=lambda item: item["id"]),
        ir_candidates=sorted(ir, key=lambda item: item["id"]),
        counts={"source": len(source), "ir": len(ir)}, dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)


def test_site_index_dual_ir_source_mismatch_and_zero():
    req = request()
    dual = build_site_index(req, [local([candidate("source")], [candidate("ir")])])
    assert dual["sites"][0]["evidence_status"] == "dual-exact"
    assert dual["sites"][0]["root_disposition"] == "adopted"
    ir_only = build_site_index(req, [local([], [candidate("ir")])])
    assert ir_only["sites"][0]["evidence_status"] == "ir-exact"
    source_only = build_site_index(req, [local([candidate("source")], [])])
    assert source_only["sites"][0]["evidence_status"] == "source-candidate"
    assert source_only["status"] == "partial"
    other = {"artifact_key": B, "function_id": "other"}
    mismatch = build_site_index(req, [local([candidate("source")], [candidate("ir", entry=other)])])
    assert mismatch["sites"][0]["evidence_status"] == "ambiguous"
    assert mismatch["sites"][0]["opposed"] == ["source-ir-callback-disagreement"]
    zero = build_site_index(req, [local()])
    assert zero["status"] == "complete" and zero["diagnostics"][0]["code"] == "thread-entry-site-zero"


def test_operation_and_async_policy_semantics():
    req = request("c++", "c++20")
    default = build_site_index(req, [local([candidate("source", api="std-thread", operation="default", status="excluded")])])
    assert default["sites"][0]["execution_semantics"] == "does-not-create-thread"
    assert default["sites"][0]["root_disposition"] == "excluded"
    deferred = build_site_index(req, [local(
        [candidate("source", api="std-async", policy="deferred")],
        [candidate("ir", api="std-async", policy="deferred")])])
    assert deferred["sites"][0]["root_disposition"] == "excluded"
    default_async = build_site_index(req, [local(
        [candidate("source", api="std-async", policy="default")],
        [candidate("ir", api="std-async", policy="default")])])
    assert default_async["sites"][0]["execution_semantics"] == "may-create-thread"
    assert default_async["sites"][0]["root_disposition"] == "conditional-frontier"
    explicit = build_site_index(req, [local(
        [candidate("source", api="std-async", policy="async")],
        [candidate("ir", api="std-async", policy="async")])])
    assert explicit["sites"][0]["root_disposition"] == "adopted"
    unknown = build_site_index(req, [local([candidate("source", api="std-async", policy="unknown")])])
    assert unknown["sites"][0]["execution_semantics"] == "unknown"


def test_site_budget_and_matching_by_source_ir_binding():
    budgets = deepcopy(expected_thread_entry_protocol()["budgets"]); budgets["sites"] = 1
    req = request(budgets=budgets)
    first = candidate("source", site="one", metadata={"ir_call_ids": ["ir-call"]})
    matched = candidate("ir", site="different", metadata={"ir_call_id": "ir-call"})
    second = candidate("source", site="two")
    result = build_site_index(req, [local([first, second], [matched])])
    assert len(result["sites"]) == 1
    assert any(item["code"] == "sites-budget-exhausted" for item in result["frontier"])


def test_duplicate_observations_collapse_but_distinct_sites_remain():
    req = request()
    first = candidate("source", site="one", evidence=["source-a"])
    duplicate = candidate("source", site="one", evidence=["source-b"])
    duplicate["id"] = identity({"duplicate": True})
    ir = candidate("ir", site="one")
    second_source = candidate("source", site="two")
    second_ir = candidate("ir", site="two")
    result = build_site_index(req, [local([first, duplicate, second_source], [ir, second_ir])])
    assert len(result["sites"]) == 2
    assert all(item["evidence_status"] == "dual-exact" for item in result["sites"])
    merged = next(item for item in result["sites"] if item["callsite_id"] == "one")
    assert {"source-a", "source-b"} <= set(merged["evidence"])


def test_overlay_deduplicates_base_and_separates_context_from_instances():
    req = request()
    sources = [candidate("source", site="one"), candidate("source", site="two")]
    irs = [candidate("ir", site="one"), candidate("ir", site="two")]
    sites = build_site_index(req, [local(sources, irs)])
    first = sites["sites"][0]
    base = {"scope_id": "scope", "roots": [{"id": B, "entry": first["callback"]["entry"],
             "creation_site_id": first["id"], "source_site_id": first["callsite_id"]}]}
    overlay = build_root_overlay(req, sites, base_roots=base)
    assert len(overlay["roots"]) == 1
    assert overlay["reconciliation"]["adopted_from_base"][0]["site_id"] == first["id"]
    assert len(overlay["contexts"]) == 1
    assert overlay["roots"][0]["context_id"] == overlay["contexts"][0]["id"]
    assert base["roots"][0]["id"] == B


def test_overlay_root_and_context_budgets_keep_references_closed():
    budgets = deepcopy(expected_thread_entry_protocol()["budgets"])
    budgets["roots"] = 1; budgets["contexts"] = 1
    req = request(budgets=budgets)
    other_entry = {"artifact_key": B, "function_id": "other"}
    sources = [candidate("source", site="one"), candidate("source", site="two", entry=other_entry)]
    irs = [candidate("ir", site="one"), candidate("ir", site="two", entry=other_entry)]
    overlay = build_root_overlay(req, build_site_index(req, [local(sources, irs)]))
    assert len(overlay["roots"]) == len(overlay["contexts"]) == len(overlay["demands"]) == 1
    assert overlay["roots"][0]["context_id"] == overlay["contexts"][0]["id"]
    assert overlay["demands"][0]["root_id"] == overlay["roots"][0]["id"]
    assert any(item["code"] == "roots-budget-exhausted" for item in overlay["frontier"])


def test_overlay_frontier_report_languages_and_failed_report():
    req = request()
    sites = build_site_index(req, [local([candidate("source")], [])])
    overlay = build_root_overlay(req, sites)
    report = build_report(req, [local([candidate("source")], [])], sites, overlay, hits=1, misses=2)
    assert report["status"] == "partial" and report["exit_code"] == 2
    assert report["safety"] == "not_evaluated" and report["findings"] is None
    assert report["language_counts"]["c11"]["abstention"] == 1
    assert report["cache"] == {"hits": 1, "misses": 2}
    failed = failed_report("bad", "坏", "bad")
    assert failed["exit_code"] == 1 and failed["diagnostics"][0]["detail_en"] == "bad"


def test_overlay_keeps_repeated_cardinality_conditional_and_unrelated_failure():
    req = request()
    source = candidate("source", metadata={"cardinality": "repeated"})
    ir = candidate("ir", metadata={"cardinality": "repeated"})
    complete = local([source], [ir])
    unrelated = thread_entry_document(
        "ThreadEntryLocalFacts", scope_id="scope", request_hash=A,
        physical_tu_id="other", profile_id=B, language="c", standard="c17", status="failed",
        source_candidates=[], ir_candidates=[], counts={"source": 0, "ir": 0}, dependencies=[],
        diagnostics=[], frontier=[{"code": "failed", "detail": "失败", "detail_en": "failed",
                                  "limitation": "限制", "limitation_en": "limit",
                                  "suggestion": None, "suggestion_en": None, "source": None}], semantic_digest=None)
    index = build_site_index(req, [complete, unrelated])
    assert index["sites"][0]["root_disposition"] == "adopted"
    overlay = build_root_overlay(req, index)
    assert overlay["status"] == "partial" and overlay["roots"][0]["cardinality"] == "repeated"
    assert overlay["demands"][0]["kind"] == "reachable-entry"

    cpp_req = request("c++", "c++20")
    conditional = build_site_index(cpp_req, [local(
        [candidate("source", api="std-async", policy="default")],
        [candidate("ir", api="std-async", policy="default")])])
    conditional_overlay = build_root_overlay(cpp_req, conditional)
    assert conditional_overlay["roots"] == []
    assert conditional_overlay["completeness"]["candidate_frontier"] == 1


def test_open_scope_unsupported_api_and_windows_are_frontier():
    open_request = request(closed_scope=False)
    open_index = build_site_index(open_request, [local()])
    assert open_index["status"] == "partial"
    assert any(item["code"] == "thread-entry-open-scope" for item in open_index["frontier"])
    unsupported = candidate("source", status="unsupported", operation="unsupported",
                            entry=None, reason="framework-descriptor-required")
    unsupported["api_family"] = "framework"; unsupported["model_id"] = "builtin:framework"
    unsupported_index = build_site_index(request(), [local([unsupported])])
    assert unsupported_index["sites"][0]["evidence_status"] == "unsupported"
    assert unsupported_index["sites"][0]["root_disposition"] == "frontier"

    windows_request = request()
    thread = {"status": "complete", "origin": {"artifact_key": A}, "calls": [{
        "source": {"artifact_key": A, "function_id": "main", "id": "call"},
        "symbol": "pthread_create", "direct": True, "status": "candidate",
        "callback_targets": [ENTRY], "success_test": None, "handle_source": None,
        "arguments": [None, None, ENTRY, None], "reason": None,
    }]}
    module = {"artifact_key": A, "target": "x86_64-pc-windows-msvc", "layout": "e-p:64:64", "calls": []}
    facts = build_local_facts(windows_request, windows_request["members"][0],
                              {"by_member": {"tu": {"ThreadLocalFacts": thread, "ModuleFacts": module}}})
    assert facts["ir_candidates"][0]["status"] == "unsupported"
    assert any(item["code"] == "thread-entry-platform-excluded" for item in facts["frontier"])


def test_build_local_facts_handles_empty_failed_and_thread_ir():
    req = request()
    empty = build_local_facts(req, req["members"][0], {"by_member": {"tu": {}}})
    assert empty["status"] == "complete" and empty["diagnostics"][0]["code"] == "thread-entry-local-zero"
    failed = build_local_facts(req, req["members"][0], {"by_member": {"tu": {"X": {"status": "failed"}}}})
    assert failed["status"] == "failed" and failed["frontier"]
    thread = {"status": "complete", "origin": {"artifact_key": A}, "calls": [{
        "source": {"artifact_key": A, "function_id": "main", "id": "call"},
        "symbol": "pthread_create", "direct": True, "status": "candidate",
        "callback_targets": [ENTRY], "success_test": {"id": "ok"},
        "handle_source": {"id": "handle"}, "arguments": [None, None, ENTRY, None],
        "reason": None,
    }]}
    facts = build_local_facts(req, req["members"][0], {"by_member": {"tu": {"ThreadLocalFacts": thread}}})
    assert facts["ir_candidates"][0]["api_family"] == "pthread"


def test_c11_thrd_create_uses_source_binding_and_direct_ir_broker():
    req = request()
    source = {
        "physical_tu_id": "tu",
        "nodes": [
            {"id": "call-source", "canonical_type": "int", "source": {"expansion": {"file": "a.c", "line": 3, "column": 10}}, "attributes": []},
            {"id": "worker-source", "canonical_type": "int (void *)", "attributes": []},
        ],
        "relations": [
            {"id": "create-rel", "kind": "thrd_create", "from": "call-source", "to": None,
             "source": {"expansion": {"file": "a.c", "line": 3, "column": 10}}, "status": "exact", "reason": None},
            {"id": "callback-rel", "kind": "thrd-callback", "from": "call-source", "to": "worker-source",
             "source": {"expansion": {"file": "a.c", "line": 3, "column": 10}}, "status": "exact", "reason": None},
        ],
    }
    binding = {
        "scope_id": "scope",
        "entity_bindings": [{"source_id": "worker-source", "resolution": "exact", "targets": [ENTRY]}],
        "expression_bindings": [{"source_id": "call-source", "resolution": "exact", "targets": [{"id": "call-ir"}]}],
    }
    module = {
        "artifact_key": A, "target": "x86_64-pc-linux-gnu", "layout": "e-p:64:64",
        "calls": [{"id": "call-ir", "kind": "direct", "target": "thrd_create", "source": {"line": 3}}],
    }
    evidence = {"by_member": {"tu": {"SourceSemanticFacts": source, "ModuleFacts": module}},
                "SourceIRBinding": {"scope": binding}}
    facts = build_local_facts(req, req["members"][0], evidence)
    assert facts["source_candidates"][0]["status"] == "exact"
    assert facts["ir_candidates"][0]["status"] == "exact"
    index = build_site_index(req, [facts])
    assert index["sites"][0]["evidence_status"] == "dual-exact"
    assert index["sites"][0]["root_disposition"] == "adopted"


def test_cpp_jthread_bounded_wrapper_broker_and_budget_frontier():
    broker = "_verified_jthread_broker"
    profile = model_profile(
        api_family="std-jthread", vendor="test", version="1", language="c++",
        standards=("c++20",), target="x86_64-pc-linux-gnu", data_layout="e-p:64:64", abi="itanium",
        canonical_entities=({"id": "std::jthread", "qualified_name": "std::jthread", "origin": "thread"},),
        brokers=({"role": "construct-attempt", "symbol": broker, "source_binding_required": True},))
    req = request("c++", "c++20", model_profiles=[profile])
    source = {
        "physical_tu_id": "tu",
        "nodes": [
            {"id": "construct", "canonical_type": "std::jthread", "source": {"expansion": {"file": "a.cpp", "line": 4, "column": 3}},
             "attributes": ["thread-entry:canonical-record=std::jthread", "thread-entry:canonical-type=wrapper<std::jthread>",
                            "thread-entry:constructor-kind=callable-construction",
                            "thread-entry:alias-chain=worker_thread|std::jthread"]},
            {"id": "worker-source", "canonical_type": "void ()", "attributes": []},
        ],
        "relations": [
            {"id": "construct-rel", "kind": "cpp-jthread-construct", "from": "construct", "to": None,
             "source": {"expansion": {"file": "a.cpp", "line": 4, "column": 3}}, "status": "candidate", "reason": "requires-profile-and-ir-binding"},
            {"id": "callback-rel", "kind": "cpp-jthread-callback", "from": "construct", "to": "worker-source",
             "source": {"expansion": {"file": "a.cpp", "line": 4, "column": 3}}, "status": "candidate", "reason": None},
        ],
    }
    binding = {"scope_id": "scope",
               "entity_bindings": [{"source_id": "worker-source", "resolution": "exact", "targets": [ENTRY]}],
               "expression_bindings": [{"source_id": "construct", "resolution": "exact", "targets": [{"id": "outer-call"}]}]}
    module = {"artifact_key": A, "target": "x86_64-pc-linux-gnu", "layout": "e-p:64:64",
              "functions": [{"id": "wrapper-id", "name": "wrapper", "declaration": False}],
              "calls": [{"id": "outer-call", "function": "main-id", "kind": "direct", "target": "wrapper", "source": {}},
                        {"id": "broker-call", "function": "wrapper-id", "kind": "direct", "target": broker, "source": {}}]}
    paths, exhausted = _broker_paths(module, module["calls"][0], {broker: {"role": "construct-attempt"}}, 1)
    assert not exhausted and paths[0][2] == ["outer-call", "broker-call"]
    evidence = {"by_member": {"tu": {"SourceSemanticFacts": source, "ModuleFacts": module}},
                "SourceIRBinding": {"scope": binding}}
    facts = build_local_facts(req, req["members"][0], evidence)
    assert facts["source_candidates"][0]["status"] == "exact"
    assert facts["ir_candidates"][0]["status"] == "exact"
    assert build_site_index(req, [facts])["sites"][0]["evidence_status"] == "dual-exact"
    limited = deepcopy(req); limited["budgets"]["wrapper_depth"] = 0
    limited["semantic_digest"] = identity({k: v for k, v in limited.items() if k != "semantic_digest"})
    limited_facts = build_local_facts(limited, limited["members"][0], evidence)
    assert limited_facts["ir_candidates"][0]["reason"] == "wrapper-depth-budget-exhausted"
    alias_limited = deepcopy(req); alias_limited["budgets"]["alias_depth"] = 1
    alias_facts = build_local_facts(alias_limited, alias_limited["members"][0], evidence)
    assert alias_facts["source_candidates"][0]["reason"] == "alias-depth-budget-exhausted"
    assert alias_facts["status"] == "partial"
    type_limited = deepcopy(req); type_limited["budgets"]["type_depth"] = 1
    type_facts = build_local_facts(type_limited, type_limited["members"][0], evidence)
    assert type_facts["source_candidates"][0]["reason"] == "type-depth-budget-exhausted"
    mismatch_evidence = deepcopy(evidence)
    mismatch_evidence["by_member"]["tu"]["ModuleFacts"]["layout"] = "e-p:32:32"
    mismatch = build_local_facts(req, req["members"][0], mismatch_evidence)
    assert any(item["code"] == "thread-entry-model-profile-mismatch" for item in mismatch["frontier"])


def test_low_level_normalizers_and_source_constructor_variants():
    assert _entry(None) is None and _entry({"artifact_key": A}) is None
    assert _entry({"artifact_key": A, "id": "worker"}) == ENTRY
    assert _anchor(None) is None and _anchor({"expansion": "bad"}) is None
    assert _anchor({"line": 1}) is None
    assert _anchor({"spelling": {"file": "a.cpp", "line": 2}})["line"] == 2

    member = request("c++", "c++20")["members"][0]
    models = profiles()
    source = {
        "nodes": [
            {"id": "construct", "canonical_type": "std::thread", "source": {"file": "a.cpp", "line": 4},
             "attributes": ["not-thread-entry", 1, "thread-entry:canonical-record=std::thread",
                            "thread-entry:constructor-kind=default", "thread-entry:launch-policy=bogus"]},
            {"id": "object", "canonical_type": "std::thread", "attributes": [
                "thread-entry:declared-spelled-type=alias", "thread-entry:declared-canonical-type=std::thread",
                "thread-entry:declared-alias-chain=alias|std::thread"]},
            {"id": "worker", "canonical_type": "void ()", "attributes": []},
        ],
        "relations": [
            {"id": "construct-rel", "kind": "cpp-thread-default", "from": "construct", "to": None,
             "source": {"file": "a.cpp", "line": 4}, "status": "candidate", "reason": None},
            {"id": "callback-rel", "kind": "cpp-thread-callback", "from": "construct", "to": "worker",
             "source": {"file": "a.cpp", "line": 4}, "status": "candidate", "reason": None},
            {"id": "object-rel", "kind": "cpp-thread-object", "from": "construct", "to": "object",
             "source": {"file": "a.cpp", "line": 4}, "status": "candidate", "reason": None},
        ],
    }
    binding = {"entity_bindings": [{"source_id": "worker", "resolution": "exact", "targets": [ENTRY]}],
               "expression_bindings": [{"source_id": "construct", "resolution": "exact",
                                         "targets": [{"id": "ir-call"}]}]}
    values = source_candidates(member, source, binding, models)
    assert values[0]["status"] == "excluded" and values[0]["operation"] == "default"
    assert values[0]["metadata"]["spelled_type"] == "alias"
    assert values[0]["metadata"]["alias_chain"] == ["alias", "std::thread"]

    async_source = deepcopy(source)
    async_source["relations"][0].update({"kind": "cpp-async-call", "reason": "bogus"})
    async_source["relations"][1]["kind"] = "cpp-async-callback"
    async_source["relations"] = async_source["relations"][:2]
    async_source["nodes"][0]["attributes"] = ["thread-entry:canonical-record=std::async",
                                                "thread-entry:launch-policy=bogus"]
    values = source_candidates(member, async_source, binding, models)
    assert values[0]["launch_policy"] == "unknown" and values[0]["status"] == "candidate"


def test_ir_local_candidates_cover_skip_move_incomplete_and_unbound_brokers():
    member = request("c++", "c++20")["members"][0]
    models = profiles()
    assert _thread_local_candidates(member, {"calls": [{"symbol": "other"}]}, models) == []
    calls = {"calls": [
        {"symbol": "pthread_create", "source": {"artifact_key": A, "function_id": "main", "id": "one"},
         "direct": False, "status": "unknown", "callback_targets": [ENTRY, {"artifact_key": B, "function_id": "other"}],
         "arguments": [], "reason": "indirect"},
        {"symbol": "thrd_create", "source": {"artifact_key": A, "function_id": "main", "id": "two"},
         "direct": True, "status": "candidate", "callback_targets": [ENTRY], "arguments": [], "reason": None},
    ]}
    result = _thread_local_candidates(member, calls, models)
    assert {item["api_family"] for item in result} == {"pthread", "c11-thread"}
    assert {item["status"] for item in result} == {"unknown", "exact"}

    std_model = next(item for item in models if item["api_family"] == "std-thread")
    facts = {"callables": [
        {"id": "good", "entity_id": "worker", "targets": [ENTRY]},
        {"id": "many", "entity_id": "many", "targets": [ENTRY, {"artifact_key": B, "function_id": "other"}]},
    ], "operations": [
        {"id": "skip", "operation": "join"},
        {"id": "construct", "operation": "construct", "outcome": "success", "callable_id": "good",
         "ir_nodes": ["n"], "source_nodes": ["s"], "guard": None},
        {"id": "incomplete", "operation": "construct", "outcome": "unknown", "callable_id": "many",
         "ir_nodes": [], "source_nodes": ["x"], "guard": None},
        {"id": "move", "operation": "move-construct", "outcome": "success", "callable_id": None,
         "ir_nodes": ["m"], "source_nodes": ["m"], "guard": None},
    ]}
    cpp = _cpp_local_candidates(member, facts, [std_model])
    assert [item["status"] for item in cpp] == ["exact", "candidate", "excluded"]
    assert _cpp_local_candidates(member, facts, []) == []

    direct_model = model_profile(api_family="std-jthread", vendor="x", version="1", language="c++",
        standards=("c++20",), target="x", data_layout="e", abi="itanium",
        brokers=({"role": "construct-attempt", "symbol": "broker", "source_binding_required": False},))
    required_model = model_profile(api_family="std-async", vendor="x", version="1", language="c++",
        standards=("c++20",), target="x", data_layout="e", abi="itanium",
        brokers=({"role": "async-start", "symbol": "bound", "source_binding_required": True},))
    module = {"calls": [
        {"id": "one", "target": "broker", "callback_targets": [ENTRY], "source": {"id": "one"}},
        {"id": "two", "target": "bound", "callback_targets": [ENTRY], "source": {"id": "two"}},
        {"id": "three", "target": "broker", "callback_targets": [], "source": {"id": "three"}},
    ]}
    candidates = _module_broker_candidates(member, module, [direct_model, required_model])
    assert len(candidates) == 2 and {item["status"] for item in candidates} == {"exact", "candidate"}


def test_broker_cycles_ambiguity_matching_and_all_local_budgets():
    module = {"functions": [
        {"id": "f", "name": "wrapper", "declaration": False},
        {"id": "g", "name": "ambiguous", "declaration": False},
        {"id": "g2", "name": "ambiguous", "declaration": False},
    ], "calls": [
        {"id": "start", "function": "main", "target": "wrapper"},
        {"id": "cycle", "function": "f", "target": "wrapper"},
        {"id": "ambiguous-start", "function": "main", "target": "ambiguous"},
    ]}
    assert _broker_paths(module, module["calls"][0], {}, 3)[1] is True
    assert _broker_paths(module, module["calls"][2], {}, 3) == ([], False)
    left = candidate("source"); right = candidate("ir")
    right["physical_tu_id"] = "other"
    assert not _matches(left, right)

    req = request()
    source = {
        "nodes": [{"id": "call", "canonical_type": "int", "source": {"file": "a.c"}, "attributes": []},
                  {"id": "worker", "canonical_type": "void *(void *)", "attributes": []}],
        "relations": [
            {"id": "create", "kind": "pthread_create", "from": "call", "to": None,
             "source": {"file": "a.c"}, "status": "candidate", "reason": None},
            {"id": "callback", "kind": "callback", "from": "call", "to": "worker",
             "source": {"file": "a.c"}, "status": "candidate", "reason": None},
        ],
    }
    binding = {"scope_id": "scope",
        "entity_bindings": [{"source_id": "worker", "resolution": "exact", "targets": [ENTRY, {"artifact_key": B, "function_id": "other"}]}],
        "expression_bindings": [{"source_id": "call", "resolution": "exact", "targets": [{"id": "a"}, {"id": "b"}]}]}
    evidence = {"by_member": {"tu": {"SourceSemanticFacts": source}}, "SourceIRBinding": {"scope": binding}}
    limited = deepcopy(req); limited["budgets"].update({"binding_candidates": 1, "callback_candidates": 1})
    facts = build_local_facts(limited, limited["members"][0], evidence)
    assert facts["status"] == "partial"
    assert any(item["code"] == "binding-candidates-budget-exhausted" for item in facts["frontier"])
    callback_limited = deepcopy(req); callback_limited["budgets"]["callback_candidates"] = 1
    callback_facts = build_local_facts(callback_limited, callback_limited["members"][0], evidence)
    assert any(item["code"] == "callback-candidates-budget-exhausted" for item in callback_facts["frontier"])

    two = deepcopy(source); two["relations"] += [
        {"id": "create2", "kind": "pthread_create", "from": "call2", "to": None,
         "source": {"file": "a.c", "line": 2}, "status": "candidate", "reason": None}]
    two["nodes"].append({"id": "call2", "canonical_type": "int", "source": {"file": "a.c", "line": 2}, "attributes": []})
    many = {"by_member": {"tu": {"SourceSemanticFacts": two, "ThreadLocalFacts": {"calls": calls_for_budget()}}}}
    limited = deepcopy(req); limited["budgets"].update({"source_facts": 1, "ir_facts": 1})
    facts = build_local_facts(limited, limited["members"][0], many)
    assert facts["counts"]["budget:source-facts-budget-exhausted:limit"] == 1
    assert facts["counts"]["budget:ir-facts-budget-exhausted:limit"] == 1


def calls_for_budget():
    return [{"symbol": "pthread_create", "source": {"artifact_key": A, "function_id": "main", "id": name},
             "direct": True, "status": "candidate", "callback_targets": [ENTRY],
             "arguments": [None], "reason": None} for name in ("one", "two")]


def test_duplicate_conflicts_failed_unsupported_merged_and_context_budget():
    req = request()
    first = candidate("source", site="same")
    second = candidate("source", site="same", entry={"artifact_key": B, "function_id": "other"})
    second["id"] = C
    conflict = build_site_index(req, [local([first, second])])
    assert conflict["sites"][0]["reason"] == "duplicate-observation-callback-conflict"
    assert conflict["sites"][0]["evidence_status"] == "source-candidate"
    failed = build_site_index(req, [local([candidate("source", status="failed")],
                                          [candidate("ir", status="exact")])])
    assert failed["sites"][0]["evidence_status"] == "failed"
    unsupported = build_site_index(req, [local([candidate("source", status="unsupported")],
                                               [candidate("ir", status="exact")])])
    assert unsupported["sites"][0]["evidence_status"] == "unsupported"
    merged = build_site_index(req, [local([candidate("source", metadata={"cardinality": "merged"})],
                                          [candidate("ir", metadata={"cardinality": "merged"})])])
    assert merged["sites"][0]["cardinality"] == "merged"

    budgets = deepcopy(expected_thread_entry_protocol()["budgets"]); budgets["contexts"] = 1
    limited = request(budgets=budgets)
    other = {"artifact_key": B, "function_id": "other"}
    sites = build_site_index(limited, [local(
        [candidate("source", site="one"), candidate("source", site="two", entry=other)],
        [candidate("ir", site="one"), candidate("ir", site="two", entry=other)])])
    overlay = build_root_overlay(limited, sites, base_plan={"scope_id": "scope", "demands": []})
    assert len(overlay["contexts"]) == 1 and any(x["code"] == "contexts-budget-exhausted" for x in overlay["frontier"])
    assert overlay["base_plan"]["kind"] == "RootDrivenAnalysisPlan"
