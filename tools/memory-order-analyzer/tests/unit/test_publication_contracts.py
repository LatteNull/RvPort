"""P4 contracts, graph rules, reports and cache unit coverage."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
import memory_order_analyzer.publication_cache as cache_module

from memory_order_analyzer.contracts import AnalysisError, canonical, identity
from memory_order_analyzer.publication_cache import PublicationCache, graph_key, local_key, template_key
from memory_order_analyzer.publication_contracts import (
    KINDS, MODEL_ID, diagnostic, expected_publication_protocol, layer_counts,
    outcome_counts, protocol_candidate_id, publication_document,
    read_publication_document, successful_observation_id, validate_publication_document,
)
from memory_order_analyzer.publication_graph import (
    PublicationGraphBuilder, _in_blocks, _object_key, _overlap, _predicate_accepts,
    build_publication_graph,
)
from memory_order_analyzer.publication_report import build_publication_report, failed_publication_report
from memory_order_analyzer.publication_report import _aggregate


A, B, C, D = (letter * 64 for letter in "abcd")


def ref(identifier, function="fn", artifact=A):
    return {"artifact_key": artifact, "function_id": function, "id": identifier}


def budgets(**changes):
    value = deepcopy(expected_publication_protocol()["budgets"])
    value.update(changes)
    return value


def request():
    return publication_document("PublicationRiskRequest", thread_request="thread-request.json",
                                model_id=MODEL_ID, budgets=budgets())


def origin(artifact=A):
    return {"artifact_key": artifact, "module_hash": C, "facts_hash": D,
            "extractor_version": "0.2.0", "llvm_version": "21.1.8",
            "profile": "source-preserving"}


def scalar(value, bits=32):
    return {"state": "exact", "bits": bits, "hex": f"{value:02X}"}


def obj_range(source):
    return {"object": deepcopy(source), "offset_bytes": "0", "size_bytes": "4",
            "address_space": 0}


def access(identifier, source, kind, object_source, *, atomic=False, ordering=None,
           value=None, multiplicity="single"):
    return {"id": identifier, "source": deepcopy(source), "kind": kind,
            "atomic": atomic, "volatile": False, "ordering": ordering,
            "syncscope": "system" if atomic else None, "range": obj_range(object_source),
            "value": deepcopy(value) if value else {"state": "unknown", "reason": "runtime"},
            "multiplicity": multiplicity, "proof": [deepcopy(source)], "status": "exact", "reason": None}


def local(artifact, accesses=(), initializers=(), observations=(), gates=(), *, status="complete"):
    return publication_document(
        "PublicationLocalFacts", origin=origin(artifact), budgets=budgets(),
        accesses=list(accesses), initializers=list(initializers), observations=list(observations),
        gates=list(gates), returns=[], order=[], analysis_evidence=[], diagnostics=[],
        frontier=[] if status == "complete" else [diagnostic("partial", "局部不完整", "Local incomplete")],
        status=status)


def scenario(*, store_order="release", load_order="acquire", flag_atomic=True,
             payload_atomic=False, reverse=False, extra_writer=False, late_acquire=False,
             fence=False, local_status="complete"):
    flag, payload = ref("flag", None, A), ref("payload", None, A)
    publish_payload, publish_flag = ref("pub:b0:i0", "producer", A), ref("pub:b0:i1", "producer", A)
    if reverse:
        publish_flag, publish_payload = ref("pub:b0:i0", "producer", A), ref("pub:b0:i1", "producer", A)
    read_flag, read_payload = ref("con:b0:i0", "consumer", B), ref("con:b1:i0", "consumer", B)
    block = ref("con:b1", "consumer", B)
    flag_key, payload_key = _object_key(obj_range(flag)), _object_key(obj_range(payload))

    def thread_effect(identifier, effect_id, source, invocation, thread, kind, object_key,
                      atomic, ordering, value_key=None):
        return {"id": identifier, "effect_id": effect_id, "source": deepcopy(source),
                "invocation_id": invocation, "thread_instance_id": thread, "kind": kind,
                "object_key": object_key, "offset_bytes": "0", "size_bytes": "4",
                "atomic": atomic, "ordering": ordering, "failure_ordering": None,
                "syncscope": "system" if atomic else None, "value_key": value_key, "guards": []}

    effects = [
        thread_effect("pw", "spw", publish_payload, "ip", "publisher", "write", payload_key,
                      payload_atomic, "monotonic" if payload_atomic else None),
        thread_effect("fw", "sfw", publish_flag, "ip", "publisher", "write", flag_key,
                      flag_atomic, store_order if flag_atomic else None),
        thread_effect("fr", "sfr", read_flag, "ic", "consumer", "read", flag_key,
                      flag_atomic, load_order if flag_atomic else None),
        thread_effect("pr", "spr", read_payload, "ic", "consumer", "read", payload_key,
                      payload_atomic, "monotonic" if payload_atomic else None),
    ]
    if extra_writer:
        effects.append(thread_effect("fw2", "sfw2", ref("pub:b2:i0", "producer", A),
                                     "ip", "publisher", "write", flag_key, True, "release"))
    if late_acquire:
        effects.append(thread_effect("late", "slate", ref("con:b2:i0", "consumer", B),
                                     "ic", "consumer", "read", flag_key, True, "acquire"))
    if fence:
        effects.append(thread_effect("fence", "sfence", ref("pub:b0:if", "producer", A),
                                     "ip", "publisher", "fence", None, True, "release"))
    order = [{"id": "payload-publish", "kind": "intra-thread",
              "before": "fw" if reverse else "pw", "after": "pw" if reverse else "fw",
              "relation": "must-before", "guards": [], "proof": [deepcopy(publish_payload)]}]
    if late_acquire:
        order.append({"id": "payload-late", "kind": "intra-thread", "before": "pr", "after": "late",
                      "relation": "must-before", "guards": [], "proof": [deepcopy(read_payload)]})
    thread_graph = {"status": "complete", "effects": effects, "order": order,
                    "mhp": [{"left": "consumer", "right": "publisher", "relation": "may_parallel"}]}
    predicate = {"kind": "eq", "bits": 32, "hex": "01", "negated": False}
    observation = {"id": "obs", "source": deepcopy(read_flag), "access_id": "read-flag",
                   "predicate": predicate, "result_source": ref("con:b0:i2", "consumer", B),
                   "proof": [deepcopy(read_flag)], "status": "exact", "reason": None}
    gate = {"id": "gate", "observation_id": "obs", "terminator": ref("con:b0:i2", "consumer", B),
            "success_edge": 0, "success_target": deepcopy(block), "retry_edge": 1,
            "controlled_blocks": [deepcopy(block)], "repeated": False,
            "proof": [deepcopy(read_flag)], "status": "exact", "reason": None}
    initializer = {"id": "init", "source": deepcopy(flag), "range": obj_range(flag),
                   "value": scalar(0), "proof": [deepcopy(flag)], "status": "exact", "reason": None}
    locals_ = {
        A: local(A, [access("write-payload", publish_payload, "write", payload,
                           atomic=payload_atomic, ordering="monotonic" if payload_atomic else None, value=scalar(42)),
                     access("write-flag", publish_flag, "write", flag, atomic=flag_atomic,
                            ordering=store_order if flag_atomic else None, value=scalar(1))], [initializer]),
        B: local(B, [access("read-flag", read_flag, "read", flag, atomic=flag_atomic,
                           ordering=load_order if flag_atomic else None),
                     access("read-payload", read_payload, "read", payload, atomic=payload_atomic,
                            ordering="monotonic" if payload_atomic else None)],
                 observations=[observation], gates=[gate], status=local_status),
    }
    static_effects = [{"id": item["effect_id"], "multiplicity": "single"} for item in effects]
    summaries = {"summary": {"context_id": "summary", "effects": static_effects,
                              "invocations": [{"id": "ip", "callsite": None},
                                              {"id": "ic", "callsite": None}]}}
    inputs = SimpleNamespace(scope_id=C, scope={"members": [A, B], "closed": True,
                                               "external_boundaries": []},
                             modules={A: {"source_mapping": "complete"},
                                      B: {"source_mapping": "complete"}})
    profiles = {A: "clang:c:c11:x86:layout", B: "clang:c:c11:x86:layout"}
    return inputs, request(), thread_graph, locals_, summaries, profiles


def test_protocol_contract_roundtrip_and_strict_rejections(tmp_path):
    protocol = expected_publication_protocol()
    assert protocol["kinds"] == dict.fromkeys(KINDS, 1)
    value = request()
    path = tmp_path / "request.json"; path.write_text(canonical(value), encoding="utf-8")
    assert read_publication_document(path, "PublicationRiskRequest") == value
    for mutation in [lambda item: item.update(extra=True),
                     lambda item: item.update(schema_version=2),
                     lambda item: item.update(model_id="future")]:
        invalid = deepcopy(value); mutation(invalid)
        with pytest.raises(AnalysisError):
            validate_publication_document(invalid, "PublicationRiskRequest")
    with pytest.raises(AnalysisError, match="Unknown publication contract"):
        validate_publication_document(value, "future")
    changed = deepcopy(protocol); changed["policy_id"] = "future"
    changed_path = tmp_path / "protocol.json"; changed_path.write_text(json.dumps(changed))
    with pytest.raises(AnalysisError, match="does not match"):
        expected_publication_protocol(changed_path)
    with pytest.raises(AnalysisError, match="Invalid or missing JSON"):
        expected_publication_protocol(tmp_path / "missing.json")
    malformed = tmp_path / "malformed.json"; malformed.write_text("[")
    with pytest.raises(AnalysisError):
        expected_publication_protocol(malformed)


def test_local_reference_closure_duplicate_and_frontier_rejections():
    values = scenario()[3][B]
    assert validate_publication_document(values, "PublicationLocalFacts") is values
    duplicate = deepcopy(values); duplicate["accesses"] *= 2
    with pytest.raises(AnalysisError, match="Duplicate publication access"):
        validate_publication_document(duplicate, "PublicationLocalFacts")
    dangling = deepcopy(values); dangling["observations"][0]["access_id"] = "missing"
    with pytest.raises(AnalysisError, match="dangling access"):
        validate_publication_document(dangling, "PublicationLocalFacts")
    complete_frontier = deepcopy(values); complete_frontier["frontier"] = [diagnostic("x", "中", "en")]
    with pytest.raises(AnalysisError, match="Complete publication-local"):
        validate_publication_document(complete_frontier, "PublicationLocalFacts")


def test_analysis_evidence_owner_dependency_and_proof_closure_rejections():
    value = deepcopy(scenario()[3][B])
    source = deepcopy(value["accesses"][0]["source"])
    proof = {"artifact_key": B, "function_id": source["function_id"], "analysis_id": "proof"}
    value["analysis_evidence"] = [{"ref": proof, "kind": "unit", "source": source,
                                   "inputs": [source], "result": "exact"}]
    value["accesses"][0]["proof"] = [proof]
    assert validate_publication_document(value, "PublicationLocalFacts") is value
    mutations = [
        lambda item: item["analysis_evidence"].append(deepcopy(item["analysis_evidence"][0])),
        lambda item: item["analysis_evidence"][0]["ref"].update(artifact_key=A),
        lambda item: item["analysis_evidence"][0]["ref"].update(function_id="other"),
        lambda item: item["analysis_evidence"][0].update(inputs=[{"artifact_key": B, "function_id": source["function_id"], "analysis_id": "missing"}]),
        lambda item: item["analysis_evidence"][0].update(inputs=[ref("foreign", artifact=A)]),
        lambda item: item["accesses"][0].update(proof=[{"artifact_key": B, "function_id": source["function_id"], "analysis_id": "missing"}]),
    ]
    for mutate in mutations:
        invalid = deepcopy(value); mutate(invalid)
        with pytest.raises(AnalysisError):
            validate_publication_document(invalid, "PublicationLocalFacts")
    foreign = deepcopy(value); foreign["accesses"][0]["source"]["artifact_key"] = A
    with pytest.raises(AnalysisError, match="Foreign publication-local"):
        validate_publication_document(foreign, "PublicationLocalFacts")
    dangling_gate = deepcopy(value); dangling_gate["gates"][0]["observation_id"] = "missing"
    with pytest.raises(AnalysisError, match="Gate has a dangling"):
        validate_publication_document(dangling_gate, "PublicationLocalFacts")
    dangling_return = deepcopy(value)
    dangling_return["returns"] = [{"id": "return", "observation_id": "missing",
        "source": source, "predicate": None, "proof": [source], "status": "exact", "reason": None}]
    with pytest.raises(AnalysisError, match="Return dependency"):
        validate_publication_document(dangling_return, "PublicationLocalFacts")


def test_publication_local_order_requires_closed_same_function_access_endpoints():
    value = deepcopy(scenario()[3][A])
    before, after = (deepcopy(item["source"]) for item in value["accesses"][:2])
    proof = {"artifact_key": A, "function_id": before["function_id"],
             "analysis_id": "dominance-order"}
    value["analysis_evidence"] = [{"ref": proof, "kind": "publication-order",
        "source": after, "inputs": [before, after], "result": "must-before"}]
    value["order"] = [{"id": "dominance-order", "before": before, "after": after,
        "relation": "must-before", "proof": [proof], "reason": "p4-dominance-order"}]
    assert validate_publication_document(value, "PublicationLocalFacts") is value

    duplicate = json.loads(json.dumps(value)); duplicate["order"] *= 2
    with pytest.raises(AnalysisError, match="Duplicate publication order"):
        validate_publication_document(duplicate, "PublicationLocalFacts")
    dangling = json.loads(json.dumps(value)); dangling["order"][0]["after"]["id"] = "missing"
    with pytest.raises(AnalysisError, match="dangling access"):
        validate_publication_document(dangling, "PublicationLocalFacts")
    cross_function = json.loads(json.dumps(value)); cross_function["order"][0]["after"]["function_id"] = "other"
    with pytest.raises(AnalysisError, match="crosses functions"):
        validate_publication_document(cross_function, "PublicationLocalFacts")


def test_identity_counts_predicates_and_ranges_are_deterministic():
    predicate = {"kind": "eq", "bits": 8, "hex": "01", "negated": False}
    assert _predicate_accepts(predicate, scalar(1, 8)) is True
    assert _predicate_accepts({**predicate, "kind": "ne"}, scalar(1, 8)) is False
    assert _predicate_accepts(predicate, {"state": "unknown", "reason": "x"}) is None
    assert _predicate_accepts(predicate, scalar(1, 16)) is None
    assert _overlap({"object_key": "o", "offset_bytes": "0", "size_bytes": "4"},
                    {"object_key": "o", "offset_bytes": "3", "size_bytes": "4"})
    assert not _overlap({"object_key": "o", "offset_bytes": None, "size_bytes": "4"},
                        {"object_key": "o", "offset_bytes": "0", "size_bytes": "4"})
    assert not _overlap({"object_key": "left", "offset_bytes": "0", "size_bytes": "4"},
                        {"object_key": "right", "offset_bytes": "0", "size_bytes": "4"})
    assert _object_key({"object": None, "address_space": 0}) is None
    assert _object_key({"object": ref("x"), "address_space": None}) is None
    assert not _in_blocks(None, [ref("b")])
    assert successful_observation_id("o", "e", "t", "i", predicate, "g") == successful_observation_id("o", "e", "t", "i", predicate, "g")
    assert protocol_candidate_id(a=1, b=2) != protocol_candidate_id(a=1, b=3)
    assert outcome_counts([], [])["evaluated_ratio"] is None
    assert layer_counts([])["complete_ratio"] is None


@pytest.mark.parametrize("options,code,status", [
    ({}, "single-publication-discharged", "discharged"),
    ({"store_order": "monotonic"}, "missing-release", "finding"),
    ({"load_order": "monotonic"}, "missing-acquire", "finding"),
    ({"flag_atomic": False}, "ordinary-conflict", "finding"),
    ({"payload_atomic": True, "store_order": "monotonic", "load_order": "monotonic"},
     "all-atomic-relaxed", "finding"),
    ({"reverse": True}, "publication-store-too-early", "finding"),
    ({"load_order": "monotonic", "late_acquire": True}, "acquire-too-late", "finding"),
    ({"extra_writer": True}, "protocol-unknown", "unknown"),
    ({"fence": True}, "protocol-unsupported", "unsupported"),
])
def test_graph_rules_cover_discharged_findings_unknown_and_unsupported(options, code, status):
    graph = build_publication_graph(*scenario(**options))
    assert validate_publication_document(graph, "SinglePublicationProtocolGraph") is graph
    assert graph["protocols"]
    assert any(item["code"] == code and item["status"] == status for item in graph["assessments"])
    assert graph["counts"] == outcome_counts(graph["protocols"], graph["assessments"])
    assert all(item["detail"] and item["detail_en"] for item in graph["assessments"])
    assert graph == build_publication_graph(*scenario(**options))


def test_graph_profile_mhp_budget_and_partial_inputs_propagate_conservatively():
    values = list(scenario())
    values[5][B] = None
    graph = build_publication_graph(*values)
    assert graph["status"] == "partial" and graph["assessments"][0]["status"] == "unknown"
    values = list(scenario())
    values[2]["mhp"][0]["relation"] = "not_parallel"
    graph = build_publication_graph(*values)
    assert not graph["protocols"] and graph["status"] == "complete"
    values = list(scenario())
    values[1]["budgets"]["protocol_candidates"] = 1
    values[2]["effects"].append(deepcopy(values[2]["effects"][0]))
    values[2]["effects"][-1].update(id="pw-extra", effect_id="spw-extra")
    values[4]["summary"]["effects"].append({"id": "spw-extra", "multiplicity": "single"})
    graph = build_publication_graph(*values)
    assert graph["status"] in {"complete", "partial"}
    builder = PublicationGraphBuilder(*scenario())
    assert builder._before("absent", "target") is False


def test_ast_source_completeness_is_candidate_relevant_and_zero_candidates_are_diagnostic():
    values = list(scenario())
    assistance = {"report": {"status": "partial"}, "binding": {"status": "partial"},
                  "overlay": {"status": "partial", "mappings": []}}
    values[2]["status"] = "partial"
    values[2]["frontier"] = []
    graph = build_publication_graph(*values, source_assistance=assistance)
    assert graph["protocols"] and graph["status"] == "complete"

    values = list(scenario())
    values[2]["mhp"][0]["relation"] = "not_parallel"
    graph = build_publication_graph(*values, source_assistance=assistance)
    assert not graph["protocols"] and graph["status"] == "partial"
    item = next(item for item in graph["frontier"]
                if item["code"] == "publication-candidate-unresolved")
    assert item["detail"] and item["detail_en"] and item["suggestion"] and item["suggestion_en"]


def test_p4_local_nodes_supplement_missing_p2_effects_and_bind_execution_order():
    inputs, req, _, locals_, _, profiles = scenario()
    producer = ref("producer", None, A); consumer = ref("consumer", None, B)
    thread_graph = {"status": "complete", "effects": [], "order": [],
        "mhp": [{"left": "consumer", "right": "publisher", "relation": "may_parallel"}],
        "contexts": [{"id": "pc", "entry": producer}, {"id": "cc", "entry": consumer}],
        "instances": [{"id": "publisher", "context_id": "pc"},
                      {"id": "consumer", "context_id": "cc"}]}
    publish_payload, publish_flag = locals_[A]["accesses"]
    locals_[A]["order"] = [{"before": publish_payload["source"],
                             "after": publish_flag["source"], "relation": "must-before"}]
    graph = build_publication_graph(inputs, req, thread_graph, locals_, {}, profiles, {})
    assert graph["protocols"] and graph["assessments"][0]["status"] == "discharged"
    builder = PublicationGraphBuilder(inputs, req, thread_graph, locals_, {}, profiles, {})
    assert any(effect.get("_p4_multiplicity") == "single" for effect in builder.effects.values())
    bound = deepcopy(thread_graph)
    for context in bound["contexts"]:
        context["dependency"] = {"kind": "EffectSummary", "id": "bound", "digest": A}
    assert not PublicationGraphBuilder(inputs, req, bound, locals_, {}, profiles, {}).effects


def test_cross_tu_wrapper_requires_registered_return_dependency():
    inputs, req, thread_graph, locals_, summaries, profiles = scenario()
    call_source = ref("caller:b0:i0", "caller", B)
    call_access = {"id": "call-access", "source": call_source, "kind": "call", "atomic": False,
        "volatile": False, "ordering": None, "syncscope": None,
        "range": {"object": None, "offset_bytes": None, "size_bytes": None, "address_space": None},
        "value": {"state": "unknown", "reason": "callee-return"}, "multiplicity": "single",
        "proof": [call_source], "status": "candidate", "reason": "callee-return"}
    observation = locals_[B]["observations"][0]
    original_access = next(item for item in locals_[B]["accesses"] if item["id"] == observation["access_id"])
    locals_[B]["accesses"].append(call_access)
    observation["access_id"] = "call-access"; observation["source"] = call_source
    locals_[B]["returns"] = [{"id": "return", "observation_id": "returned-observation",
        "source": ref("callee:b1:i0", "consumer", B), "predicate": None,
        "proof": [original_access["source"]], "status": "exact", "reason": None}]
    locals_[B]["observations"].append({"id": "returned-observation",
        "source": original_access["source"], "access_id": original_access["id"], "predicate": None,
        "result_source": ref("callee:b1:i0", "consumer", B),
        "proof": [original_access["source"]], "status": "exact", "reason": None})
    summaries["summary"]["invocations"][1].update(callsite=call_source,
        function={"artifact_key": B, "function_id": None, "id": "consumer"})
    builder = PublicationGraphBuilder(inputs, req, thread_graph, locals_, summaries, profiles)
    assert [item["id"] for item in builder._bound_effects(observation)] == ["fr"]
    builder.return_access_sources.clear()
    assert builder._bound_effects(observation) == []
    assert builder._bound_effects({"source": call_source, "access_id": "missing"}) == []
    assert builder._profile(A, B) is not None
    builder.profiles[B] = "other"
    assert builder._profile(A, B) is None


def test_graph_candidate_and_assessment_budgets_cut_with_frontier():
    values = list(scenario(extra_writer=True))
    values[1]["budgets"]["protocol_candidates"] = 1
    graph = build_publication_graph(*values)
    assert graph["status"] == "partial" and graph["frontier"][0]["code"] == "publication-graph-budget"
    values = list(scenario(store_order="monotonic"))
    values[1]["budgets"]["assessments"] = 1
    graph = build_publication_graph(*values)
    assert graph["status"] == "partial" and graph["frontier"]
    values = list(scenario())
    values[2]["order"] = []
    graph = build_publication_graph(*values)
    assert graph["assessments"][0]["code"] == "protocol-unknown"


def test_report_exit_precedence_and_failure_shape():
    assert _aggregate([]) == "not_run"
    assert _aggregate([{"status": "failed"}]) == "failed"
    assert _aggregate([{"status": "complete"}, {"status": "partial"}]) == "partial"
    inputs, req, thread_graph, locals_, summaries, profiles = scenario()
    graph = build_publication_graph(inputs, req, thread_graph, locals_, summaries, profiles)
    thread_report = {"thread_modeling": "complete"}
    report = build_publication_report(inputs, req, graph, locals_, thread_report)
    assert report["exit_code"] == 0 and report["verdict"] == "no_supported_risk_found"
    assert report["safety"] == "not_established"
    risky_values = scenario(store_order="monotonic")
    risky = build_publication_graph(*risky_values)
    report = build_publication_report(risky_values[0], risky_values[1], risky, risky_values[3], thread_report)
    assert report["exit_code"] == 3 and report["verdict"] == "risks_found" and report["findings"]
    partial_values = scenario(extra_writer=True)
    partial = build_publication_graph(*partial_values)
    report = build_publication_report(partial_values[0], partial_values[1], partial, partial_values[3], thread_report)
    assert report["exit_code"] == 2 and report["verdict"] == "inconclusive"
    failed = failed_publication_report("unit", "broken")
    assert failed["exit_code"] == 1 and failed["verdict"] == "failed"
    assert validate_publication_document(failed, "PublicationRiskReport") is failed
    unavailable_inputs, req, graph_input, locals_input, summaries_input, profiles = scenario()
    unavailable_inputs.modules[A]["source_mapping"] = "unavailable"
    unavailable_inputs.modules[B]["source_mapping"] = "unavailable"
    unavailable_graph = build_publication_graph(unavailable_inputs, req, graph_input, locals_input,
                                                summaries_input, profiles)
    unavailable = build_publication_report(unavailable_inputs, req, unavailable_graph, locals_input,
                                           {"thread_modeling": "failed"})
    assert unavailable["source_mapping"] == "unavailable" and unavailable["exit_code"] == 1


def test_graph_and_report_semantic_rejection_matrix():
    values = scenario()
    graph = build_publication_graph(*values)
    mutations = [
        lambda item: item["dependencies"].append(deepcopy(item["dependencies"][0])),
        lambda item: item["protocols"][0].update(successful_observation="missing"),
        lambda item: item["protocols"][0].update(assessment_ids=["missing"]),
        lambda item: item["assessments"][0].update(protocol_id="missing"),
        lambda item: item["counts"].update(planned=99),
        lambda item: (item.update(status="complete"), item["frontier"].append(diagnostic("x", "中", "en"))),
    ]
    for mutate in mutations:
        invalid = deepcopy(graph); mutate(invalid)
        with pytest.raises(AnalysisError):
            validate_publication_document(invalid, "SinglePublicationProtocolGraph")

    report = build_publication_report(values[0], values[1], graph, values[3],
                                      {"thread_modeling": "complete"})
    report_mutations = [
        lambda item: item["member_counts"].update(planned=99),
        lambda item: item["findings"].append(deepcopy(graph["assessments"][0])),
        lambda item: item["outcome_counts"].update(finding=1),
        lambda item: item.update(exit_code=2, verdict="inconclusive"),
        lambda item: item.update(exit_code=1, verdict="inconclusive"),
    ]
    for mutate in report_mutations:
        invalid = deepcopy(report); mutate(invalid)
        with pytest.raises(AnalysisError):
            validate_publication_document(invalid, "PublicationRiskReport")
    risky_values = scenario(store_order="monotonic")
    risky_graph = build_publication_graph(*risky_values)
    risky = build_publication_report(risky_values[0], risky_values[1], risky_graph,
                                     risky_values[3], {"thread_modeling": "complete"})
    risky["exit_code"] = 0
    with pytest.raises(AnalysisError, match="Exit zero"):
        validate_publication_document(risky, "PublicationRiskReport")
    no_findings = deepcopy(report); no_findings.update(exit_code=3, verdict="risks_found")
    with pytest.raises(AnalysisError, match="Exit three"):
        validate_publication_document(no_findings, "PublicationRiskReport")


def test_cache_keys_publish_load_corruption_collision_and_race(tmp_path, monkeypatch):
    value = build_publication_graph(*scenario())
    cache = PublicationCache(tmp_path / "cache")
    key = graph_key(request(), {"x": 1}, [B, A])
    assert graph_key(request(), {"x": 1}, [A, B]) == key
    assert local_key(origin(), budgets(), MODEL_ID) != local_key(origin(), budgets(local_steps=1), MODEL_ID)
    assert template_key(C, request(), [B, A]) == template_key(C, request(), [A, B])
    assert cache.load("graphs", key, "SinglePublicationProtocolGraph") is None
    path = cache.publish("graphs", key, value)
    assert cache.load("graphs", key, "SinglePublicationProtocolGraph") == value
    assert cache.publish("graphs", key, value) == path
    path.write_text("{}")
    with pytest.raises(AnalysisError, match="Invalid publication cache"):
        cache.load("graphs", key, "SinglePublicationProtocolGraph")
    path.write_text("different")
    with pytest.raises(AnalysisError, match="Conflicting publication cache"):
        cache.publish("graphs", key, value)
    with pytest.raises(AnalysisError, match="escapes root"):
        cache.load("../../../escape", A, "SinglePublicationProtocolGraph")

    race = PublicationCache(tmp_path / "race")
    real_link = cache_module.os.link
    def same(source, destination):
        real_link(source, destination); raise FileExistsError(destination)
    monkeypatch.setattr(cache_module.os, "link", same)
    assert race.publish("graphs", key, value).is_file()
    conflicting = PublicationCache(tmp_path / "conflicting-race")
    def conflict(source, destination):
        destination.write_text("different")
        raise FileExistsError(destination)
    monkeypatch.setattr(cache_module.os, "link", conflict)
    with pytest.raises(AnalysisError, match="Conflicting publication cache"):
        conflicting.publish("graphs", key, value)


def test_diagnostic_translation_does_not_enter_identity():
    first = diagnostic("code", "中文一", "English one", suggestion="建议", suggestion_en="Advice")
    second = diagnostic("code", "中文二", "English two", suggestion="另一个", suggestion_en="Other")
    assert first["code"] == second["code"]
    assert identity({"rule": first["code"]}) == identity({"rule": second["code"]})
