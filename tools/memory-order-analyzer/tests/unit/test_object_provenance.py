import json
import io
from pathlib import Path
from copy import deepcopy

import pytest

from memory_order_analyzer.contracts import AnalysisError, identity
from memory_order_analyzer.object_provenance import (
    bottom, build_graph, build_report, byte_relation, candidate, exact_adapter,
    compare_truth, compose_evidence, failed_report, join, may, must, object_instance, propagate_load, specialize,
    storage_instance, unknown,
)
from memory_order_analyzer.analyze_object_provenance import (
    _normalize_worker_objects, _resolve_dependency, _run_request,
    analyze_llvm_provenance, analyze_object_provenance, analyze_source_paths,
    check_worker,
)
import memory_order_analyzer.provenance_contracts as provenance_contracts
import memory_order_analyzer.provenance_cache as provenance_cache
from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, file_hash
from memory_order_analyzer.effect_contracts import effect_document, expected_analysis_protocol
from memory_order_analyzer.provenance_cache import ProvenanceCache, cache_key
from memory_order_analyzer.provenance_contracts import (
    diagnostic, expected_provenance_protocol, provenance_document,
    semantic_digest, validate_provenance_document,
)
from memory_order_analyzer.source_contracts import counts, source_document


def budgets(**overrides):
    result = dict(expected_provenance_protocol()["budgets"])
    result.update(overrides)
    return result


def member(tu="tu", language="c", standard="c17", source="source.json", llvm="llvm.json"):
    return {"physical_tu_id": tu, "profile_id": "a" * 64, "language": language,
            "standard": standard, "source_request": source, "llvm_request": llvm}


def request(members=None, **limits):
    return provenance_document(
        "BoundedObjectProvenanceRequest", scope_id="scope", roots=["main"],
        members=members or [member()], dependencies=[], budgets=budgets(**limits),
        semantic_digest=None)


def segment(field="field", offset=0, size=32, union=None):
    return {"kind": "field", "field_id": field, "record_type": "record",
            "access": "dot", "field_index": 0, "offset_bits": offset,
            "size_bits": size, "align_bits": 32, "union_group": union}


def source_facts(tu="tu", status="complete", language="c", standard="c17"):
    frontier = [] if status == "complete" else [diagnostic("source-gap", "源码证据缺失", "Source evidence is missing")]
    return provenance_document(
        "SourceObjectPathFacts", profile_id="a" * 64, physical_tu_id=tu,
        source_digest="b" * 64, language=language, standard=standard, mode="ast-only",
        status=status, paths=[{
            "id": "path", "expression_id": "expr", "role": "read",
            "base": {"kind": "global", "declaration_id": "g", "name": "g"},
            "segments": [segment()], "status": "exact", "reason": None,
            "source": {"spelling": {"file": "a.c", "line": 1, "column": 1}},
            "evidence": ["ast-record-layout", "member-expr-base"],
        }], counts={"paths": 1}, dependencies=[], diagnostics=[], frontier=frontier,
        semantic_digest=None)


def llvm_facts(tu="tu", status="complete", domains=None):
    value = object_instance(storage_instance("global", "g", artifact_key="c" * 64), [segment()], offset=0, size=4)
    domains = domains or [("v", must(value, proof=("underlying-object",)))]
    frontier = [] if status == "complete" else [diagnostic("ir-gap", "IR 证据缺失", "IR evidence is missing")]
    values = [{"id": key, "function_id": None, "opcode": "global", "domain": domain,
               "offset": 0, "address_space": 0, "evidence": ["value-tracking"]}
              for key, domain in domains]
    return provenance_document(
        "LLVMObjectProvenanceFacts", artifact_key="c" * 64, profile_id="a" * 64,
        physical_tu_id=tu, bitcode_digest="d" * 64, target="x86_64-linux-gnu",
        data_layout="e-p:64:64", mode="ir-only", status=status, values=values,
        queries=[], call_edges=[], returns=[], counts={"values": len(values)},
        dependencies=[], diagnostics=[], frontier=frontier, semantic_digest=None)


def adopted_evidence(caller_facts, callee_facts, *, callee="callee", edge="call", scope="scope"):
    """Minimal already-validated A1/P2 evidence for composition-unit tests."""
    index = {"kind": "ProgramEntityIndex", "scope_id": scope, "entities": [{
        "kind": "function", "resolution": "resolved", "key": {"symbol": callee},
        "definitions": [f"definition:{callee}"],
    }]}
    summary = {"kind": "EffectSummary", "scope_id": scope, "adoptions": [{
        "call": {"artifact_key": caller_facts["artifact_key"], "function_id": "caller", "id": edge},
        "target": {"artifact_key": callee_facts["artifact_key"], "function_id": None, "id": callee},
        "kind": "unique-definition", "reason": "exact_unique_definition", "assumptions": [],
    }]}
    binding = {"kind": "SourceIRBinding", "scope_id": scope, "entity_bindings": [{
        "source_id": "g", "resolution": "exact", "cardinality": "one-to-one",
        "targets": [{"artifact_key": caller_facts["artifact_key"], "id": "actual"}],
        "opposed": [],
    }]}
    return {"scope_id": scope, "entity_indexes": [index], "source_bindings": [binding],
            "effect_summaries": [summary]}


def test_protocol_schema_version_digest_and_bilingual_diagnostics_are_strict(tmp_path):
    protocol = expected_provenance_protocol()
    assert protocol["kinds"]["BoundedObjectProvenanceGraph"] == 1
    assert protocol["budgets"]["candidate_targets"] == 64
    item = diagnostic("x", "中文" * 100, "English" * 100, suggestion="建议",
                      suggestion_en="Suggestion", limit=48)
    assert len(item["detail"].encode()) <= 48 and len(item["detail_en"].encode()) <= 48
    value = request()
    assert validate_provenance_document(value, value["kind"]) == value
    broken = deepcopy(value); broken["schema_version"] = 2
    with pytest.raises(AnalysisError, match="schema_version"):
        validate_provenance_document(broken, broken["kind"])
    broken = deepcopy(value); broken["roots"] = ["main", "main"]
    broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="unique"):
        validate_provenance_document(broken, broken["kind"])
    bad_protocol = tmp_path / "protocol.json"
    bad_protocol.write_text(json.dumps({**protocol, "llvm_version": "22"}), encoding="utf-8")
    with pytest.raises(AnalysisError, match="does not match"):
        expected_provenance_protocol(bad_protocol)


def test_request_language_evidence_and_translation_unit_budget_boundaries():
    with pytest.raises(AnalysisError, match="AST or LLVM"):
        request([member(source=None, llvm=None)])
    with pytest.raises(AnalysisError, match="disagree"):
        request([member(language="c", standard="c++17")])
    with pytest.raises(AnalysisError, match="translation unit budget"):
        request([member("a"), member("b")], translation_units=1)
    with pytest.raises(AnalysisError, match="unique"):
        request([member("a"), member("a")])


def test_runtime_identity_separates_storage_instances_and_keeps_field_as_path():
    first_storage = storage_instance("stack", "local", function_id="f", invocation_id="i1")
    second_storage = storage_instance("stack", "local", function_id="f", invocation_id="i2")
    first = object_instance(first_storage, [segment("mutex")], offset=0, size=40)
    second = object_instance(second_storage, [segment("mutex")], offset=0, size=40)
    assert first["id"] != second["id"]
    assert first["storage"]["source_id"] == second["storage"]["source_id"] == "local"
    assert first["path"][0]["field_id"] == "mutex"
    changed_lifetime = storage_instance("stack", "local", function_id="f", invocation_id="i1", lifetime="expired")
    assert changed_lifetime["id"] != first_storage["id"]


def test_finite_lattice_join_guards_budget_and_opposed_evidence():
    one = object_instance(storage_instance("global", "a"), offset=0, size=4)
    two = object_instance(storage_instance("global", "b"), offset=0, size=4)
    assert join(bottom(), must(one)) == must(one)
    assert may([])["state"] == "unknown"
    combined = join(must(one, guards=("left",)), must(two, guards=("right",)))
    assert combined["state"] == "may" and len(combined["candidates"]) == 2
    assert join(must(one), must(two), candidate_limit=1)["reason"] == "candidate-budget-exhausted"
    assert join(must(one, guards=("a", "b")), must(two), guard_limit=1)["reason"] == "guard-budget-exhausted"
    opposed = may([one], opposed=("may-alias",))
    assert opposed["state"] == "may"
    assert join(unknown("ptr-int"), must(one))["state"] == "unknown"
    assert may([one])["state"] == "must"


def test_byte_ranges_union_and_unknown_layout_are_conservative():
    storage = storage_instance("global", "record")
    left = object_instance(storage, [segment("a")], offset=0, size=4)
    same = object_instance(storage, [segment("a")], offset=0, size=4)
    right = object_instance(storage, [segment("b", offset=32)], offset=4, size=4)
    overlap = object_instance(storage, [segment("c")], offset=2, size=4)
    unknown_range = object_instance(storage, [segment("d")], offset=None, size=None)
    union_left = object_instance(storage, [segment("u.a", union="u")], offset=0, size=4)
    union_right = object_instance(storage, [segment("u.b", union="u")], offset=0, size=8)
    assert byte_relation(left, same) == "same"
    assert byte_relation(left, right) == "disjoint"
    assert byte_relation(left, overlap) == "overlap"
    assert byte_relation(left, unknown_range) == "unknown"
    assert byte_relation(union_left, union_right) == "overlap"
    assert byte_relation(left, object_instance(storage_instance("global", "other"), offset=0, size=4)) == "disjoint"


@pytest.mark.parametrize("kwargs,reason", [
    ({"stores": []}, "non-unique-reaching-store"),
    ({"stores": None}, "non-unique-reaching-store"),
    ({"exact_range": False}, "non-exact-range"),
    ({"no_clobber": False}, "memory-clobber"),
    ({"captured": True}, "storage-escaped"),
    ({"lifetime": "expired"}, "lifetime-not-live"),
    ({"atomic": True}, "atomic-or-volatile-pointer-load"),
    ({"volatile": True}, "atomic-or-volatile-pointer-load"),
    ({"load_hops": 3, "hop_limit": 2}, "load-hop-budget-exhausted"),
])
def test_pointer_field_strong_update_requires_all_proofs(kwargs, reason):
    value = object_instance(storage_instance("stack", "slot"), offset=0, size=8)
    args = {"stores": [value], **kwargs}
    if args["stores"] is None:
        args["stores"] = [value, value]
    result = propagate_load(**args)
    assert result["state"] == "unknown" and reason in result["reason"]
    exact = propagate_load([value])
    assert exact["state"] == "must" and "memoryssa-no-clobber" in exact["candidates"][0]["proof"]


def test_direct_call_specialization_return_lifetime_and_exact_only_adapters():
    formal = object_instance(storage_instance("parameter", "arg", function_id="callee"), offset=0, size=8)
    actual = object_instance(storage_instance("global", "actual"), offset=0, size=8)
    bound = specialize(must(formal), {"arg": actual})
    assert bound["candidates"][0]["object"]["id"] == actual["id"]
    assert specialize(must(formal), {}, expired_returns=("arg",))["reason"] == "expired-local-return"
    assert specialize(must(formal), {}) == must(formal)
    opposed_formal = must(formal)
    opposed_formal["state"] = "may"
    opposed_formal["candidates"][0]["opposed"] = ["captured"]
    assert specialize(opposed_formal, {"arg": actual})["state"] == "may"
    exact = exact_adapter("mutex", bound, consumer="A4")
    assert exact["status"] == "exact" and exact["object_id"] == actual["id"]
    ambiguous = exact_adapter("mutex", unknown("virtual-call"), consumer="A4")
    assert ambiguous["reason"] == "mutex-provenance-ambiguous"
    p4 = exact_adapter("payload", may([formal, actual]), consumer="P4")
    assert p4["reason"] == "object-provenance-ambiguous"


def test_graph_modes_candidate_relevant_completeness_and_report_semantics():
    req = request([member("ast", llvm=None), member("both"), member("ir", source=None),
                   member("none", source="missing", llvm="missing")])
    sf = [source_facts("both"), source_facts("ast")]
    lf = [llvm_facts("both"), llvm_facts("ir")]
    obj = lf[0]["values"][0]["domain"]["candidates"][0]["object"]
    adapter = exact_adapter("m", must(obj), consumer="A4")
    graph = build_graph(req, sf, lf, domains=[("v", must(obj))], adapters=[adapter])
    assert [item["mode"] for item in graph["members"]] == ["ast-only", "ast+ir", "ir-only", "failed"]
    assert graph["status"] == "partial" and graph["counts"]["completed"] == 1
    report = build_report(req, graph, hits=2, misses=1)
    assert report["exit_code"] == 2 and report["safety"] == "not_established"
    assert report["findings"] is None and report["cache"] == {"hits": 2, "misses": 1}
    assert semantic_digest(report) == report["semantic_digest"]
    failed = failed_report("worker", "失败", "failed")
    assert failed["exit_code"] == 1 and failed["frontier"][0]["detail_en"] == "failed"


def test_source_and_llvm_contracts_reject_runtime_claims_invalid_domains_and_frontier():
    source = source_facts()
    source["paths"][0]["base"]["object"] = "runtime"
    source["semantic_digest"] = semantic_digest(source)
    with pytest.raises(AnalysisError, match="AST-only"):
        validate_provenance_document(source, source["kind"])
    value = llvm_facts()
    value["values"][0]["domain"] = {"state": "must", "candidates": [], "reason": None}
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="must requires"):
        validate_provenance_document(value, value["kind"])
    value = llvm_facts()
    value["frontier"] = [diagnostic("x", "x", "x")]
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="Complete"):
        validate_provenance_document(value, value["kind"])


def test_cache_isolated_revalidates_dependencies_and_rejects_transient_entries(tmp_path):
    cache = ProvenanceCache(tmp_path)
    value = source_facts()
    key = cache_key("source", {"tu": "tu"})
    path = cache.publish("source", key, value)
    assert cache.load("source", key, value["kind"]) == value
    assert cache.load("missing", key, value["kind"]) is None
    assert cache.publish("source", key, value) == path
    with pytest.raises(AnalysisError, match="stale"):
        cache.load("source", key, value["kind"], dependencies=[{"kind": "x"}])
    with pytest.raises(AnalysisError, match="documents"):
        cache.publish("source", "bad", [])
    with pytest.raises(AnalysisError, match="Transient"):
        cache.publish("source", "bad", value, stability="timeout")
    with pytest.raises(AnalysisError, match="escapes"):
        cache._path("../../outside", "bad")
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A5 cache"):
        cache.load("source", key, value["kind"])


def test_validation_denominators_and_report_exit_references_are_enforced():
    cases = [{"id": standard, "standard": standard} for standard in ("c++17", "c++20", "c11", "c17")]
    suite = provenance_document("ObjectProvenanceValidationSuite", suite_version="1", cases=cases,
                                semantic_digest=None)
    assert suite["kind"] == "ObjectProvenanceValidationSuite"
    broken = request(); broken["kind"] = "NoSuchKind"
    with pytest.raises(AnalysisError, match="Unknown"):
        validate_provenance_document(broken, broken["kind"])
    report = failed_report("x", "x")
    report["exit_code"] = 0; report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="exit code"):
        validate_provenance_document(report, report["kind"])


def test_direct_cross_tu_composition_and_source_ir_alignment_are_evidence_bounded():
    actual_object = object_instance(storage_instance("global", "actual"), offset=0, size=8)
    formal_object = object_instance(storage_instance("parameter", "formal", function_id="callee"), offset=0, size=8)
    caller = llvm_facts("caller", domains=[("actual", must(actual_object))])
    caller["values"][0].update(function_id="caller", ir_name="%actual", argument_index=None)
    caller["call_edges"] = [{"id": "call", "caller": "caller", "callee": "callee",
                             "arguments": ["%actual"], "status": "direct"}]
    caller["semantic_digest"] = semantic_digest(caller)
    callee = llvm_facts("callee", domains=[("formal", must(formal_object))])
    callee["values"][0].update(function_id="callee", opcode="argument", ir_name="%formal", argument_index=0)
    callee["semantic_digest"] = semantic_digest(callee)
    source = source_facts("caller")
    source["paths"][0]["base"]["name"] = "actual"
    source["paths"][0]["segments"][0]["offset_bits"] = 0
    source["semantic_digest"] = semantic_digest(source)
    _, unadopted, _ = compose_evidence([source], [caller, callee], budgets())
    assert next(item for item in unadopted
                if item["kind"] == "direct-actual-to-formal")["status"] == "candidate"
    evidence = adopted_evidence(caller, callee)
    domains, relations, frontier = compose_evidence(
        [source], [caller, callee], budgets(), **evidence)
    assert len(domains) >= 3 and not frontier
    kinds = {item["kind"]: item for item in relations}
    assert kinds["direct-actual-to-formal"]["status"] == "exact"
    assert kinds["source-ir-object-alignment"]["status"] == "exact"
    limited = budgets(call_contexts=1, recursive_iterations=1)
    caller["call_edges"] *= 2
    caller["call_edges"][1] = {**caller["call_edges"][1], "id": "call-2", "callee": "caller"}
    assert compose_evidence([], [caller, callee], limited, **evidence)[2]


def test_a1_p2_dependency_resolution_rejects_missing_stale_and_unsupported(tmp_path, monkeypatch):
    import memory_order_analyzer.analyze_object_provenance as analyzer

    scope = "e" * 64
    entity = {"id": "function", "object_id": None, "kind": "function",
              "resolution": "resolved", "key": {"symbol": "callee"},
              "declarations": ["decl"], "definitions": ["def"], "candidates": [],
              "evidence": ["usr"], "reason": None}
    index = source_document("ProgramEntityIndex", scope_id=scope, status="complete",
                            dependencies=[], entities=[entity], counts={"groups": counts(1)},
                            diagnostics=[], frontier=[], semantic_digest=None)
    summary = effect_document(
        "EffectSummary", scope_id=scope, context_id="context", root_invocation_id="root",
        invocations=[{"id": "root", "context_id": "context",
                      "function": {"artifact_key": "a" * 64, "function_id": None, "id": "caller"},
                      "parent_id": None, "callsite": None, "cardinality": "single", "reason": None}],
        root={"artifact_key": "a" * 64, "function_id": "caller", "arguments": []},
        origins=[{"artifact_key": "a" * 64, "module_hash": "b" * 64,
                  "facts_hash": "c" * 64, "extractor_version": "0.2.0",
                  "llvm_version": "21.1.8", "profile": "source-preserving"}],
        budgets=expected_analysis_protocol()["budgets"], effects=[], order=[], returns=[],
        escape=[], adoptions=[], dependencies=[], local_dependencies=[], resolutions=[],
        diagnostics=[], status="complete")
    for directory_name, identifier, document in (
            ("entity-index", scope, index), ("summaries", "context", summary)):
        directory = tmp_path / directory_name; directory.mkdir(exist_ok=True)
        (directory / f"{identifier}.json").write_text(canonical(document), encoding="utf-8")
        reference = {"kind": document["kind"], "id": identifier, "digest": identity(document)}
        assert _resolve_dependency(tmp_path, reference) == document

    value = {"kind": "ProgramEntityIndex", "scope_id": "scope"}
    directory = tmp_path / "entity-index"
    (directory / "scope.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(analyzer, "_read_dependency", lambda path, kind: value)
    reference = {"kind": value["kind"], "id": "scope", "digest": identity(value)}
    assert _resolve_dependency(tmp_path, reference) is value
    with pytest.raises(AnalysisError, match="digest changed"):
        _resolve_dependency(tmp_path, {**reference, "digest": "0" * 64})
    with pytest.raises(AnalysisError, match="missing"):
        _resolve_dependency(tmp_path, {**reference, "id": "absent"})
    (tmp_path / "unsupported.json").write_text("{}", encoding="utf-8")
    monkeypatch.undo()
    with pytest.raises(AnalysisError, match="Unsupported"):
        _resolve_dependency(tmp_path, {"kind": "Unsupported", "id": "unsupported",
                                       "digest": "0" * 64})


def test_cross_tu_return_local_chain_mismatch_expiry_and_relation_budgets_are_conservative():
    actual = object_instance(storage_instance("global", "actual"), offset=8, size=16)
    formal = object_instance(storage_instance("parameter", "%formal", function_id="callee"),
                             offset=0, size=16)
    local = object_instance(storage_instance("unknown", "%load", function_id="callee"),
                            offset=4, size=4)
    caller = llvm_facts("caller", domains=[("actual", must(actual))])
    caller["values"][0].update(function_id=None, ir_name="@actual", argument_index=None)
    caller["call_edges"] = [{"id": "call", "caller": "caller", "callee": "callee",
                             "arguments": ["@actual"], "result": "%call", "status": "direct"}]
    callee = llvm_facts("callee", domains=[("formal", must(formal)), ("load", must(formal)),
                                            ("result", may([local], opposed=("llvm-unknown-storage-kind",)))])
    callee["values"][0].update(function_id="callee", opcode="argument", ir_name="%formal", argument_index=0)
    callee["values"][1].update(function_id="callee", opcode="load", ir_name="%load", argument_index=None)
    callee["values"][2].update(function_id="callee", opcode="getelementptr", ir_name="%result", argument_index=None)
    callee["returns"] = [{"id": "return", "function_id": "callee", "value": "%result",
                          "lifetime": "unknown"}]

    evidence = adopted_evidence(caller, callee)
    domains, relations, frontier = compose_evidence(
        [], [caller, callee], budgets(), **evidence)
    assert not frontier
    assert {item["kind"]: item["status"] for item in relations} == {
        "direct-actual-to-formal": "exact", "direct-return-to-call": "exact"}
    result = dict(domains)["call:return"]
    assert result["state"] == "must"
    assert result["candidates"][0]["object"]["storage"]["source_id"] == "actual"
    assert result["candidates"][0]["object"]["byte_range"] == {"offset": 12, "size": 4}
    assert "bounded-local-value-resolution" in result["candidates"][0]["proof"]

    expired = deepcopy(callee); expired["returns"][0]["lifetime"] = "expired"
    expired_result = dict(compose_evidence(
        [], [caller, expired], budgets(), **evidence)[0])["call:return"]
    assert expired_result["state"] == "unknown" and expired_result["reason"] == "expired-local-return"

    incompatible = deepcopy(callee); incompatible["target"] = "aarch64-linux-gnu"
    _, mismatch_relations, _ = compose_evidence(
        [], [caller, incompatible], budgets(), **evidence)
    assert mismatch_relations[0]["status"] == "candidate"

    limited = budgets(load_hops=1)
    assert any(item["code"] == "load-hop-budget-exhausted"
               for item in compose_evidence([], [caller, callee], limited, **evidence)[2])
    relation_limited = budgets(relations=1)
    assert any(item["code"] == "relation-budget-exhausted"
               for item in compose_evidence([], [caller, callee], relation_limited, **evidence)[2])


def test_recursive_graph_and_nameless_source_paths_publish_frontiers_without_guessing():
    value = object_instance(storage_instance("global", "g"), offset=0, size=4)
    facts = llvm_facts("cycle", domains=[("g", must(value))])
    facts["call_edges"] = [
        {"id": "ab", "caller": "a", "callee": "b", "arguments": [], "result": None, "status": "direct"},
        {"id": "bc", "caller": "b", "callee": "c", "arguments": [], "result": None, "status": "direct"},
        {"id": "cb", "caller": "c", "callee": "b", "arguments": [], "result": None, "status": "direct"},
    ]
    source = source_facts("cycle")
    source["paths"][0]["base"]["name"] = None
    _, relations, frontier = compose_evidence([source], [facts], budgets(recursive_iterations=1))
    assert not relations
    assert any(item["code"] == "recursive-budget-exhausted" for item in frontier)


def test_worker_transports_verify_protocol_hashes_identity_and_failures(tmp_path):
    source_path = tmp_path / "a.c"; source_path.write_text("int g;", encoding="utf-8")
    profile = {"profile_id": "a" * 64, "working_directory": str(tmp_path),
               "source": {"path": str(source_path), "sha256": file_hash(source_path)},
               "argv": ["clang-21", "-std=c17"]}
    source_request = provenance_document(
        "SourceObjectPathRequest", profile=profile, physical_tu_id="tu",
        source_path=str(source_path), budgets=budgets(), semantic_digest=None)
    bitcode = tmp_path / "a.bc"; bitcode.write_bytes(b"BC\xc0\xdeplaceholder")
    llvm_request = provenance_document(
        "LLVMObjectProvenanceRequest", artifact_key="c" * 64, profile_id="a" * 64,
        physical_tu_id="tu", bitcode={"path": str(bitcode), "sha256": file_hash(bitcode)},
        dependencies=[], budgets=budgets(), semantic_digest=None)
    source_output = source_facts()
    source_output["source_digest"] = profile["source"]["sha256"]
    source_output.pop("semantic_digest")
    llvm_output = llvm_facts()
    llvm_output["bitcode_digest"] = file_hash(bitcode)
    llvm_output.pop("semantic_digest")

    def runner(argv, cwd, **kwargs):
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
        value = source_output if "--object-path-request" in argv else llvm_output
        return {"status": "completed", "stdout": canonical(value), "stderr": ""}

    assert check_worker("worker", tmp_path, runner=runner)["protocol_version"] == 1
    assert analyze_source_paths(source_request, "source", tmp_path, runner=runner)["status"] == "complete"
    facts = analyze_llvm_provenance(llvm_request, "ir", tmp_path, runner=runner)
    assert facts["values"][0]["domain"]["candidates"][0]["object"]["id"]

    bad_source = deepcopy(source_output); bad_source["profile_id"] = "f" * 64
    def bad_source_identity(argv, cwd, **kwargs):
        value = expected_provenance_protocol() if "--object-provenance-protocol" in argv else bad_source
        return {"status": "completed", "stdout": canonical(value), "stderr": ""}
    with pytest.raises(AnalysisError, match="does not match"):
        analyze_source_paths(source_request, "source", tmp_path, runner=bad_source_identity)
    bad_llvm = deepcopy(llvm_output); bad_llvm["artifact_key"] = "f" * 64
    def bad_llvm_identity(argv, cwd, **kwargs):
        value = expected_provenance_protocol() if "--object-provenance-protocol" in argv else bad_llvm
        return {"status": "completed", "stdout": canonical(value), "stderr": ""}
    with pytest.raises(AnalysisError, match="does not match"):
        analyze_llvm_provenance(llvm_request, "ir", tmp_path, runner=bad_llvm_identity)
    bitcode.write_bytes(b"changed")
    with pytest.raises(AnalysisError, match="missing or changed"):
        analyze_llvm_provenance(llvm_request, "ir", tmp_path, runner=runner)

    def bad_runner(argv, cwd, **kwargs):
        return {"status": "failed", "stdout": "", "stderr": "failed", "code": "nonzero_exit"}

    with pytest.raises(AnalysisError, match="mismatch"):
        check_worker("worker", tmp_path, runner=bad_runner)
    source_path.write_text("changed", encoding="utf-8")
    with pytest.raises(AnalysisError, match="missing or changed"):
        analyze_source_paths(source_request, "source", tmp_path, runner=runner)


def test_full_orchestration_cache_determinism_outputs_and_cli_exit_codes(tmp_path):
    source_path = tmp_path / "main.c"; source_path.write_text("int g;", encoding="utf-8")
    bitcode = tmp_path / "main.bc"; bitcode.write_bytes(b"BC\xc0\xdeplaceholder")
    profile = {"profile_id": "a" * 64, "working_directory": str(tmp_path),
               "source": {"path": str(source_path), "sha256": file_hash(source_path)},
               "argv": ["clang-21", "-std=c17"]}
    source_request = provenance_document(
        "SourceObjectPathRequest", profile=profile, physical_tu_id="tu",
        source_path=str(source_path), budgets=budgets(), semantic_digest=None)
    llvm_request = provenance_document(
        "LLVMObjectProvenanceRequest", artifact_key="c" * 64, profile_id="a" * 64,
        physical_tu_id="tu", bitcode={"path": str(bitcode), "sha256": file_hash(bitcode)},
        dependencies=[], budgets=budgets(), semantic_digest=None)
    source_request_path = tmp_path / "source.json"
    llvm_request_path = tmp_path / "llvm.json"
    source_request_path.write_text(canonical(source_request), encoding="utf-8")
    llvm_request_path.write_text(canonical(llvm_request), encoding="utf-8")
    outer = request([member(source=str(source_request_path), llvm=str(llvm_request_path))])
    outer_path = tmp_path / "request.json"; outer_path.write_text(canonical(outer), encoding="utf-8")
    source_output = source_facts(); source_output["source_digest"] = file_hash(source_path); source_output.pop("semantic_digest")
    llvm_output = llvm_facts(); llvm_output["bitcode_digest"] = file_hash(bitcode)
    llvm_output["values"][0]["id"] = "mutex-payload"; llvm_output.pop("semantic_digest")
    calls = []

    def runner(argv, cwd, **kwargs):
        calls.append(tuple(argv))
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
        value = source_output if "--object-path-request" in argv else llvm_output
        return {"status": "completed", "stdout": canonical(value), "stderr": ""}

    cold = analyze_object_provenance(outer_path, tmp_path / "cache", tmp_path / "cold",
                                     "source-worker", "ir-worker", runner=runner)
    action_calls = len([item for item in calls if "--object-path-request" in item or "--object-provenance-request" in item])
    warm = analyze_object_provenance(outer_path, tmp_path / "cache", tmp_path / "warm",
                                     "source-worker", "ir-worker", runner=runner)
    assert action_calls == 2
    assert len([item for item in calls if "--object-path-request" in item or "--object-provenance-request" in item]) == 2
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert cold["cache"] == {"hits": 0, "misses": 3}
    assert warm["cache"] == {"hits": 3, "misses": 0}
    assert (tmp_path / "cold/report.json").is_file()
    graph = json.loads(next((tmp_path / "cold/graphs").glob("*.json")).read_text(encoding="utf-8"))
    assert {item["consumer"] for item in graph["adapters"]} == {"A4", "P4"}

    llvm_output["values"][0]["id"] = "plain"
    plain = analyze_object_provenance(outer_path, tmp_path / "plain-cache", tmp_path / "plain",
                                      "source-worker", "ir-worker", runner=runner)
    plain_graph = json.loads(next((tmp_path / "plain/graphs").glob("*.json")).read_text(encoding="utf-8"))
    assert plain["status"] == "complete" and plain_graph["adapters"] == []

    source_only = request([member(source=str(source_request_path), llvm=None)])
    source_only_path = tmp_path / "source-only.json"
    source_only_path.write_text(canonical(source_only), encoding="utf-8")
    partial = analyze_object_provenance(source_only_path, tmp_path / "cache", tmp_path / "source-only",
                                        "source-worker", "ir-worker", runner=runner)
    assert partial["status"] == "partial" and partial["modes"]["ast-only"] == 1

    ticks = iter((0.0, 3601.0))
    timed = analyze_object_provenance(
        source_only_path, tmp_path / "timed-cache", tmp_path / "timed",
        "source-worker", "ir-worker", runner=runner, clock=lambda: next(ticks))
    assert timed["status"] == "partial"
    assert any(item["code"] == "object-provenance-request-time-budget-exhausted"
               for item in timed["frontier"])

    failed_source = source_facts(status="failed")
    failed_source["source_digest"] = file_hash(source_path); failed_source.pop("semantic_digest")
    def failed_fact_runner(argv, cwd, **kwargs):
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": canonical(failed_source), "stderr": ""}
    failed_fact = analyze_object_provenance(
        source_only_path, tmp_path / "failed-fact-cache", tmp_path / "failed-fact",
        "source-worker", "ir-worker", runner=failed_fact_runner)
    assert failed_fact["status"] == "partial" and failed_fact["cache"]["misses"] == 2

    def failed_runner(argv, cwd, **kwargs):
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
        return {"status": "failed", "code": "worker-failed", "stdout": "", "stderr": "boom"}
    failed = analyze_object_provenance(
        outer_path, tmp_path / "failed-cache", tmp_path / "all-failed",
        "source-worker", "ir-worker", runner=failed_runner)
    assert failed["status"] == "failed" and failed["exit_code"] == 1

    limited = deepcopy(source_only); limited["budgets"]["request_output_bytes"] = 1024
    limited["semantic_digest"] = semantic_digest(limited)
    limited_path = tmp_path / "limited.json"; limited_path.write_text(canonical(limited), encoding="utf-8")
    with pytest.raises(AnalysisError, match="request_output_bytes"):
        analyze_object_provenance(limited_path, tmp_path / "cache", tmp_path / "limited-output",
                                  "source-worker", "ir-worker", runner=runner)

    stdout, stderr = io.StringIO(), io.StringIO()
    assert cli.main(["analyze-object-provenance", "--request", str(tmp_path / "missing.json"),
                     "--artifact-store", str(tmp_path / "cache"), "--output", str(tmp_path / "failed")],
                    stdout=stdout, stderr=stderr) == 1
    assert json.loads(stdout.getvalue())["kind"] == "BoundedObjectProvenanceReport"


def test_truth_comparison_reports_each_language_tp_fp_fn_and_abstention():
    cases = [{"id": f"case-{index}", "standard": standard}
             for index, standard in enumerate(("c11", "c17", "c++17", "c++20"), 1)]
    suite = provenance_document("ObjectProvenanceValidationSuite", suite_version="1", cases=cases,
                                semantic_digest=None)
    truth = provenance_document(
        "ObjectProvenanceValidationTruth", suite_version="1",
        cases=[{"case_id": item["id"], "id": item["id"], "standard": item["standard"],
                "must_objects": [item["id"]]} for item in cases], semantic_digest=None)
    actuals = {
        "case-1": {"status": "complete", "must_objects": ["case-1"]},
        "case-2": {"status": "complete", "must_objects": ["extra"]},
        "case-3": {"status": "partial", "must_objects": [], "unknown": True},
    }
    report = compare_truth(suite, truth, actuals)
    assert report["status"] == "partial"
    assert report["metrics"] == {"planned": 4, "completed": 3, "tp": 1, "fp": 1,
                                  "fn": 2, "abstention": 2}
    assert report["languages"]["c11"]["tp"] == 1
    assert report["languages"]["c++20"]["completed"] == 0


def test_contract_negative_boundaries_cover_sorted_references_domains_and_claims(tmp_path, monkeypatch):
    malformed = tmp_path / "malformed.json"; malformed.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        provenance_contracts.read_provenance_document(malformed, "BoundedObjectProvenanceRequest")
    bad_schema = tmp_path / "schema.json"; bad_schema.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(provenance_contracts, "SCHEMA", bad_schema)
    with pytest.raises(AnalysisError, match="budget schema"):
        expected_provenance_protocol()
    monkeypatch.setattr(provenance_contracts, "SCHEMA", provenance_contracts.ROOT / "schemas/bounded_object_provenance.json")

    obj = object_instance(storage_instance("global", "g"), offset=0, size=4)
    value = llvm_facts(domains=[("v", must(obj, guards=("a", "b")))])
    value["values"][0]["domain"]["candidates"][0]["guards"] = ["b", "a"]
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="guards"):
        validate_provenance_document(value, value["kind"])
    for field, expected in (("opposed", "Opposed"),):
        value = llvm_facts(domains=[("v", must(obj))])
        value["values"][0]["domain"]["candidates"][0][field] = ["b", "a"]
        value["values"][0]["domain"]["state"] = "may"
        value["semantic_digest"] = semantic_digest(value)
        with pytest.raises(AnalysisError, match=expected):
            validate_provenance_document(value, value["kind"])
    value = llvm_facts(domains=[("v", must(obj))])
    value["values"][0]["domain"]["candidates"][0]["object"]["id"] = "0" * 64
    value["semantic_digest"] = semantic_digest(value)
    with pytest.raises(AnalysisError, match="identity"):
        validate_provenance_document(value, value["kind"])
    for domain in ({"state": "may", "candidates": [], "reason": None},
                   {"state": "unknown", "candidates": [], "reason": None}):
        value = llvm_facts(); value["values"][0]["domain"] = domain
        value["semantic_digest"] = semantic_digest(value)
        with pytest.raises(AnalysisError, match="requires"):
            validate_provenance_document(value, value["kind"])
    unsorted = request(); unsorted["roots"] = ["z", "a"]; unsorted["semantic_digest"] = semantic_digest(unsorted)
    with pytest.raises(AnalysisError, match="roots"):
        validate_provenance_document(unsorted, unsorted["kind"])

    source = source_facts(); source["standard"] = "c++17"; source["semantic_digest"] = semantic_digest(source)
    with pytest.raises(AnalysisError, match="disagree"):
        validate_provenance_document(source, source["kind"])
    source = source_facts(); source["paths"][0]["evidence"] = ["z", "a"]; source["semantic_digest"] = semantic_digest(source)
    with pytest.raises(AnalysisError, match="evidence"):
        validate_provenance_document(source, source["kind"])
    source = source_facts(); source["paths"][0]["reason"] = "bad"; source["semantic_digest"] = semantic_digest(source)
    with pytest.raises(AnalysisError, match="Exact"):
        validate_provenance_document(source, source["kind"])

    graph = build_graph(request(), [source_facts()], [llvm_facts()], domains=[("v", must(obj))])
    missing = deepcopy(graph); missing["objects"] = []; missing["semantic_digest"] = semantic_digest(missing)
    with pytest.raises(AnalysisError, match="missing object"):
        validate_provenance_document(missing, missing["kind"])
    missing = deepcopy(graph); missing["adapters"] = [{"id": "a", "status": "exact", "object_id": "0" * 64}]
    missing["semantic_digest"] = semantic_digest(missing)
    with pytest.raises(AnalysisError, match="adapter"):
        validate_provenance_document(missing, missing["kind"])
    complete_frontier = deepcopy(graph); complete_frontier["frontier"] = [diagnostic("x", "x", "x")]
    complete_frontier["semantic_digest"] = semantic_digest(complete_frontier)
    with pytest.raises(AnalysisError, match="Complete graph"):
        validate_provenance_document(complete_frontier, complete_frontier["kind"])

    report = build_report(request(), graph)
    broken = deepcopy(report); broken["dependencies"] = []; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="missing from dependencies"):
        validate_provenance_document(broken, broken["kind"])
    broken = deepcopy(report); broken["safety"] = "safe"; broken["semantic_digest"] = semantic_digest(broken)
    with pytest.raises(AnalysisError, match="not_established|const"):
        validate_provenance_document(broken, broken["kind"])
    broken = deepcopy(request()); broken["kind"] = "SourceObjectPathFacts"
    with pytest.raises(AnalysisError, match="required|Expected"):
        validate_provenance_document(broken, "SourceObjectPathFacts")
    broken = request(); broken["semantic_digest"] = "0" * 64
    with pytest.raises(AnalysisError, match="semantic digest"):
        validate_provenance_document(broken, broken["kind"])


def test_validation_denominator_failures_cache_collision_and_link_race(tmp_path, monkeypatch):
    cases = [{"id": str(index), "standard": standard}
             for index, standard in enumerate(("c11", "c17", "c++17", "c++20"))]
    report = provenance_document("ObjectProvenanceValidationReport", suite_version="1", status="complete",
                                 metrics={}, languages={name: {} for name in ("c11", "c17", "c++17", "c++20")},
                                 diagnostics=[], semantic_digest=None)
    report["languages"].pop("c11"); report["semantic_digest"] = semantic_digest(report)
    with pytest.raises(AnalysisError, match="four language"):
        validate_provenance_document(report, report["kind"])
    suite = provenance_document("ObjectProvenanceValidationSuite", suite_version="1", cases=cases,
                                semantic_digest=None)
    suite["cases"][0]["standard"] = "c17"; suite["semantic_digest"] = semantic_digest(suite)
    with pytest.raises(AnalysisError, match="four standards"):
        validate_provenance_document(suite, suite["kind"])

    cache = ProvenanceCache(tmp_path)
    first = source_facts(); key = cache_key("source", {})
    path = cache.publish("source", key, first)
    second = source_facts("other")
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("source", key, second)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(AnalysisError, match="Invalid A5 cache"):
        cache.load("source", key, first["kind"])
    path.unlink()
    def same_race(source, destination):
        Path(destination).write_text(canonical(first), encoding="utf-8")
        raise FileExistsError()
    monkeypatch.setattr(provenance_cache.os, "link", same_race)
    assert cache.publish("source", key, first) == path
    other_key = cache_key("source", {"other": True})
    with pytest.raises(AnalysisError, match="Conflicting"):
        cache.publish("source", other_key, second)


def test_transport_rejects_bad_output_identity_and_normalizes_opposed_candidates(tmp_path):
    def protocol_runner(argv, cwd, **kwargs):
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": "not-json", "stderr": ""}
        return {"status": "failed", "code": "worker-failed", "stderr": "boom", "stdout": ""}
    with pytest.raises(AnalysisError, match="mismatch"):
        check_worker("worker", tmp_path, runner=protocol_runner)

    def invalid_output(argv, cwd, **kwargs):
        if "--object-provenance-protocol" in argv:
            return {"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
        return {"status": "completed", "stdout": "{", "stderr": ""}
    with pytest.raises(AnalysisError, match="Invalid A5 worker JSON"):
        _run_request({"budgets": budgets()}, "worker", tmp_path, "--x", "x", runner=invalid_output)
    with pytest.raises(AnalysisError, match="worker failed"):
        _run_request({"budgets": budgets()}, "worker", tmp_path, "--x", "x",
                     runner=lambda argv, cwd, **kwargs: ({"status": "completed", "stdout": canonical(expected_provenance_protocol()), "stderr": ""}
                                                        if "--object-provenance-protocol" in argv else
                                                        {"status": "failed", "code": "worker-failed", "stderr": "boom", "stdout": ""}))

    value = llvm_facts()
    domain = value["values"][0]["domain"]
    domain["candidates"][0]["opposed"] = ["captured"]
    assert _normalize_worker_objects(value)["values"][0]["domain"]["state"] == "may"
    value = llvm_facts(); value["values"][0]["domain"] = {"state": "must", "candidates": [], "reason": None}
    normalized = _normalize_worker_objects(value)["values"][0]["domain"]
    assert normalized == {"state": "unknown", "candidates": [], "reason": "worker-candidate-empty"}
    value = llvm_facts()
    value["values"][0]["domain"]["candidates"][0]["object"]["storage"]["kind"] = "unknown"
    normalized = _normalize_worker_objects(value)["values"][0]["domain"]
    assert normalized["state"] == "may"
    assert normalized["candidates"][0]["opposed"] == ["llvm-unknown-storage-kind"]


def test_lattice_merge_non_direct_and_missing_source_paths_cover_conservative_branches():
    obj = object_instance(storage_instance("global", "g"), offset=0, size=4)
    dep = {"kind": "x", "id": "x", "digest": "a" * 64}
    left = must(obj, guards=("a",), dependencies=(dep,))
    right = must(obj, guards=("b",), proof=("p",), dependencies=(dep,))
    merged = join(left, right)
    assert merged["state"] == "must" and merged["candidates"][0]["guards"] == ["a", "b"]
    assert join(must(obj), bottom()) == must(obj)
    assert specialize(unknown("virtual"), {})["reason"] == "virtual"
    facts = llvm_facts()
    facts["call_edges"] = [{"id": "indirect", "caller": "f", "callee": "g",
                            "arguments": [], "status": "indirect"}]
    facts["semantic_digest"] = semantic_digest(facts)
    _, relations, frontier = compose_evidence([], [facts], budgets())
    assert not relations and not frontier
