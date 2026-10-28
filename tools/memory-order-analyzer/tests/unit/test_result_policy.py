"""结果准入正负对照与诊断身份单元测试。"""

from memory_order_analyzer.result_policy import admit_candidates, adapt_diagnostics, merge_diagnostics, stage_applicability, evidence_complete, bound_diagnostics


def test_diagnostic_budget_retains_explicit_gap_and_full_artifact_reference():
    values = adapt_diagnostics([{"code": "a"}, {"code": "b"}, {"code": "c"}])
    assert bound_diagnostics(values, 3, "all.json") == values
    bounded = bound_diagnostics(values, 2, "all.json")
    assert len(bounded) == 2 and bounded[0] == values[0]
    assert bounded[1]["code"] == "diagnostic-budget-exhausted"
    assert bounded[1]["references"] == ["all.json"]
    assert len(bound_diagnostics(values, 1, "all.json")) == 1
    assert len(values) == 3


def test_evidence_files_do_not_imply_complete_evidence():
    assert not evidence_complete([])
    assert not evidence_complete([{}])
    assert not evidence_complete([{"status": "partial"}])
    assert not evidence_complete([{"status": "complete", "frontier": [{"code": "gap"}]}])
    assert not evidence_complete([{"status": "complete"}, {"status": "unknown"}])
    assert evidence_complete([{"status": "complete", "frontier": []}, {"status": "complete"}])


def test_stage_absence_requires_complete_source_evidence():
    records = [{"record_id": "tu", "language": "c++"}]
    assert stage_applicability("other", records, {}) is None
    assert stage_applicability("cpp-thread-lifecycle", [{"language": "c"}], {}) is False
    assert stage_applicability("advanced-atomic", records, {}) is None
    assert stage_applicability("advanced-atomic", records, {"tu": {"status": "partial"}}) is None
    assert stage_applicability("advanced-atomic", records, {"tu": {"status": "complete", "nodes": []}}) is False
    assert stage_applicability("cpp-thread-lifecycle", records, {"tu": {"status": "complete", "name": "std::thread"}}) is True


def candidate(identifier, shape, nodes, profile="p", tu="tu"):
    return {"id": identifier, "scope_id": "scope", "shape": shape, "node_ids": nodes,
            "relation_ids": [identifier], "physical_tu_ids": [tu], "profile_ids": [profile]}


def test_ordinary_vector_and_loop_do_not_become_findings():
    values = [candidate("read", "memory-access", ["local"]), candidate("loop", "control", ["local"])]
    admitted, audit = admit_candidates(values)
    assert admitted == []
    assert (audit["raw"], audit["admitted"], audit["excluded"]) == (2, 0, 2)
    assert {item["reason"] for item in audit["decisions"]} == {"no-concurrency-anchor"}


def test_concurrency_anchors_are_local_to_profile_and_tu():
    values = [candidate("atomic", "atomic", ["object"]),
              candidate("access", "memory-access", ["object"]),
              candidate("other-profile", "memory-access", ["object"], profile="q"),
              candidate("other-tu", "memory-access", ["object"], tu="other"),
              {**candidate("other-scope", "memory-access", ["object"]), "scope_id": "other"},
              candidate("wrapper", "unknown-sync-wrapper", ["lock"]),
              candidate("thread", "pthread-create", ["callback"]),
              candidate("raii", "unknown-raii", ["guard"])]
    admitted, audit = admit_candidates(values)
    assert {item["id"] for item in admitted} == {"atomic", "access", "wrapper", "thread", "raii"}
    assert audit["excluded"] == 3
    assert admit_candidates([])[1]["raw"] == 0


def test_duplicate_identity_preserves_distinct_relations():
    value = candidate("a", "pthread-mutex", ["object"])
    admitted, audit = admit_candidates([value, {**value, "id": "copy"}, candidate("b", "pthread-mutex", ["object"])])
    assert [item["id"] for item in admitted] == ["a", "b"]
    assert audit["decisions"][-1]["reason"] == "duplicate-identity"


def test_diagnostics_merge_root_but_preserve_scope_and_tu():
    root = {"code": "facts_partial", "detail": "事实不完整", "detail_en": "Partial facts", "record_id": "r"}
    items = adapt_diagnostics([root], stage="ingest", scope_id="a")
    items += adapt_diagnostics([root], stage="downstream", scope_id="a")
    items += adapt_diagnostics([{**root, "record_id": "other"}], stage="ingest", scope_id="a")
    items += adapt_diagnostics([root], stage="ingest", scope_id="b")
    merged = merge_diagnostics(items)
    assert len(merged) == 3
    joined = next(item for item in merged if item["scope_id"] == "a" and "r" in item["references"])
    assert set(joined["references"]) == {"r", "stage:ingest", "stage:downstream"}
    assert "stage:ingest" not in items[0]["references"]
    assert merge_diagnostics(merged) == merged


def test_diagnostic_defaults_and_source_identity():
    items = adapt_diagnostics([{}, {"source": {"physical_tu_id": "tu", "artifact_key": "artifact"}},
                              {"source": "legacy", "stage": "source", "scope_id": "scope", "relevant": False}])
    assert items[0]["suggestion"] and items[0]["suggestion_en"]
    assert items[1]["references"] == ["artifact", "tu"]
    assert items[2]["stage"] == "source" and not items[2]["relevant"]
    assert len(merge_diagnostics(items)) == 3
