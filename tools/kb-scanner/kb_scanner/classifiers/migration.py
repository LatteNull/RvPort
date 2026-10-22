from __future__ import annotations

from collections import defaultdict

from ..core import (
    AnalysisSnapshot,
    Classification,
    ClassificationSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    Observation,
    ScanContext,
    StageResult,
    stable_id,
)
from .policy import DEFAULT_CLASSIFICATION_POLICY, ClassificationPolicy
from ..core.candidate_contract import invalid_candidate
from .semantic_admission import SemanticAdmissionIndex
from .risk import confirmed_dependency


class MigrationClassifier:
    __slots__ = ("_policy",)

    def __init__(self, policy: ClassificationPolicy = DEFAULT_CLASSIFICATION_POLICY) -> None:
        self._policy = policy

    def classify(
        self,
        context: ScanContext,
        detections: DetectionSnapshot,
        analysis: AnalysisSnapshot,
    ) -> StageResult[ClassificationSnapshot]:
        del context
        relation_by_id = {item.id: item for item in analysis.relations}
        proof_by_id = {item.id: item for item in analysis.proof_paths}
        proofs_by_relation = defaultdict(set)
        for proof in analysis.proof_paths:
            for rid in proof.relation_ids:
                proofs_by_relation[rid].add(proof.id)
        closed_terminals = {proof.relation_ids[-1] for proof in analysis.proof_paths
                            if proof.status == "complete" and not proof.truncated and proof.relation_ids}
        groups: dict[tuple[str, str, str, str], list[tuple[Observation, object, tuple[str, ...]]]] = defaultdict(list)
        rejected = []
        semantic_gate = SemanticAdmissionIndex(analysis)
        excluded = []
        for observation in detections.observations:
            if invalid_candidate(observation):
                rejected.append(observation.id)
                continue
            if any(rid not in relation_by_id for rid in observation.relation_ids):
                return _failed("classifier.invalid-relation-reference", "Observation references an unknown Relation")
            explicit_proofs = tuple(
                item for item in observation.metadata.get("proofPathIds", ()) if isinstance(item, str)
            )
            if any(pid not in proof_by_id for pid in explicit_proofs):
                return _failed("classifier.invalid-proof-reference", "Observation references an unknown ProofPath")
            admission = semantic_gate.decide(observation)
            if admission.status == "excluded":
                excluded.append({"observationId": observation.id, "reason": admission.reason, "relationIds": admission.relation_ids, "proofIds": admission.proof_ids})
                continue
            inferred_proofs = tuple(sorted({pid for rid in observation.relation_ids for pid in proofs_by_relation[rid]}))
            proof_ids = tuple(sorted(set((*explicit_proofs, *inferred_proofs))))
            proof_complete = bool(proof_ids) and all(proof_by_id[item].status == "complete" for item in proof_ids)
            linked_relations = tuple(relation_by_id[item] for item in observation.relation_ids)
            selected_reachable = any(
                item.status == "selected" and item.metadata.get("itemKind") == "source_x86_dependency"
                for item in linked_relations
            )
            inactive_reachable = bool(linked_relations) and any(
                item.status in {"inactive", "not_selected"} and item.metadata.get("itemKind") == "source_x86_dependency"
                for item in linked_relations
            )
            dependency_relations = tuple(item for item in linked_relations
                                         if item.metadata.get("itemKind") == "source_x86_dependency")
            if dependency_relations:
                # A closed target-to-dependency path is not invalidated by an
                # unrelated partial macro/include path attached for context.
                if selected_reachable:
                    proof_complete = any(item.status == "selected" and item.id in closed_terminals
                                         for item in dependency_relations)
                elif inactive_reachable:
                    proof_complete = all(item.status in {"inactive", "not_selected"} and item.id in closed_terminals
                                         for item in dependency_relations)
            relation_unknown = any(item.status == "unknown" for item in linked_relations) and not selected_reachable
            local_guards = tuple(item for item in linked_relations if item.kind == "guarded_by")
            if observation.metadata.get("branchRole") == "x86" and local_guards and all(
                    item.status == "complete" for item in local_guards):
                proof_complete = True
                # Unread system-header contents do not invalidate an already
                # closed architecture guard excluding that include directive.
                relation_unknown = False
            decision = self._policy.decide(
                observation,
                proof_complete=proof_complete,
                relation_unknown=relation_unknown,
                selected_reachable=selected_reachable,
                inactive_reachable=inactive_reachable,
            )
            has_alternative = bool(observation.metadata.get("compatibleSiblingBranch")) or any(
                item.kind == "alternative_to" and item.status == "complete" for item in linked_relations
            )
            alternative_complete = selected_reachable and not any(
                item.kind == "alternative_to" and item.status != "complete" for item in linked_relations
            )
            portability_gap = decision.impact == "blocking_issue" and alternative_complete and not has_alternative
            root = str(
                observation.metadata.get("rootCauseId")
                or observation.metadata.get("factId")
                or observation.metadata.get("subjectId")
                or observation.kind
            )
            configuration = str(observation.metadata.get("configuration", "default"))
            groups[(root, configuration, decision.impact, decision.reason)].append(
                (observation, decision, proof_ids, selected_reachable, has_alternative, alternative_complete, portability_gap)
            )

        classifications: list[Classification] = []
        for key in sorted(groups):
            root, configuration, impact, reason = key
            values = groups[key]
            observation_ids = tuple(item[0].id for item in values)
            evidence_ids = tuple(sorted({value for item, *_ in values for value in item.evidence_ids}))
            knowledge_ids = tuple(sorted({value for item, *_ in values for value in item.knowledge_ids}))
            relation_ids = tuple(sorted({value for item, *_ in values for value in item.relation_ids}))
            proof_ids = tuple(sorted({value for _, _, ids, *_ in values for value in ids}))
            confidence = _confidence(item[0].confidence for item in values)
            identity = stable_id("classification", self._policy.version, root, configuration, impact, reason)
            classifications.append(
                Classification(
                    identity,
                    self._policy.policy_id,
                    impact,
                    reason,
                    observation_ids,
                    evidence_ids,
                    knowledge_ids,
                    relation_ids,
                    proof_ids,
                    confidence,
                    {
                        "policyVersion": self._policy.version,
                        "semanticRoot": root,
                        "configuration": configuration,
                        "producerCount": len(values),
                        "selectedReachable": any(item[3] for item in values),
                        "hasCompatibleAlternative": any(item[4] for item in values),
                        "alternativeComplete": all(item[5] for item in values),
                        "portabilityGap": any(item[6] for item in values),
                        "enumCandidate": any(item[0].kind == "architecture_enum_candidate" for item in values),
                        "confirmedExecutionDependency": any(confirmed_dependency(item[0]) for item in values),
                        "selectionContext": next((str(item[0].metadata.get("selectionContext")) for item in values if item[0].metadata.get("selectionContext")), "unknown"),
                        "completeness": (
                            "unknown"
                            if impact == "unknown" or any(item[0].metadata.get("bindingStatus") in {"unknown", "ambiguous", "partial"} or item[0].metadata.get("templateDependent") is True for item in values)
                            else "partial" if impact == "actionable_non_blocking" and any(confirmed_dependency(item[0]) for item in values)
                            else "complete"
                        ),
                    },
                )
            )
        unknown = [item for item in classifications if item.metadata.get("completeness") != "complete"]
        status = CompletionStatus.PARTIAL if unknown else CompletionStatus.COMPLETE
        diagnostics = (
            (Diagnostic("classifier.invalid-candidate-admission", "classifier", DiagnosticSeverity.INFO,
                        "Ineligible architecture candidates were rejected before classification",
                        producer="migration-classifier", details={"observationIds": tuple(sorted(rejected))}),)
            if rejected else ()
        )
        if unknown:
            diagnostics += (
                Diagnostic(
                    "classifier.unknown-results",
                    "classifier",
                    DiagnosticSeverity.WARNING,
                    "Some observations cannot be classified with complete static proof",
                    producer="migration-classifier",
                    details={"reason": "classification-input-incomplete", "count": len(unknown)},
                ),
            )
        if excluded:
            diagnostics += (Diagnostic("classifier.candidate-semantic-exclusions", "classifier", DiagnosticSeverity.INFO,
                "Candidate migration conclusions excluded by complete occurrence-role proof; facts and observations retained",
                producer="migration-classifier", details={"count": len(excluded), "exclusions": tuple(sorted(excluded, key=lambda item: item["observationId"]))}),)
        snapshot = ClassificationSnapshot(
            observations=tuple(item for item in detections.observations if item.id not in rejected),
            classifications=tuple(sorted(classifications, key=lambda item: (item.impact, item.reason, item.id))),
        )
        return StageResult(snapshot, status, diagnostics)


def _confidence(values) -> str:
    ordered = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    return min(values, key=lambda value: ordered.get(value, 0), default="unknown")


def _failed(code: str, message: str) -> StageResult[ClassificationSnapshot]:
    diagnostic = Diagnostic(code, "classifier", DiagnosticSeverity.ERROR, message, producer="migration-classifier", affects_exit_code=True)
    return StageResult(None, CompletionStatus.FAILED, (diagnostic,))
