from __future__ import annotations

from collections import defaultdict

from ..core import (
    CompletionStatus,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    FrontendSnapshot,
    NormalizedFact,
    NormalizedSnapshot,
    ScanContext,
    StageResult,
    normalize_project_path,
    stable_id,
)
from ..frontends.cpp.compilation_database import compilation_context_id
from .build_effects import validate_effects


class BuildEvidenceNormalizer:
    __slots__ = ()

    def normalize(self, context: ScanContext, frontend: FrontendSnapshot) -> StageResult[NormalizedSnapshot]:
        entity_ids = {item.id for item in frontend.entities}
        build_evidence = [item for item in frontend.evidence if item.kind.startswith("build_")]
        derived, derived_entities, diagnostics = self._compile_context_evidence(context, frontend)
        entities = {item.id: item for item in (*frontend.entities, *derived_entities)}
        build_evidence.extend(derived)
        invalid_effects = validate_effects(build_evidence)
        if invalid_effects:
            diagnostics.append(_warning('build-normalization.invalid-effect-provenance',
                                        'Build argument provenance is incomplete or conflicting'))
        for item in build_evidence:
            if item.subject_id not in entities:
                return _failed("build-normalization.unknown-subject", "Build Evidence references an unknown Entity")

        groups: dict[tuple[str, str, str, str], list[Evidence]] = defaultdict(list)
        for item in sorted(build_evidence, key=lambda value: value.id):
            if not isinstance(item.value, str) or not item.value.strip():
                diagnostics.append(_warning("build-normalization.invalid-value", "Build Evidence has no textual value"))
                continue
            canonical = _canonical(item.kind, item.value)
            scope = _scope(item)
            groups[(item.kind, item.subject_id, canonical, scope)].append(item)

        facts: list[NormalizedFact] = []
        for key in sorted(groups):
            kind, subject, value, scope = key
            items = groups[key]
            metadata: dict[str, object] = {"identityVersion": 1, "evidenceKind": kind}
            if "rpm" in items[0].metadata:
                metadata["rpm"] = dict(items[0].metadata["rpm"])
            if "autoconf" in items[0].metadata:
                metadata["autoconf"] = dict(items[0].metadata["autoconf"])
            if "cmake" in items[0].metadata:
                metadata["cmake"] = dict(items[0].metadata["cmake"])
            if "sourceChain" in items[0].metadata:
                metadata["sourceChain"] = dict(items[0].metadata["sourceChain"])
            if any(item.id in invalid_effects for item in items):
                metadata['effectProvenanceStatus'] = 'unknown'
            for field in (
                "inputKind", "selectionStatus", "role", "reason", "variable", "operator",
                "conditionGroup", "target", "configuration", "schema", "jsonPointer", "field", "section",
                "resolvedValue", "architectureProbe",
                "testRole", "testSuite", "coverageTarget", "testedSource", "callTarget", "alternativeTestFor",
            ):
                values = tuple(sorted({str(item.metadata[field]) for item in items if field in item.metadata}))
                if values:
                    metadata[field] = values[0] if len(values) == 1 else values
            facts.append(
                NormalizedFact(
                    id=stable_id("normalized_fact", 1, kind, subject, value, scope),
                    kind=kind,
                    subject_id=subject,
                    canonical_value=value,
                    scope=scope,
                    evidence_ids=tuple(item.id for item in items),
                    producers=tuple(item.producer for item in items),
                    metadata=metadata,
                )
            )
        status = CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE
        return StageResult(
            NormalizedSnapshot(
                entities=tuple(sorted(entities.values(), key=lambda item: (item.kind, item.name, item.id))),
                evidence=tuple(sorted({item.id: item for item in build_evidence}.values(), key=lambda item: item.id)),
                facts=tuple(sorted(facts, key=lambda item: (item.kind, item.scope, item.canonical_value, item.id))),
            ),
            status,
            tuple(diagnostics),
        )

    @staticmethod
    def _compile_context_evidence(
        context: ScanContext,
        frontend: FrontendSnapshot,
    ) -> tuple[list[Evidence], list[Entity], list[Diagnostic]]:
        sources = {item.name: item for item in frontend.entities if item.kind == "source_file"}
        evidence: list[Evidence] = []
        entities: list[Entity] = []
        diagnostics: list[Diagnostic] = []
        for unit in context.compile_contexts:
            try:
                relative = normalize_project_path(unit.path, context.input_root)
            except ValueError:
                diagnostics.append(_warning("build-normalization.context-outside-workspace", "Compilation context is outside workspace"))
                continue
            subject = sources.get(relative)
            if subject is None:
                continue
            context_id = compilation_context_id(unit, context.input_root)
            status, reason = _compile_status(unit.tokens, context.target_arch)
            for index, token in enumerate(unit.tokens):
                if index == 0 or not token.startswith("-"):
                    continue
                metadata = {"identityVersion": 1, "inputKind": "compilation-database", "selectionStatus": status, "reason": reason, "configuration": context_id, "tokenIndex": index}
                evidence.append(
                    Evidence(
                        stable_id("build_compile_argument_evidence", 1, subject.id, context_id, index, token),
                        "build_argument",
                        subject.id,
                        token[:512],
                        "compilation-database-build-bridge",
                        "compile_context",
                        "high" if status != "unknown" else "medium",
                        metadata=metadata,
                    )
                )
        return evidence, entities, diagnostics


def _compile_status(tokens: tuple[str, ...], target_arch: str) -> tuple[str, str]:
    text = " ".join(tokens).lower()
    target = target_arch.lower()
    if target in text or (target.startswith("riscv") and "--target=riscv" in text):
        return "selected", "target-argument"
    if any(value in text for value in ("--target=x86", "--target=i386", "-march=x86", "-m32", "-m64")):
        return "inactive", "different-target-argument"
    return "unknown", "target-provenance-missing"


def _canonical(kind: str, value: str) -> str:
    text = " ".join(value.strip().split())
    if kind in {"build_argument", "build_arch_constraint", "build_arch_probe"}:
        return text.lower()
    return text.replace("\\", "/")


def _scope(evidence: Evidence) -> str:
    if "cmake" in evidence.metadata:
        return f"cmake:{evidence.metadata['cmake']['key']}"
    if "autoconf" in evidence.metadata:
        return f"autoconf:{evidence.metadata['autoconf']['key']}"
    if "sourceChain" in evidence.metadata:
        data = evidence.metadata["sourceChain"]
        if data.get('useId'):
            return f"source-chain:{data['useId']}:{data['key']}:{data.get('recipeLine', '')}:{data.get('order', '')}"
        return f"source-chain:{data['key']}:{data.get('recipeLine', '')}:{data.get('order', '')}"
    if "rpm" in evidence.metadata:
        return f"rpm:{evidence.subject_id}:{evidence.metadata['rpm']['key']}"
    if evidence.location is None:
        return f"subject:{evidence.subject_id}:{evidence.metadata.get('configuration', '')}:{evidence.metadata.get('tokenIndex', '')}"
    start = evidence.location.start
    return f"source:{start.path}:{start.line}:{start.column or 0}:{evidence.kind}"


def _warning(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, "normalization.build", DiagnosticSeverity.WARNING, message, producer="build-evidence-normalizer")


def _failed(code: str, message: str) -> StageResult[NormalizedSnapshot]:
    diagnostic = Diagnostic(code, "normalization.build", DiagnosticSeverity.ERROR, message, producer="build-evidence-normalizer", affects_exit_code=True)
    return StageResult(None, CompletionStatus.FAILED, (diagnostic,))
