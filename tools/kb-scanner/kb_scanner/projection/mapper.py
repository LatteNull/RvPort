from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from ..core import (
    AnalysisSnapshot, AssessmentSnapshot, ClassificationSnapshot, DetectionSnapshot, Diagnostic,
    FrontendSnapshot, KnowledgeSnapshot, NormalizedSnapshot, ScanContext, WorkspaceSnapshot,
)
from ..core.metadata import to_json_compatible
from .contract import TOP_LEVEL_FIELDS, validate_payload
from .diagnostics import aggregate_diagnostics
from .policy import DEFAULT_PROJECTION_POLICY, ProjectionPolicy
from .reference import ReferenceClosureResolver, resolve_symbol


class ProjectionError(ValueError):
    pass


class CompatibilityMapper:
    __slots__ = ("_policy",)

    def __init__(self, policy: ProjectionPolicy = DEFAULT_PROJECTION_POLICY) -> None:
        self._policy = policy

    def map(
        self,
        context: ScanContext,
        workspace: WorkspaceSnapshot,
        knowledge: KnowledgeSnapshot,
        frontend: FrontendSnapshot,
        facts: NormalizedSnapshot,
        analysis: AnalysisSnapshot,
        detections: DetectionSnapshot,
        classifications: ClassificationSnapshot,
        assessments: AssessmentSnapshot,
        diagnostics: tuple[Diagnostic, ...],
    ) -> dict[str, Any]:
        del detections
        evidence = {item.id: item for item in (*frontend.evidence, *facts.evidence)}
        entities = {item.id: item for item in (*frontend.entities, *facts.entities, *analysis.entities)}
        entries = {item.id: item for item in knowledge.entries}
        sources = {item.id: item for item in knowledge.sources}
        relations = {item.id: item for item in analysis.relations}
        proofs = {item.id: item for item in analysis.proof_paths}
        observations = {item.id: item for item in classifications.observations}
        findings: list[dict[str, Any]] = []
        projection_diagnostics = aggregate_diagnostics(diagnostics)
        closure_resolver = ReferenceClosureResolver(evidence, entities, relations, proofs)
        for classification in sorted(classifications.classifications, key=lambda item: item.id):
            linked = [observations[item] for item in classification.observation_ids if item in observations]
            if len(linked) != len(classification.observation_ids) or not linked:
                raise ProjectionError("classification has missing or empty observation references")
            candidates = [evidence[item] for item in classification.evidence_ids if item in evidence]
            if not candidates:
                projection_diagnostics.append(f"projection: classification {classification.id} has no locatable evidence")
                continue
            observation = min(linked, key=lambda item: (item.detector_id, item.kind, item.id))
            primary = min(candidates, key=lambda item: _evidence_key(item, enum=observation.kind == "architecture_enum_candidate"))
            presentation = self._policy.present(observation, classification)
            fields = self._policy.fields(observation, classification)
            location = primary.location.start if primary.location else None
            subject = entities.get(primary.subject_id)
            file_name = str(context.input_root / location.path) if location else "<project>"
            line = location.line if location else 1
            column = location.column if location else None
            snippet = _snippet(primary.value)
            closure = closure_resolver.resolve(
                classification.evidence_ids,
                classification.relation_ids,
                classification.proof_path_ids,
            )
            missing_knowledge = tuple(sorted(item for item in classification.knowledge_ids if item not in entries))
            missing_references = tuple(sorted(set((*closure.missing_ids, *missing_knowledge))))
            closure_reasons = list(closure.reasons)
            if missing_knowledge and "missing-reference" not in closure_reasons:
                closure_reasons.append("missing-reference")
            if missing_references or closure.conflicting_ids or closure.truncated:
                projection_diagnostics.append(
                    "projection: partial reference closure | details="
                    + json.dumps(
                        {
                            "classificationId": classification.id,
                            "missingIds": missing_references,
                            "conflictingIds": closure.conflicting_ids,
                            "reasons": sorted(closure_reasons),
                            "truncated": closure.truncated,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            closed_evidence = [evidence[item] for item in closure.evidence_ids]
            occurrences = [_occurrence_trace(item) for item in sorted(candidates, key=_evidence_key)]
            trace = {
                "classificationIds": [classification.id],
                "observationIds": sorted(classification.observation_ids),
                "evidence": [_evidence_trace(item) for item in sorted(closed_evidence, key=lambda item: item.id)],
                "knowledge": [_knowledge_trace(entries[item], sources) for item in sorted(classification.knowledge_ids) if item in entries],
                "relations": [_relation_trace(relations[item], entities) for item in closure.relation_ids],
                "proofPaths": [_proof_trace(proofs[item]) for item in closure.proof_path_ids],
                "referenceClosure": {
                    "status": "partial" if missing_references else closure.status,
                    "missingIds": list(missing_references),
                    "conflictingIds": list(closure.conflicting_ids),
                    "reasons": sorted(closure_reasons),
                    "truncated": closure.truncated,
                },
                "primarySpan": _occurrence_span_trace(primary),
                "occurrenceCount": len(occurrences),
                "occurrences": occurrences,
                "policy": {"id": self._policy.policy_id, "version": self._policy.version},
            }
            linked_relations = tuple(relations[item] for item in closure.relation_ids)
            linked_entries = tuple(entries[item] for item in classification.knowledge_ids if item in entries)
            symbol = resolve_symbol(primary, linked_entries, linked_relations, entities)
            finding = {
                "id": classification.id,
                "rule_id": presentation.rule_id,
                "severity": fields["severity"],
                "confidence": classification.confidence,
                "title": presentation.title,
                "title_en": presentation.title_en,
                "file": file_name,
                "line": line,
                "column": column,
                "symbol": symbol or (subject.name if subject and subject.kind not in {"source_file", "project"} else None),
                "reason": presentation.reason,
                "reason_en": presentation.reason_en,
                "suggestion": presentation.suggestion,
                "suggestion_en": presentation.suggestion_en,
                "snippet": snippet,
                "scan_mode": context.scan_mode,
                "finding_type": fields["finding_type"],
                "source_kind": _source_kind(presentation.source_kind, primary),
                "is_actionable": fields["is_actionable"],
                "is_reference_source": True,
                "is_blocking": fields["is_blocking"],
                "arch_reachability": fields["arch_reachability"],
                "branch_group_id": observation.metadata.get("branchGroupId"),
                "branch_role": observation.metadata.get("branchRole") or observation.metadata.get("role"),
                "compatible_sibling_branch": bool(observation.metadata.get("compatibleSiblingBranch")),
                "compatible_branch_kind": observation.metadata.get("compatibleBranchKind"),
                "build_context": _build_context(observation, relations),
                "alternative_impl": _alternative(observation),
                "condition_macros": _condition_macros(observation),
                "trace": trace,
                "location": {"file": file_name, "line": line, "column": column},
                "context": {"snippet": snippet},
            }
            if finding["symbol"] is None and primary.kind == "include":
                finding["symbol"] = str(primary.value)
            findings.append(finding)
        findings.sort(key=lambda item: (item["file"], item["line"], item["column"] or 0, item["rule_id"], item["id"]))
        summary = _summary(findings, len(workspace.files))
        readiness = _readiness(assessments)
        if readiness is not None:
            summary["readiness"] = readiness
        payload = dict(zip(TOP_LEVEL_FIELDS, (
            "1.0",
            {"name": context.scanner_name, "version": context.scanner_version},
            {"id": context.rule_pack_id, "version": context.rule_pack_version},
            _project(context),
            summary,
            findings,
            projection_diagnostics,
        ), strict=True))
        validate_payload(payload)
        return payload


def _project(context: ScanContext) -> dict[str, Any]:
    compile_contexts = {
        str(item.path): {
            "includeDirs": list(item.include_dirs), "defines": [[key, value] for key, value in item.defines],
            "languageStandard": item.language_standard, "entryIndex": item.entry_index,
            "compiler": item.compiler, "tokenCount": len(item.tokens),
        }
        for item in context.compile_contexts
    }
    return {
        "root": str(context.input_root), "scanMode": context.scan_mode, "targetArch": context.target_arch,
        "includeInactiveBranches": context.include_inactive_branches,
        "compileCommands": str(context.compile_commands_path) if context.compile_commands_path else None,
        "compileContexts": compile_contexts,
    }


def _summary(findings: list[dict[str, Any]], files: int) -> dict[str, int]:
    severity: dict[str, int] = {}
    for finding in findings:
        severity[finding["severity"]] = severity.get(finding["severity"], 0) + 1
    hints = sum(item["finding_type"] == "hint" for item in findings)
    issues = len(findings) - hints
    refs = sum(not item["is_reference_source"] for item in findings if item["finding_type"] != "hint")
    result = {
        "files": files, "findings": len(findings), "issues": issues, "hints": hints,
        "blocking": sum(bool(item["is_blocking"]) for item in findings),
        "portabilityGaps": sum(item["finding_type"] == "portability_gap" for item in findings),
        "inactiveOrGuarded": sum(item["finding_type"] in {"inactive", "guarded"} for item in findings),
        "referenceSources": issues - refs, "references": refs,
    }
    result.update(severity)
    return result


def _readiness(assessments: AssessmentSnapshot) -> dict[str, Any] | None:
    projects = [item for item in assessments.assessments if item.kind == "project_migration_state"]
    if not projects:
        return None
    if len(projects) != 1:
        raise ProjectionError("assessment snapshot must contain exactly one project state")
    item = projects[0]
    metadata = to_json_compatible(item.metadata)
    return {
        "state": item.state,
        "confidence": item.confidence,
        "dimensions": metadata.get("dimensions", {}),
        "blockingDimensions": metadata.get("blockingDimensions", []),
        "completeness": metadata.get("completeness", {}),
        "staticScopeOnly": True,
        "compiled": False,
        "testsExecuted": False,
        "trace": {
            "assessmentId": item.id,
            "classificationIds": list(item.classification_ids),
            "observationIds": list(item.observation_ids),
            "evidenceIds": list(item.evidence_ids),
            "relationIds": list(item.relation_ids),
            "proofPathIds": list(item.proof_path_ids),
        },
    }


def _evidence_key(item, *, enum: bool = False) -> tuple[object, ...]:
    location = item.location.start if item.location else None
    priority = {"enum_member_reference": 0, "constexpr_condition": 1, "selection_condition": 1, "enum_member_declaration": 2, "enum_declaration": 3}.get(item.kind, 4) if enum else 0
    return (priority, location.path if location else "~", location.line if location else 2**31, location.column or 0 if location else 0, item.producer, item.id)


def _snippet(value: object) -> str:
    compatible = to_json_compatible(value)
    return compatible if isinstance(compatible, str) else json.dumps(compatible, ensure_ascii=False, sort_keys=True)


def _source_kind(default: str, evidence) -> str:
    if "compilation-database" in evidence.producer:
        return "compile_command"
    if evidence.kind.startswith("build_"):
        return "build"
    return default


def _build_context(observation, relations: Mapping[str, object]) -> dict[str, Any]:
    if observation.detector_id not in {"BUILD.SELECTION", "TEST.SELECTION"}:
        return {}
    linked = [relations[item] for item in observation.relation_ids if item in relations]
    return {
        "selectionStatus": observation.metadata.get("selectionStatus", "unknown"),
        "reason": observation.metadata.get("reason", ""),
        "relationIds": [item.id for item in linked],
    }


def _alternative(observation) -> dict[str, Any]:
    if not observation.metadata.get("compatibleSiblingBranch"):
        return {}
    return {
        "has_compatible_alternative": True,
        "matched_by": "evidence-graph",
        "matched_path": observation.metadata.get("compatibleBranchKind"),
    }


def _condition_macros(observation) -> list[str]:
    value = observation.metadata.get("conditionExpression")
    if not isinstance(value, str):
        return []
    ignored = {"defined", "if", "elif", "and", "or", "not"}
    return sorted({token for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", value) if token.lower() not in ignored})


def _evidence_trace(item) -> dict[str, Any]:
    return {"id": item.id, "kind": item.kind, "value": to_json_compatible(item.value), "producer": item.producer, "parseMode": item.parse_mode, "confidence": item.confidence, "location": _span_trace(item)}


def _span_trace(item) -> dict[str, Any] | None:
    if item.location is None:
        return None
    return {
        "file": item.location.start.path,
        "start": {"line": item.location.start.line, "column": item.location.start.column},
        "end": {"line": item.location.end.line, "column": item.location.end.column},
    }


def _occurrence_trace(item) -> dict[str, Any]:
    return {
        "evidenceId": item.id,
        "value": to_json_compatible(item.value),
        "span": _occurrence_span_trace(item),
        "configuration": item.metadata.get("configuration") or item.metadata.get("compilationContextId") or "default",
        "selectionStatus": item.metadata.get("selectionStatus", "unknown"),
        "completeness": "complete" if item.location is not None else "partial",
    }


def _occurrence_span_trace(item) -> dict[str, Any] | None:
    span = _span_trace(item)
    if (
        span is not None
        and item.kind == "call_expression"
        and isinstance(item.value, str)
        and item.location.start.line == item.location.end.line
    ):
        token_end = item.location.start.column + len(item.value)
        if token_end <= item.location.end.column:
            span["end"] = {"line": item.location.start.line, "column": token_end}
    return span


def _knowledge_trace(item, sources: Mapping[str, object]) -> dict[str, Any]:
    return {"id": item.id, "kind": item.fact_kind, "value": item.canonical_value, "sourceIds": list(item.source_ids), "producers": [sources[source].source_id for source in item.source_ids if source in sources]}


def _relation_trace(item, entities: Mapping[str, object]) -> dict[str, Any]:
    return {"id": item.id, "kind": item.kind, "source": entities[item.source_id].name if item.source_id in entities else item.source_id, "target": entities[item.target_id].name if item.target_id in entities else item.target_id, "status": item.status, "confidence": item.confidence, "evidenceIds": list(item.evidence_ids)}


def _proof_trace(item) -> dict[str, Any]:
    return {"id": item.id, "sourceId": item.source_id, "targetId": item.target_id, "relationIds": list(item.relation_ids), "status": item.status, "reason": item.reason, "visited": item.visited, "truncated": item.truncated}
