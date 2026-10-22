from copy import deepcopy

from memory_order_analyzer.contracts import identity
from memory_order_analyzer.degraded_analysis import (
    adapt_formal_assessments, bounded_slice, build_availability, build_report,
    build_synchronization_gaps, evidence_mode, generate_source_candidates,
    request_mode, source_facts_usable,
)
from memory_order_analyzer.degraded_contracts import dependency, failure_record, stage_counts


def source_request(language="c", standard="c17"):
    return {"physical_tu_id": "tu", "profile": {"profile_id": "a" * 64,
            "language": language, "standard": standard}}


def node(identifier, name="", kind="call-expression"):
    return {"id": identifier, "kind": kind, "name": name, "qualified_name": name,
            "canonical_type": "int"}


def facts(relations, *, status="complete", diagnostics=()):
    nodes = [node("call"), node("pthread_create", "pthread_create", "function"),
             node("mutex", "std::lock_guard<int>", "function"), node("flag", "flag", "variable")]
    return {"kind": "SourceSemanticFacts", "physical_tu_id": "tu", "profile_id": "a" * 64,
            "status": status, "nodes": nodes, "relations": relations,
            "diagnostics": list(diagnostics), "frontier": []}


def relation(identifier, kind, target="flag", status="exact"):
    return {"id": identifier, "kind": kind, "from": "call", "to": target,
            "status": status, "reason": None}


def availability(mode="ast-only", language="c", standard="c17"):
    value = build_availability("scope", source_request(language, standard),
                               facts([]) if mode in {"ast-only", "ast-ir"} else None,
                               [{"artifact_key": "artifact"}] if mode in {"ir-only", "ast-ir"} else [],
                               [], [])
    assert value["mode"] == mode
    return value


def test_source_trust_modes_and_request_mode():
    assert source_facts_usable(facts([]))
    assert source_facts_usable(facts([], status="partial", diagnostics=[{"code": "source-budget-exhausted"}]))
    assert not source_facts_usable(None)
    assert not source_facts_usable(facts([], status="failed"))
    assert not source_facts_usable(facts([], status="partial", diagnostics=[{"code": "clang-replay-failed"}]))
    assert not source_facts_usable(facts([], diagnostics=[{"code": "fatal-anything"}]))
    assert evidence_mode(facts([]), True) == "ast-ir"
    assert evidence_mode(None, True) == "ir-only"
    assert evidence_mode(facts([]), False) == "ast-only"
    assert evidence_mode(None, False) == "failed"
    assert request_mode(["ast-ir"]) == "ast-ir"
    assert request_mode(["ast-ir", "ir-only"]) == "mixed"


def test_availability_preserves_products_and_failures():
    module = {"kind": "ModuleFacts", "id": "artifact", "digest": "b" * 64}
    failure = failure_record("tu", "p2", "p2_failed", "boom")
    value = build_availability("scope", source_request(), facts([]), [{"artifact_key": "artifact"}],
                               [module], [failure])
    assert value["mode"] == "ast-ir" and value["status"] == "partial"
    assert {item["stage"]: item["status"] for item in value["products"]} == {
        "bc": "complete", "p1": "complete", "p2": "failed", "p3": "not-run",
        "p4": "not-run", "source": "complete"}


def test_source_candidates_cover_c_shapes_and_never_promote_source_order():
    values = [relation("r1", "pthread_create", "pthread_create"), relation("r2", "pthread_join", "pthread_create"),
              relation("r3", "pthread_mutex_lock", "flag"), relation("r4", "atomic", "flag"),
              relation("r5", "read", "flag"), relation("r6", "control", None),
              relation("r7", "sequenced-before", "flag")]
    candidates, cut = generate_source_candidates("scope", facts(values), availability(), limit=20)
    assert not cut
    assert {item["shape"] for item in candidates} == {
        "pthread-create", "pthread-join", "pthread-mutex", "atomic", "memory-access", "control"}
    assert all(item["verdict"] == "unknown" and item["safety"] == "not-established" for item in candidates)
    assert all("happens-before" in item["missing_evidence"] for item in candidates)
    assert not any(item["shape"] == "sequenced-before" for item in candidates)
    limited, cut = generate_source_candidates("scope", facts(values), availability(), limit=1)
    assert len(limited) == 1 and cut
    assert generate_source_candidates("scope", facts(values, status="failed"), availability(), limit=10) == ([], False)
    uncertain = [relation("callback", "pthread_create", None, status="unknown"),
                 relation("object", "atomic", None)]
    candidates, _ = generate_source_candidates("scope", facts(uncertain), availability("ast-ir"), limit=10)
    assert "callback-target" in candidates[0]["missing_evidence"] or "callback-target" in candidates[1]["missing_evidence"]
    assert any("object-identity" in item["missing_evidence"] for item in candidates)


def test_cpp_raii_and_wrapper_create_gaps_but_direct_pthread_does_not():
    values = [relation("r1", "call", "mutex"), relation("r2", "call", "flag"),
              relation("r3", "pthread_mutex_lock", "flag")]
    candidates, _ = generate_source_candidates("scope", facts(values), availability(language="c++", standard="c++17"), limit=10)
    assert "unknown-raii" in {item["shape"] for item in candidates}
    gaps = build_synchronization_gaps("scope", candidates, None, {})
    assert {item["reason"] for item in gaps} == {"unmodeled-raii-lifetime"}
    direct = [item for item in candidates if item["shape"] == "pthread-mutex"]
    assert build_synchronization_gaps("scope", direct, None, {}) == []

    graph = {"diagnostics": [
        {"code": "mutex-kind-unknown", "source": {"artifact_key": "artifact"}, "instance": "thread"},
        {"code": "mutex-state-unknown", "source": {}, "instance": None},
        {"code": "thread-graph-budget", "source": None, "instance": None},
        {"code": "irrelevant", "source": None, "instance": None}], "frontier": []}
    gaps = build_synchronization_gaps("scope", [], graph, {"artifact": "tu"})
    assert {item["reason"] for item in gaps} == {
        "mutex-kind-unknown", "unbalanced-or-conditional-lock", "synchronization-budget"}
    node_only = facts([])
    node_only["nodes"].append(node("guard", "", "variable"))
    node_only["nodes"][-1]["canonical_type"] = "std::lock_guard<std::mutex>"
    candidates, _ = generate_source_candidates(
        "scope", node_only, availability(language="c++", standard="c++20"), limit=10)
    assert candidates and {item["shape"] for item in candidates} == {"unknown-raii"}


def test_bounded_slice_cycles_duplicates_and_budget():
    edges = {"a": ["b", "b"], "b": ["a", "c"]}
    assert bounded_slice(["a"], edges, 10) == {
        "roots": ["a"], "items": ["a", "b", "c"], "status": "complete", "missing": []}
    cut = bounded_slice(["a"], edges, 1)
    assert cut["status"] == "partial" and cut["missing"] == ["slice-budget"]
    assert bounded_slice([], {}, 1)["items"] == []
    assert bounded_slice(["a", "a"], {"a": ["a"]}, 2)["items"] == ["a"]


def test_formal_adapter_degrades_relevant_and_unmapped_but_preserves_unrelated():
    assessment = {"id": "risk", "kind": "potential-data-race", "status": "finding",
                  "detail": "risk", "detail_en": "risk", "evidence": [{"artifact_key": "a"}]}
    complete = availability("ast-ir")
    complete["physical_tu_id"] = "tu-a"
    degraded = availability("ast-only")
    degraded["physical_tu_id"] = "tu-b"
    gap = {"id": "g" * 64, "physical_tu_ids": ["tu-b"]}
    kept = adapt_formal_assessments([assessment], [complete, degraded], [gap], {"a": "tu-a"}, slice_limit=10)
    assert kept[0]["effective_status"] == "finding"
    relevant = deepcopy(gap); relevant["physical_tu_ids"] = ["tu-a"]
    changed = adapt_formal_assessments([assessment], [complete, degraded], [relevant], {"a": "tu-a"}, slice_limit=10)
    assert changed[0]["effective_status"] == "unknown"
    assert changed[0]["reason_codes"] == ["candidate-relevant-synchronization-gap"]
    unmapped = deepcopy(assessment); unmapped["evidence"] = []
    assert adapt_formal_assessments([unmapped], [complete, degraded], [], {}, slice_limit=1)[0]["effective_status"] == "unknown"
    degraded_assessment = adapt_formal_assessments([assessment], [degraded], [], {"a": "tu-b"}, slice_limit=10)
    assert degraded_assessment[0]["reason_codes"] == ["candidate-depends-on-degraded-tu"]
    unsupported = deepcopy(assessment); unsupported["status"] = "unsupported"
    assert adapt_formal_assessments([unsupported], [complete], [relevant], {"a": "tu-a"}, slice_limit=10)[0]["effective_status"] == "unsupported"
    lifecycle = {"id": "l" * 64, "physical_tu_ids": ["tu-a"],
                 "object_ids": ["thread-object"], "thread_ids": ["thread-instance"],
                 "path_ids": ["normal-path"]}
    changed = adapt_formal_assessments(
        [assessment], [complete], [], {"a": "tu-a"}, slice_limit=10,
        lifecycle_gaps=[lifecycle])
    assert changed[0]["effective_status"] == "unknown"
    assert changed[0]["reason_codes"] == ["candidate-relevant-cpp-thread-lifecycle-gap"]
    unrelated = deepcopy(lifecycle); unrelated["physical_tu_ids"] = ["tu-z"]
    kept = adapt_formal_assessments(
        [assessment], [complete], [], {"a": "tu-a"}, slice_limit=10,
        lifecycle_gaps=[unrelated])
    assert kept[0]["effective_status"] == "finding"


def test_report_exit_precedence_and_separate_denominators():
    request = {"scope": "scope"}
    stages = {name: stage_counts(0) for name in ("source", "bc", "p1", "p2", "p3", "p4")}
    complete = availability("ast-ir")
    finding = adapt_formal_assessments(
        [{"id": "risk", "kind": "risk", "status": "finding", "evidence": [], "detail": "x", "detail_en": "x"}],
        [complete], [], {}, slice_limit=10)
    risk = build_report("scope", request, [complete], [], [], finding, [], stages, [])
    assert risk["status"] == "complete" and risk["exit_code"] == 3
    source_only, _ = generate_source_candidates("scope", facts([relation("r", "atomic")]), availability(), limit=2)
    partial = build_report("scope", request, [availability()], source_only, [], [], [], stages, [])
    assert partial["exit_code"] == 2 and not partial["formal_assessments"]
    failed = build_report("scope", request, [availability("failed")], [], [], [], [], stages, [])
    assert failed["exit_code"] == 1
