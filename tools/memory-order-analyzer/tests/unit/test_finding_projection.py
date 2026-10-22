from copy import deepcopy
import json

import pytest

import memory_order_analyzer.finding_contracts as finding_contracts
from memory_order_analyzer.contracts import AnalysisError
from memory_order_analyzer.finding_contracts import (
    finding_digest, provenance, read_finding, validate_finding,
)
from memory_order_analyzer.finding_projection import (
    EvidenceChainBuilder, project_assessment, project_pipeline_assessment,
    project_source_candidate,
)


def prov():
    return [provenance("UnitFact", "fact", "org.rvport.memory-order-analyzer.unit", 1, "a" * 64)]


def formal():
    builder = EvidenceChainBuilder(max_depth=8, max_visited=8, max_paths=2)
    root = builder.step("thread-creation", "线程创建", "Thread creation", prov())
    access = builder.step("memory-access", "内存访问", "Memory access", prov())
    conclusion = builder.step("conclusion", "风险结论", "Risk conclusion", prov())
    builder.edge(root, access, "reaches", prov())
    builder.edge(access, conclusion, "supports", prov())
    chain = builder.build(root, [root, access, conclusion], impacts=[access])
    return project_assessment("scope", {"id": "risk", "reason": "relaxed publication"}, prov(),
                              category="formal", chain=chain)


def test_formal_projection_round_trip_and_bilingual_fields(tmp_path):
    value = formal()
    assert value["conclusion"]["verdict"] == "risk"
    assert value["conclusion"]["title"] and value["conclusion"]["title_en"]
    assert value["semanticDigest"] == finding_digest(value)
    path = tmp_path / "finding.json"; path.write_text(json.dumps(value), encoding="utf-8")
    assert read_finding(path) == value
    with pytest.raises(AnalysisError, match="Invalid or missing"):
        read_finding(tmp_path / "missing")


def test_source_candidate_requires_break_and_cannot_be_promoted():
    value = project_assessment("scope", {"id": "source", "reason": "candidate"}, prov(),
                               category="source")
    assert value["evidenceChain"]["breaks"] and value["conclusion"]["status"] == "unknown"
    invalid = deepcopy(value); invalid["conclusion"]["verdict"] = "risk"
    invalid["semanticDigest"] = finding_digest(invalid)
    with pytest.raises(AnalysisError, match="AST-only"):
        validate_finding(invalid)
    with pytest.raises(AnalysisError, match="Unknown projection"):
        project_assessment("scope", {}, prov(), category="other")


def test_discharged_and_inconclusive_have_bounded_vocabulary():
    discharged = project_assessment("scope", {"id": "ok"}, prov(), category="discharged")
    assert discharged["conclusion"]["verdict"] == "discharged-within-bounded-model"
    unknown = project_assessment("scope", {"id": "maybe"}, prov(), category="inconclusive")
    assert unknown["conclusion"]["verdict"] == "inconclusive" and unknown["evidenceChain"]["breaks"]


def test_builder_rejects_edges_and_adds_budget_break():
    with pytest.raises(AnalysisError, match="positive"):
        EvidenceChainBuilder(max_depth=0)
    builder = EvidenceChainBuilder(max_depth=1, max_visited=1, max_paths=1)
    root = builder.step("execution-root", "入口", "Root", prov())
    child = builder.step("memory-access", "访问", "Access", prov())
    builder.edge(root, child, "reaches", prov())
    with pytest.raises(AnalysisError, match="endpoints"):
        builder.edge("missing", child, "reaches", prov())
    chain = builder.build(root, [root, child])
    assert chain["budget"]["truncated"] and chain["breaks"]


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(primaryOccurrenceId="missing"),
    lambda value: value["evidenceChain"].update(rootStepId="missing"),
    lambda value: value["evidenceChain"]["edges"][0].update(toStepId="missing"),
    lambda value: value["evidenceChain"].update(primaryPath=list(reversed(value["evidenceChain"]["primaryPath"]))),
    lambda value: value["occurrences"][0].update(scopeId="other"),
    lambda value: value["fact"]["provenance"][0].update(producer="foreign.tool"),
    lambda value: value["conclusion"].update(status="unknown"),
])
def test_reference_scope_provenance_and_status_validation(mutation):
    value = formal(); mutation(value); value["semanticDigest"] = finding_digest(value)
    with pytest.raises(AnalysisError):
        validate_finding(value)


def test_context_semantics_are_validated():
    value = formal()
    source = {"file": "src/a.c", "span": {"start": {"line": 1, "column": 1},
              "end": {"line": 1, "column": 2}}, "sourceSha256": "b" * 64, "snapshot": None,
              "context": {"status": "complete", "reasonCodes": [], "lines": [{"line": 1, "text": "x"}],
                          "highlights": [{"line": 1, "startColumn": 1, "endColumn": 2}],
                          "budget": {"beforeLines": 20, "afterLines": 20, "maxLines": 256,
                                     "maxCharacters": 65536, "truncated": False}}}
    value["fact"]["primaryLocation"] = source
    value["occurrences"][0]["location"] = source
    value["evidenceChain"]["steps"][0]["source"] = source
    value["semanticDigest"] = finding_digest(value)
    assert validate_finding(value) == value
    for update in (
        lambda item: item["span"]["end"].update(column=1),
        lambda item: item["context"].update(reasonCodes=["bad"]),
        lambda item: item["context"]["highlights"][0].update(line=2),
        lambda item: item.update(file="../a.c"),
    ):
        broken = deepcopy(value); update(broken["fact"]["primaryLocation"])
        broken["semanticDigest"] = finding_digest(broken)
        with pytest.raises(AnalysisError):
            validate_finding(broken)


def test_pipeline_projection_builds_complete_and_missing_layer_chains():
    layers = {name: {"kind": name, "id": name} for name in
              ("thread_creation", "callback", "root", "call_path", "thread_instance", "mhp",
               "access", "object", "byte_range", "synchronization")}
    value = project_pipeline_assessment("scope", {"id": "risk"}, prov(),
                                        category="formal", layers=layers)
    assert value["conclusion"]["verdict"] == "risk"
    assert value["evidenceChain"]["status"] == "complete"
    assert len(value["evidenceChain"]["primaryPath"]) == len(layers) + 1
    atomic = {**layers, "atomic": {}, "reads_from": {}, "modification_order": {},
              "release_sequence": {}}
    discharged = project_pipeline_assessment("scope", {"id": "ok"}, prov(),
                                              category="discharged", layers=atomic, atomic=True)
    assert discharged["conclusion"]["verdict"] == "discharged-within-bounded-model"
    incomplete = project_pipeline_assessment("scope", {"id": "broken"}, prov(),
                                              category="formal", layers={"root": {}})
    assert incomplete["conclusion"]["verdict"] == "inconclusive"
    assert incomplete["evidenceChain"]["breaks"]


def test_source_candidate_projects_ast_step_context_and_all_missing_proofs():
    location = {"file": "src/a.c", "span": {"start": {"line": 1, "column": 1},
                "end": {"line": 1, "column": 2}}, "sourceSha256": "b" * 64,
                "snapshot": {"kind": "SourceSnapshot", "id": "b" * 64},
                "context": {"status": "complete", "reasonCodes": [],
                            "lines": [{"line": 1, "text": "x"}],
                            "highlights": [{"line": 1, "startColumn": 1, "endColumn": 2}],
                            "budget": {"beforeLines": 20, "afterLines": 20, "maxLines": 256,
                                       "maxCharacters": 65536, "truncated": False}}}
    candidate = {"id": "candidate", "shape": "atomic", "node_ids": ["n"],
                 "relation_ids": ["r"], "missing_evidence": ["reads-from", "happens-before"],
                 "reason": "source only", "physical_tu_id": "tu"}
    value = project_source_candidate("scope", candidate, prov(), location=location)
    assert value["conclusion"]["verdict"] == "source-candidate"
    assert value["fact"]["primaryLocation"] == location
    assert {item["reasonCode"] for item in value["evidenceChain"]["breaks"]} == {
        "missing-happens-before", "missing-reads-from"}
    missing = project_source_candidate("scope", {**candidate, "id": "no-location",
                                                  "missing_evidence": []}, prov())
    assert "source-location-unavailable" in {item["reasonCode"] for item in missing["evidenceChain"]["breaks"]}


def test_finding_contract_rejects_source_and_graph_budget_edge_cases(tmp_path, monkeypatch):
    value = formal()
    source = {"file": "src/a.c", "span": {"start": {"line": 1, "column": 1},
              "end": {"line": 1, "column": 2}}, "sourceSha256": "b" * 64, "snapshot": None,
              "context": {"status": "partial", "reasonCodes": ["cut"],
                          "lines": [{"line": 1, "text": "xy"}],
                          "highlights": [{"line": 1, "startColumn": 1, "endColumn": 2}],
                          "budget": {"beforeLines": 0, "afterLines": 0, "maxLines": 2,
                                     "maxCharacters": 2, "truncated": True}}}
    value["fact"]["primaryLocation"] = source
    value["occurrences"][0]["location"] = source
    value["semanticDigest"] = finding_digest(value)
    assert validate_finding(value)
    mutations = (
        lambda item: item["context"]["lines"].append({"line": 1, "text": "z"}),
        lambda item: item["context"]["budget"].update(maxCharacters=1),
        lambda item: item["context"].update(status="complete"),
        lambda item: item["context"].update(reasonCodes=[]),
        lambda item: item["context"].update(status="unavailable"),
    )
    for mutate in mutations:
        broken = deepcopy(value); mutate(broken["fact"]["primaryLocation"])
        broken["semanticDigest"] = finding_digest(broken)
        with pytest.raises(AnalysisError):
            validate_finding(broken)
    graph_mutations = (
        lambda item: item["evidenceChain"]["breaks"].append({
            "id": "break", "status": "unknown", "reasonCode": "x", "stage": "x",
            "fromStepId": "missing", "candidateStepIds": [], "expectedKind": None,
            "missingId": None, "detail": "x", "detail_en": "x", "suggestion": "x",
            "suggestion_en": "x"}),
        lambda item: item["evidenceChain"]["budget"].update(visited=99),
    )
    for mutate in graph_mutations:
        broken = formal(); mutate(broken); broken["semanticDigest"] = finding_digest(broken)
        with pytest.raises(AnalysisError):
            validate_finding(broken)
    monkeypatch.setattr(finding_contracts, "SCHEMA", tmp_path / "missing.json")
    with pytest.raises(AnalysisError, match="schema"):
        finding_contracts._schema()
