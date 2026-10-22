from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import identity
from memory_order_analyzer.cpp_thread_analysis import (
    adapt_p3_join_proofs, build_lifecycle_graph, build_lifecycle_report, build_local_facts,
    failed_lifecycle_report, module_wrapper_calls, trace_handle_provenance,
)
from memory_order_analyzer.cpp_thread_contracts import (
    cpp_thread_document, dependency, expected_cpp_thread_protocol,
)
from memory_order_analyzer.cpp_thread_profiles import build_library_profile
from memory_order_analyzer.model_cpp_thread_lifecycle import model_cpp_thread_lifecycle
from memory_order_analyzer.source_contracts import counts, source_document


def profile():
    compilation = {"language": "c++", "standard": "c++20", "target": "x86_64-pc-linux-gnu"}
    wrappers = [
        {"role": role, "symbol": symbol, "calling_convention": "ccc",
         "parameter_roles": ["object"], "layout": "v1"}
        for role, symbol in (
            ("construct-attempt", "construct"), ("entry-broker", "entry"),
            ("join-attempt", "join"), ("detach-attempt", "detach"),
            ("handle-transfer", "move"),
        )
    ]
    return build_library_profile(compilation, {
        "macros": {"__GLIBCXX__": "20230818"}, "data_layout": "e-p:64:64",
        "pointer_width": 64, "toolchain_lineage": "test", "headers": [],
        "wrappers": wrappers, "provenance": ["unit-test"],
    })


def source(*relations, status="complete"):
    callback = {
        "id": "fn", "kind": "function", "name": "worker", "qualified_name": "worker",
        "usr": "usr:worker", "mangled_name": "_Z6workerv", "canonical_decl": "fn",
        "definition": False, "definition_kind": "declaration", "linkage": "external",
        "language_linkage": "c++", "storage": "none", "visibility": "default",
        "tls": False, "canonical_type": "void ()", "abi": {"complete": True},
        "source": {"expansion": {"file": "a.cpp", "line": 1, "column": 1}},
        "macro_stack": [], "attributes": [],
    }
    obj = {**callback, "id": "obj", "kind": "variable", "name": "thread",
           "qualified_name": "thread", "usr": "usr:thread", "mangled_name": None,
           "canonical_decl": "obj", "definition": True, "canonical_type": "std::thread"}
    return {
        "physical_tu_id": "tu", "profile_id": "a" * 64, "status": status,
        "nodes": [callback, obj], "relations": list(relations),
    }


def relation(number, kind, from_, to=None, *, status="candidate"):
    return {"id": f"r{number}", "kind": kind, "from": from_, "to": to,
            "source": {"expansion": {"file": "a.cpp", "line": number, "column": 1}},
            "status": status, "reason": None}


def wrapper_calls(value, roles=("construct-attempt", "join-attempt")):
    by_role = {item["role"]: item for item in value["wrapper_signatures"]}
    result = []
    for number, role in enumerate(roles, 2):
        signature = by_role[role]
        result.append({
            "id": f"ir-{role}", "symbol": signature["symbol"], "calling_convention": "ccc",
            "signature_digest": signature["digest"], "contains_pthread": True,
            "evidence": [f"ir:{role}"],
            "source": {"inline_chain": [{"file": "a.cpp", "line": number, "column": 1}]},
            "result_ref": "handle" if role == "construct-attempt" else None,
        })
    return result


def member():
    return {"physical_tu_id": "tu", "profile_id": "a" * 64,
            "language": "c++", "standard": "c++20"}


def request(value):
    return cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id="scope", roots=["main"],
        members=[{**member(), "source_facts": None, "ir_facts": None}],
        dependencies=[], library_profiles=[dependency("CppThreadLibraryProfile", value["profile_id"], value)],
        budgets=expected_cpp_thread_protocol()["budgets"],
        semantic_digest=None)


def exact_index_binding():
    index = {"entities": [{"id": "entity", "resolution": "resolved",
                            "declarations": ["fn"], "definitions": ["definition"]}]}
    binding = {"entity_bindings": [{"source_id": "fn", "resolution": "exact",
                                     "targets": [{"id": "ir-worker"}]}]}
    return index, binding


def test_ast_ir_local_facts_and_complete_join_graph():
    value = profile()
    facts = source(
        relation(2, "cpp-thread-object", "init", "obj"),
        relation(2, "cpp-thread-construct", "construct-node:2:1"),
        relation(2, "cpp-thread-callback", "construct-node:2:1", "fn"),
        relation(3, "cpp-thread-join", "join-node:3:1", "obj"),
        relation(4, "cpp-thread-destruct", "obj"),
    )
    index, binding = exact_index_binding()
    local = build_local_facts("scope", member(), facts, value, entity_index=index,
                              source_binding=binding, wrapper_calls=wrapper_calls(value))
    assert local["status"] == "complete"
    assert [item["operation"] for item in local["operations"]] == sorted(
        ["construct", "join", "destruct"], key=lambda kind: next(
            item["id"] for item in local["operations"] if item["operation"] == kind))
    join_id = next(item["id"] for item in local["operations"] if item["operation"] == "join")
    graph = build_lifecycle_graph(request(value), [local], [value],
                                  p3_join_proofs={join_id: ["p3:worker-exit", "p3:successor"]})
    assert graph["status"] == "complete"
    assert {item["relation"] for item in graph["relations"]} >= {
        "thread-start", "join-complete", "thread-exit", "not-parallel",
    }
    assert graph["objects"][0]["state"] == "joined"
    report = build_lifecycle_report(request(value), graph, [value], hits=1, misses=2)
    assert report["exit_code"] == 0 and report["safety"] == "not_evaluated"


def test_ast_only_is_partial_and_never_creates_thread_instance():
    value = profile()
    facts = source(relation(2, "cpp-thread-object", "init", "obj"),
                   relation(2, "cpp-thread-construct", "construct-node:2:1"),
                   relation(2, "cpp-thread-callback", "construct-node:2:1", "fn"))
    local = build_local_facts("scope", member(), facts, value)
    assert local["status"] == "partial"
    assert local["operations"][0]["outcome"] == "unknown"
    graph = build_lifecycle_graph(request(value), [local], [value])
    assert graph["status"] == "partial" and graph["instances"] == []
    assert graph["relations"] == []


def test_c_is_independent_and_missing_cpp_source_is_partial():
    c_member = {"physical_tu_id": "c-tu", "profile_id": "b" * 64,
                "language": "c", "standard": "c17"}
    c_local = build_local_facts("scope", c_member, {"status": "complete"})
    assert c_local["status"] == "complete" and c_local["library_profile_id"] is None
    missing = build_local_facts("scope", member(), None, profile())
    assert missing["status"] == "partial" and missing["frontier"][0]["code"] == "source-evidence-missing"


def test_move_detach_unknown_join_and_joinable_destructor_are_conservative():
    value = profile()
    index, binding = exact_index_binding()
    facts = source(
        relation(2, "cpp-thread-object", "init", "obj"),
        relation(2, "cpp-thread-construct", "construct-node:2:1"),
        relation(2, "cpp-thread-callback", "construct-node:2:1", "fn"),
        relation(3, "cpp-thread-joinable", "query:3:1", "obj"),
        relation(4, "cpp-thread-detach", "detach-node:4:1", "obj"),
        relation(5, "cpp-thread-destruct", "obj"),
    )
    local = build_local_facts("scope", member(), facts, value, entity_index=index,
                              source_binding=binding,
                              wrapper_calls=wrapper_calls(value, ("construct-attempt", "detach-attempt")))
    graph = build_lifecycle_graph(request(value), [local], [value])
    assert any(item["relation"] == "detach" for item in graph["relations"])
    assert not any(item["relation"] == "not-parallel" for item in graph["relations"])
    assert graph["objects"][0]["state"] == "detached"

    join_local = deepcopy(local)
    detach = next(item for item in join_local["operations"] if item["operation"] == "detach")
    detach["operation"] = "join"; detach["id"] = identity(detach)
    join_local["semantic_digest"] = identity({k: v for k, v in join_local.items() if k != "semantic_digest"})
    partial = build_lifecycle_graph(request(value), [join_local], [value])
    assert any(item["code"] == "join-proof-incomplete" for item in partial["gaps"])


def test_module_calls_require_exact_target_layout_and_failed_report_is_bilingual():
    value = profile(); signature = value["wrapper_signatures"][0]
    module = {"target": value["target"], "layout": value["data_layout"], "calls": [{
        "id": "call", "kind": "direct", "target": signature["symbol"], "calling_convention": 0,
        "source": {"inline_chain": []}, "arguments": [], "result_ref": None,
        "normal": None, "unwind": None,
    }]}
    calls = module_wrapper_calls({"a": module}, value)
    assert calls[0]["signature_digest"] == signature["digest"]
    wrong_convention = deepcopy(module); wrong_convention["calls"][0]["calling_convention"] = 8
    raw = module_wrapper_calls({"a": wrong_convention}, value)
    assert raw[0]["calling_convention"] == "llvm:8"
    from memory_order_analyzer.cpp_thread_profiles import normalize_wrapper_calls
    normalized, diagnostics = normalize_wrapper_calls(raw, value)
    assert normalized == [] and diagnostics[0]["code"] == "abi-wrapper-mismatch"
    bad = deepcopy(module); bad["target"] = "other"
    assert module_wrapper_calls({"a": bad}, value) == []
    failed = failed_lifecycle_report("bad", "错误", "error")
    assert failed["exit_code"] == 1 and failed["diagnostics"][0]["detail_en"]


def test_bounded_handle_provenance_covers_phi_select_cast_unknown_and_budget():
    values = [
        {"id": "slot", "details": {"opcode": "alloca"}, "operands": []},
        {"id": "cast", "details": {"opcode": "bitcast"}, "operands": ["slot"]},
        {"id": "choice", "details": {"opcode": "select"}, "operands": ["cast", "other"]},
        {"id": "bad", "details": {"opcode": "call"}, "operands": ["slot"]},
    ]
    exact = trace_handle_provenance(["cast"], values)
    assert exact["status"] == "exact" and exact["roots"] == ["slot"]
    candidate = trace_handle_provenance(["choice"], values)
    assert candidate["status"] == "candidate" and candidate["roots"] == ["other", "slot"]
    unresolved = trace_handle_provenance(["bad"], values)
    assert unresolved["status"] == "unresolved" and unresolved["opposed"]
    limited = trace_handle_provenance(["choice"], values, limit=1)
    assert "provenance-budget-exhausted" in limited["opposed"]


def test_state_machine_handles_failed_repeated_move_and_self_move():
    value = profile()
    callable_id = "c" * 64
    callable_ = {"id": callable_id, "callable_kind": "free-function", "entity_id": "entity",
                 "receiver_id": None, "capture_ids": [], "resolution": "exact",
                 "targets": ["definition"], "source_nodes": ["fn"], "ir_nodes": ["ir-fn"]}
    def op(line, kind, object_id, *, other=None, outcome="success", repeated=False, callback=True):
        fields = {"operation": kind, "object_id": object_id, "other_object_id": other,
                  "callable_id": callable_id if callback and kind == "construct" else None,
                  "outcome": outcome, "guard": None, "wrapper_role": "construct-attempt" if kind == "construct" else None,
                  "native_handle": f"handle-{object_id}" if kind == "construct" else None,
                  "source_nodes": [f"node:{line}:1"], "ir_nodes": [f"ir:{line}"], "repeated": repeated}
        return {"id": identity(fields), **fields}
    operations = [
        op(1, "construct", "source"), op(2, "move-construct", "target", other="source", callback=False),
        op(3, "move-assign", "target", other="target", callback=False),
        op(4, "construct", "failed", outcome="throw"),
        op(5, "construct", "loop", repeated=True),
    ]
    local = cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="tu", profile_id="a" * 64,
        language="c++", standard="c++20", status="complete", library_profile_id=value["profile_id"],
        callables=[callable_], operations=sorted(operations, key=lambda item: item["id"]), dependencies=[],
        diagnostics=[], frontier=[], semantic_digest=None)
    graph = build_lifecycle_graph(request(value), [local], [value])
    states = {item["object_id"]: item["state"] for item in graph["objects"]}
    assert states["source"] == "moved-from"
    assert states["target"] == "unknown"
    assert states["failed"] == "failed"
    assert any(item["cardinality"] == "repeated" for item in graph["instances"])
    assert graph["status"] == "partial" and graph["frontier"]


def test_runner_reads_explicit_dependencies_caches_and_rejects_reused_output(tmp_path):
    value = profile()
    local = cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="tu",
        profile_id="a" * 64, language="c++", standard="c++20", status="complete",
        library_profile_id=value["profile_id"], callables=[], operations=[], dependencies=[],
        diagnostics=[], frontier=[], semantic_digest=None)
    local_ref = dependency("CppThreadLocalFacts", "tu", local)
    profile_ref = dependency("CppThreadLibraryProfile", value["profile_id"], value)
    req = cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id="scope", roots=["main"],
        members=[{**member(), "source_facts": None, "ir_facts": None}],
        dependencies=[local_ref], library_profiles=[profile_ref],
        budgets=expected_cpp_thread_protocol()["budgets"], semantic_digest=None)
    artifacts = tmp_path / "artifacts"
    (artifacts / "local-facts").mkdir(parents=True)
    (artifacts / "cpp-thread-profiles").mkdir()
    import json
    (artifacts / "local-facts/tu.json").write_text(json.dumps(local), encoding="utf-8")
    (artifacts / f"cpp-thread-profiles/{value['profile_id']}.json").write_text(
        json.dumps(value), encoding="utf-8")
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(req), encoding="utf-8")
    report = model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "out")
    assert report["status"] == "complete" and report["exit_code"] == 0
    import pytest
    from memory_order_analyzer.contracts import AnalysisError
    with pytest.raises(AnalysisError, match="fresh output"):
        model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "out")


def test_runner_builds_and_reuses_c_local_and_graph_cache(tmp_path):
    c_tu = "d" * 64
    c_facts = source_document(
        "SourceSemanticFacts", profile_id="b" * 64, physical_tu_id=c_tu,
        source_digest="c" * 64, status="complete", nodes=[], relations=[],
        counts={"nodes": counts(0), "relations": counts(0)}, diagnostics=[], frontier=[],
        semantic_digest=None)
    source_ref = dependency("SourceSemanticFacts", c_tu, c_facts)
    req = cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id="c-scope", roots=["main"],
        members=[{"physical_tu_id": c_tu, "profile_id": "b" * 64, "language": "c",
                  "standard": "c11", "source_facts": source_ref, "ir_facts": None}],
        dependencies=[source_ref], library_profiles=[], budgets=expected_cpp_thread_protocol()["budgets"],
        semantic_digest=None)
    artifacts = tmp_path / "artifacts"; (artifacts / "source-facts").mkdir(parents=True)
    import json
    (artifacts / f"source-facts/{c_tu}.json").write_text(json.dumps(c_facts), encoding="utf-8")
    request_path = tmp_path / "c-request.json"; request_path.write_text(json.dumps(req), encoding="utf-8")
    first = model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "cold")
    second = model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "warm")
    assert first["semantic_digest"] == second["semantic_digest"]
    assert first["cache"]["misses"] == 2 and second["cache"]["hits"] == 2


def test_runner_dependency_errors_timeout_output_and_dispatch_branches(tmp_path, monkeypatch):
    import memory_order_analyzer.model_cpp_thread_lifecycle as runner
    from memory_order_analyzer.contracts import AnalysisError
    with pytest.raises(AnalysisError, match="Unsupported"):
        runner._read_kind(tmp_path / "x", "Other")
    with pytest.raises(AnalysisError, match="missing"):
        runner._resolve_dependency(tmp_path, {"kind": "CppThreadLocalFacts", "id": "none",
                                              "digest": "a" * 64})
    for kind in ("ModuleFacts", "ThreadContextGraph"):
        with pytest.raises(AnalysisError):
            runner._read_kind(tmp_path / "missing.json", kind)

    value = profile(); local = cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="tu", profile_id="a" * 64,
        language="c++", standard="c++20", status="complete", library_profile_id=value["profile_id"],
        callables=[], operations=[], dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    local_ref = dependency("CppThreadLocalFacts", "tu", local)
    profile_ref = dependency("CppThreadLibraryProfile", value["profile_id"], value)
    req = cpp_thread_document(
        "CppThreadLifecycleRequest", scope_id="scope", roots=["main"],
        members=[{**member(), "source_facts": None, "ir_facts": None}], dependencies=[local_ref],
        library_profiles=[profile_ref], budgets={**expected_cpp_thread_protocol()["budgets"], "request_seconds": 1},
        semantic_digest=None)
    artifacts = tmp_path / "store"; (artifacts / "local-facts").mkdir(parents=True)
    (artifacts / "cpp-thread-profiles").mkdir()
    import json
    (artifacts / "local-facts/tu.json").write_text(json.dumps(local), encoding="utf-8")
    (artifacts / f"cpp-thread-profiles/{value['profile_id']}.json").write_text(json.dumps(value), encoding="utf-8")
    request_path = tmp_path / "request.json"; request_path.write_text(json.dumps(req), encoding="utf-8")
    ticks = iter((0, 2)); monkeypatch.setattr(runner, "monotonic", lambda: next(ticks))
    with pytest.raises(AnalysisError, match="request budget"):
        runner.model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "timeout")
    with pytest.raises(AnalysisError, match="digest changed"):
        runner._resolve_dependency(artifacts, {"kind": "CppThreadLocalFacts", "id": "tu",
                                               "digest": "f" * 64})

    monkeypatch.setattr(runner, "monotonic", lambda: 0)
    small = deepcopy(req); small["budgets"]["request_output_bytes"] = 1024
    from memory_order_analyzer.cpp_thread_contracts import semantic_digest
    small["semantic_digest"] = semantic_digest(small)
    request_path.write_text(json.dumps(small), encoding="utf-8")
    with pytest.raises(AnalysisError, match="output budget"):
        runner.model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "oversize")

    over = deepcopy(req); over["members"] = [deepcopy(req["members"][0]),
                                               {**deepcopy(req["members"][0]), "physical_tu_id": "other"}]
    over["budgets"]["translation_units"] = 1
    monkeypatch.setattr(runner, "read_cpp_thread_document", lambda *args: over)
    with pytest.raises(AnalysisError, match="translation-unit"):
        runner.model_cpp_thread_lifecycle(request_path, artifacts, tmp_path / "tu-over")


def test_analysis_helper_branches_and_ambiguous_source_candidate():
    import memory_order_analyzer.cpp_thread_analysis as a
    cyclic = [{"id": "cycle", "opcode": "phi", "operands": ["cycle"]}]
    assert a.trace_handle_provenance(["cycle"], cyclic)["status"] == "unresolved"
    assert a._entity_for_node({"entities": []}, "x") is None
    assert a._binding_for_node({"entity_bindings": []}, "x") is None
    assert a._callable_kind({"name": "", "qualified_name": "lambda at a.cpp"}) == "lambda"
    assert a._callable_kind({"name": "operator()", "qualified_name": "f::operator()"}) == "functor"
    assert a._callable_kind({"name": "run", "qualified_name": "n::owner::run"}) == "member-function"
    assert a._gap("x", "中", "en", tu=None)["physical_tu_ids"] == []
    with pytest.raises(Exception, match="require an adopted"):
        a.build_local_facts("scope", member(), source(), None)

    value = profile()
    unsupported = deepcopy(value); unsupported["status"] = "unsupported"
    from memory_order_analyzer.cpp_thread_contracts import semantic_digest
    unsupported["semantic_digest"] = semantic_digest(unsupported)
    rejected = a.build_local_facts("scope", member(), source(), unsupported)
    assert rejected["status"] == "partial"
    assert rejected["frontier"][0]["code"] == "library-profile-unsupported"
    signature = value["wrapper_signatures"][0]
    calls = a.module_wrapper_calls({"artifact": {
        "target": value["target"], "layout": value["data_layout"], "values": [],
        "calls": [{"id": "indirect", "kind": "indirect", "target": signature["symbol"]},
                  {"id": "other", "kind": "direct", "target": "lookalike"}],
    }}, value)
    assert calls == []
    facts = source(relation(2, "cpp-thread-construct", "construct:2:1"),
                   relation(2, "cpp-thread-callback", "construct:2:1", None, status="unknown"))
    local = a.build_local_facts("scope", member(), facts, value)
    assert local["operations"][0]["object_id"].startswith("source-object:")
    assert local["callables"][0]["resolution"] == "unresolved"


def test_state_machine_budget_overwrite_destructor_and_invalid_operation_paths():
    value = profile(); callable_id = "c" * 64
    callable_ = {"id": callable_id, "callable_kind": "free-function", "entity_id": "e",
                 "receiver_id": None, "capture_ids": [], "resolution": "exact",
                 "targets": ["definition"], "source_nodes": ["fn"], "ir_nodes": ["ir"]}
    def op(line, kind, obj, other=None, callback=None):
        fields = {"operation": kind, "object_id": obj, "other_object_id": other,
                  "callable_id": callable_id if callback else None, "outcome": "success",
                  "guard": None, "wrapper_role": "construct-attempt" if callback else None,
                  "native_handle": f"h-{obj}" if callback else None,
                  "source_nodes": [f"node:{line}:1"], "ir_nodes": [f"ir:{line}"], "repeated": False}
        return {"id": identity(fields), **fields}
    operations = [op(1, "construct", "left", callback=True),
                  op(2, "construct", "right", callback=True),
                  op(3, "move-assign", "right", "left"),
                  op(4, "destruct", "left")]
    local = cpp_thread_document(
        "CppThreadLocalFacts", scope_id="scope", physical_tu_id="tu", profile_id="a" * 64,
        language="c++", standard="c++20", status="complete", library_profile_id=value["profile_id"],
        callables=[callable_], operations=sorted(operations, key=lambda item: item["id"]),
        dependencies=[], diagnostics=[], frontier=[], semantic_digest=None)
    graph = build_lifecycle_graph(request(value), [local], [value])
    assert any(item["code"] == "move-assign-joinable-target" for item in graph["gaps"])

    limited_request = deepcopy(request(value)); limited_request["budgets"]["objects"] = 1
    limited_request["budgets"]["instances"] = 1; limited_request["budgets"]["relations"] = 1
    from memory_order_analyzer.cpp_thread_contracts import semantic_digest
    limited_request["semantic_digest"] = semantic_digest(limited_request)
    limited = build_lifecycle_graph(limited_request, [local], [value])
    codes = {item["code"] for item in limited["frontier"]}
    assert {"objects-budget-exhausted", "instances-budget-exhausted", "relations-budget-exhausted"} <= codes

    invalid = deepcopy(local); invalid["operations"] = [op(1, "magic", "unknown")]
    unknown = build_lifecycle_graph(request(value), [invalid], [value])
    assert unknown["objects"][0]["state"] == "unknown"


def test_cli_exposes_a3_and_returns_machine_readable_failure(monkeypatch):
    import io
    import memory_order_analyzer.cli as cli
    assert "model-cpp-thread-lifecycle" in cli.parser()._subparsers._group_actions[0].choices
    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(["model-cpp-thread-lifecycle"], stdout=stdout, stderr=stderr) == 1
    assert '"kind":"CppThreadLifecycleReport"' in stdout.getvalue()

    monkeypatch.setattr(cli, "model_cpp_thread_lifecycle", lambda *args: {
        "exit_code": 2, "kind": "CppThreadLifecycleReport", "status": "partial"})
    code = cli.main(["model-cpp-thread-lifecycle", "--request", "r", "--artifact-store", "a",
                     "--output", "o"], stdout=io.StringIO(), stderr=io.StringIO())
    assert code == 2


def test_p3_adapter_requires_closed_exit_join_and_parent_successor_chain():
    operation = {"id": "a3-join", "operation": "join",
                 "source_nodes": ["source-join"], "ir_nodes": ["ir-join"]}
    local = [{"operations": [operation]}]
    graph = {
        "lifecycles": [
            {"id": "exit", "kind": "thread-exit", "status": "may", "source": None, "proof": []},
            {"id": "complete", "kind": "join-complete", "status": "may",
             "source": {"operation_id": "a3-join"}, "proof": [{"analysis_id": "join-proof"}]},
        ],
        "order": [{"id": "edge", "kind": "join", "before": "exit", "after": "complete",
                   "relation": "may-before", "proof": [{"analysis_id": "order-proof"}]}],
        "mhp": [{"id": "not-parallel", "relation": "not_parallel", "left_endpoint": "exit",
                 "right_endpoint": "parent-successor"}],
    }
    proof = adapt_p3_join_proofs(graph, local)
    assert set(proof["a3-join"]) >= {"exit", "complete", "edge", "not-parallel", "join-proof"}
    missing_successor = deepcopy(graph); missing_successor["mhp"] = []
    assert adapt_p3_join_proofs(missing_successor, local) == {}
    ambiguous = deepcopy(graph)
    ambiguous["lifecycles"].append({**graph["lifecycles"][1], "id": "complete-2"})
    ambiguous["order"].append({**graph["order"][0], "id": "edge-2", "after": "complete-2"})
    assert adapt_p3_join_proofs(ambiguous, local) == {}


def test_p3_adapter_drives_join_and_is_recorded_as_dependency():
    value = profile()
    facts = source(
        relation(2, "cpp-thread-object", "init", "obj"),
        relation(2, "cpp-thread-construct", "construct-node:2:1"),
        relation(2, "cpp-thread-callback", "construct-node:2:1", "fn"),
        relation(3, "cpp-thread-join", "join-node:3:1", "obj"),
    )
    index, binding = exact_index_binding()
    local = build_local_facts("scope", member(), facts, value, entity_index=index,
                              source_binding=binding, wrapper_calls=wrapper_calls(value))
    join = next(item for item in local["operations"] if item["operation"] == "join")
    p3 = {
        "scope_id": "p3-scope", "lifecycles": [
            {"id": "exit", "kind": "thread-exit", "status": "may", "source": None, "proof": []},
            {"id": "complete", "kind": "join-complete", "status": "may",
             "source": {"a3_operation_id": join["id"]}, "proof": []},
        ],
        "order": [{"id": "join-edge", "kind": "join", "before": "exit", "after": "complete",
                   "relation": "may-before", "proof": []}],
        "mhp": [{"id": "closed", "relation": "not_parallel", "left_endpoint": "exit",
                 "right_endpoint": "successor"}],
    }
    graph = build_lifecycle_graph(request(value), [local], [value], thread_graph=p3)
    assert {item["relation"] for item in graph["relations"]} >= {"join-complete", "not-parallel"}
    assert any(item["kind"] == "ThreadContextGraph" for item in graph["dependencies"])
