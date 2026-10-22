from __future__ import annotations

from collections import defaultdict

from ..core import (
    AnalysisSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    Observation,
    Relation,
    ScanContext,
    StageResult,
    stable_id,
)


class TestSelectionDetector:
    __slots__ = ()

    def detect(
        self,
        context: ScanContext,
        facts: NormalizedSnapshot,
        analysis: AnalysisSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> StageResult[DetectionSnapshot]:
        del context
        evidence_ids = {item.id for item in facts.evidence}
        entity_ids = {item.id for item in analysis.entities}
        relation_ids = {item.id for item in analysis.relations}
        knowledge_ids = {item.id for item in knowledge.entries}
        for relation in analysis.relations:
            if relation.source_id not in entity_ids or relation.target_id not in entity_ids or not set(relation.evidence_ids).issubset(evidence_ids):
                return _failed("test-detector.invalid-relation-reference", "Test relation references unknown Entity or Evidence")
        for proof in analysis.proof_paths:
            if proof.source_id not in entity_ids or proof.target_id not in entity_ids or not set(proof.relation_ids).issubset(relation_ids):
                return _failed("test-detector.invalid-proof-reference", "Test proof references unknown Entity or Relation")

        entities = {item.id: item for item in analysis.entities}
        observations: dict[str, Observation] = {}
        target_proofs = defaultdict(list)
        for proof in analysis.proof_paths:
            target_proofs[proof.target_id].append(proof)
        proofs_by_target = {target: tuple(sorted(item.id for item in proofs))
            for target, proofs in target_proofs.items()}
        for relation in analysis.relations:
            target = entities[relation.target_id]
            if relation.kind == "selects_test" and target.kind == "test_candidate":
                _add(observations, "test_selection_unknown", relation, (), (), "candidate-role", "candidate", "medium")
                continue
            if relation.kind != "exercises":
                continue
            referenced_knowledge = tuple(
                sorted(item for item in relation.metadata.get("knowledgeIds", ()) if isinstance(item, str))
            )
            if not set(referenced_knowledge).issubset(knowledge_ids):
                return _failed("test-detector.invalid-knowledge-reference", "Test relation references unknown KnowledgeEntry")
            related_proofs = proofs_by_target.get(relation.target_id, ())
            supporting = [item for item in target_proofs[relation.target_id] if relation.id in item.relation_ids]
            complete = bool(supporting) and all(item.status == "complete" and not item.truncated for item in supporting)
            if relation.status == "unknown" or not complete:
                _add(observations, "test_selection_unknown", relation, referenced_knowledge, related_proofs, "selection-proof-incomplete", "candidate", "medium")
            elif referenced_knowledge and relation.status == "selected":
                _add(observations, "riscv_test_blocker", relation, referenced_knowledge, related_proofs, "selected-x86-test-dependency", "confirmed_local", "high")
            elif referenced_knowledge and relation.status in {"inactive", "not_selected"}:
                _add(observations, "x86_test_guarded", relation, referenced_knowledge, related_proofs, "x86-test-path-excluded", "confirmed_local", "high")
            elif relation.metadata.get("x86Candidate"):
                _add(observations, "test_selection_unknown", relation, (), related_proofs, "x86-shaped-test-dependency-without-knowledge", "candidate", "medium")

        coverage_relations = [item for item in analysis.relations if item.kind == "covers_candidate" and item.status == "selected"]
        confirmed_test_scope = [
            item for item in analysis.relations
            if item.kind == "selects_test" and entities[item.target_id].kind == "test_target" and item.status in {"selected", "inactive", "not_selected"}
        ]
        for implementation in analysis.entities:
            if implementation.properties.get("coverageRequired") is not True:
                continue
            covered = any(item.target_id == implementation.id for item in coverage_relations)
            if covered:
                continue
            complete_inventory = implementation.properties.get("testInventoryComplete") is True
            evidence = tuple(
                sorted({evidence for item in analysis.relations if item.target_id == implementation.id for evidence in item.evidence_ids})
            )
            representative = confirmed_test_scope[0] if confirmed_test_scope else _coverage_relation(implementation.id, evidence, "unknown")
            if complete_inventory and confirmed_test_scope:
                _add(observations, "riscv_test_coverage_gap", representative, (), (), "complete-inventory-without-explicit-coverage", "confirmed_local", "high", implementation.id)
            else:
                _add(observations, "test_selection_unknown", representative, (), (), "test-inventory-incomplete", "candidate", "medium", implementation.id)

        status = CompletionStatus.PARTIAL if any(item.kind == "test_selection_unknown" for item in observations.values()) else CompletionStatus.COMPLETE
        diagnostics = ()
        if status is CompletionStatus.PARTIAL:
            diagnostics = (
                Diagnostic(
                    "test-detector.partial",
                    "detector.test-selection",
                    DiagnosticSeverity.WARNING,
                    "Some test roles, selections, or coverage relations remain unknown",
                    producer="test-selection-detector",
                    details={"reason": "test-selection-incomplete"},
                ),
            )
        return StageResult(
            DetectionSnapshot(tuple(sorted(observations.values(), key=lambda item: (item.kind, item.id)))),
            status,
            diagnostics,
        )


def _coverage_relation(target_id: str, evidence_ids: tuple[str, ...], status: str) -> Relation:
    source_id = stable_id("coverage_gap_source", 1, target_id)
    return Relation(
        stable_id("relation", 1, "coverage_gap", source_id, target_id, evidence_ids, status),
        "coverage_gap",
        source_id,
        target_id,
        evidence_ids,
        "high" if status == "selected" else "medium",
        status,
        {"basis": "coverage-requirement", "synthetic": True},
    )


def _add(
    output: dict[str, Observation],
    kind: str,
    relation: Relation,
    knowledge_ids: tuple[str, ...],
    proof_ids: tuple[str, ...],
    reason: str,
    status: str,
    confidence: str,
    root_id: str | None = None,
) -> None:
    semantic_root = root_id or relation.target_id
    observation_id = stable_id("observation", 1, "TEST.SELECTION", kind, semantic_root, relation.id, knowledge_ids, proof_ids, reason)
    output[observation_id] = Observation(
        observation_id,
        "TEST.SELECTION",
        kind,
        relation.evidence_ids,
        () if relation.metadata.get("synthetic") else (relation.id,),
        confidence,
        status,
        {
            "basis": "test-selection-proof",
            "selectionStatus": relation.status,
            "reason": reason,
            "proofPathIds": proof_ids,
            "configuration": relation.metadata.get("configuration", "default"),
            "rootCauseId": semantic_root,
        },
        knowledge_ids,
    )


def _failed(code: str, message: str) -> StageResult[DetectionSnapshot]:
    diagnostic = Diagnostic(code, "detector.test-selection", DiagnosticSeverity.ERROR, message, producer="test-selection-detector", affects_exit_code=True)
    return StageResult(None, CompletionStatus.FAILED, (diagnostic,))
