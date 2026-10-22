from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ..core import (
    CompletionStatus, Diagnostic, DiagnosticSeverity, KnowledgeEntry, KnowledgeSnapshot, KnowledgeSource, ScanContext, StageResult,
)
from .identity import canonicalize_fact_value, content_sha256, knowledge_entry_id, knowledge_snapshot_id, knowledge_source_id
from .production import lint_curated, lint_generated
from .schema import (
    CuratedFactsModel, CuratedManifestSourceModel, FACT_KINDS, GeneratedFactsModel, GeneratedFactsV2Model,
    GeneratedSourceModel, KnowledgeManifestModel, KnowledgeManifestV2Model, ManifestSourceModel, ReferenceRegistryModel,
)


class GeneratedFactsKnowledgeProvider:
    __slots__ = ("_manifest_name",)

    def __init__(self, manifest_name: str | None = None) -> None:
        self._manifest_name = manifest_name

    def load(self, context: ScanContext) -> StageResult[KnowledgeSnapshot]:
        root = context.rule_dir.resolve()
        manifest_path = (root / (self._manifest_name or context.knowledge_manifest_name)).resolve()
        if not manifest_path.is_relative_to(root):
            return _failed("knowledge.manifest-path-escape", "Knowledge manifest resolves outside the rule pack")
        try:
            content = manifest_path.read_bytes()
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("manifest root must be an object")
            if payload.get("schemaVersion") == "1.0":
                manifest: KnowledgeManifestModel | KnowledgeManifestV2Model = KnowledgeManifestModel.model_validate_json(content)
            elif payload.get("schemaVersion") == "2.0":
                manifest = KnowledgeManifestV2Model.model_validate_json(content)
            else:
                raise ValueError("unsupported manifest version")
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            return _failed("knowledge.invalid-manifest", f"Knowledge manifest is unavailable or invalid: {type(exc).__name__}")

        sources: list[KnowledgeSource] = []
        entries: dict[str, KnowledgeEntry] = {}
        diagnostics: list[Diagnostic] = []
        declarations = manifest.generatedSources if isinstance(manifest, KnowledgeManifestModel) else manifest.sources
        for declaration in declarations:
            loaded = self._load_source(root, declaration)
            if isinstance(loaded, Diagnostic):
                diagnostics.append(loaded)
                continue
            source, facts = loaded
            sources.append(source)
            self._merge_entries(entries, source, facts)

        if not sources:
            return _failed("knowledge.no-valid-sources", "No knowledge source could be loaded", diagnostics=tuple(diagnostics))
        ordered_sources = tuple(sorted(sources, key=lambda item: (item.source_id, item.id)))
        ordered_entries = tuple(sorted(entries.values(), key=lambda item: (item.fact_kind, item.canonical_value, item.id)))
        snapshot = KnowledgeSnapshot(
            identity=knowledge_snapshot_id(
                manifest.catalogId, manifest.version, tuple(item.id for item in ordered_sources), tuple(item.id for item in ordered_entries),
            ),
            version=manifest.version,
            sources=ordered_sources,
            entries=ordered_entries,
        )
        status = CompletionStatus.PARTIAL if diagnostics else CompletionStatus.COMPLETE
        return StageResult(value=snapshot, status=status, diagnostics=tuple(diagnostics))

    @staticmethod
    def _load_source(
        root: Path,
        model: GeneratedSourceModel | ManifestSourceModel | CuratedManifestSourceModel,
    ) -> tuple[KnowledgeSource, tuple[tuple[str, str, str, tuple[str, ...]], ...]] | Diagnostic:
        content_or_error = _read_declared_json(root, model, model.path, model.sha256)
        if isinstance(content_or_error, Diagnostic):
            return content_or_error
        content = content_or_error
        try:
            if isinstance(model, CuratedManifestSourceModel):
                reference_content = _read_declared_json(root, model, model.referencePath, model.referenceSha256)
                if isinstance(reference_content, Diagnostic):
                    return reference_content
                registry = ReferenceRegistryModel.model_validate_json(reference_content)
                curated = CuratedFactsModel.model_validate_json(content)
                if curated.sourceId != model.sourceId:
                    raise ValueError("curated source identity mismatch")
                lint = lint_curated(curated, registry)
                if lint:
                    raise ValueError(lint[0])
                facts = tuple((item.factKind, item.canonicalValue, item.semanticScope, item.referenceIds) for item in curated.entries)
                metadata = {
                    "reviewPolicy": curated.reviewPolicy,
                    "reviewPolicyVersion": curated.reviewPolicyVersion,
                    "referenceIds": sorted({reference for item in curated.entries for reference in item.referenceIds}),
                }
                kind = "curated-json"
            elif isinstance(model, ManifestSourceModel) and model.kind == "generated-v2":
                generated = GeneratedFactsV2Model.model_validate_json(content)
                if generated.source.sourceId != model.sourceId or lint_generated(generated):
                    raise ValueError("generated source identity or canonical order is invalid")
                facts = tuple((item.factKind, item.canonicalValue, item.semanticScope, ()) for item in generated.facts)
                metadata = {"upstreamSource": generated.source.model_dump(mode="json")}
                kind = "generated-json-v2"
            else:
                legacy = GeneratedFactsModel.model_validate_json(content)
                payload = legacy.model_dump()
                facts = tuple((fact_kind, value, "x86-only", ()) for fact_kind in FACT_KINDS[:6] for value in payload[fact_kind])
                metadata = {"originalSource": legacy.source}
                kind = "generated-json"
        except (ValidationError, ValueError) as exc:
            return _source_diagnostic(model, "knowledge.source-invalid", f"Knowledge source shape is invalid: {type(exc).__name__}")
        source = KnowledgeSource(
            id=knowledge_source_id(model.sourceId, model.path, model.sha256),
            source_id=model.sourceId,
            kind=kind,
            logical_path=model.path,
            sha256=model.sha256,
            metadata=metadata,
        )
        return source, facts

    @staticmethod
    def _merge_entries(
        entries: dict[str, KnowledgeEntry], source: KnowledgeSource,
        facts: tuple[tuple[str, str, str, tuple[str, ...]], ...],
    ) -> None:
        for fact_kind, raw_value, scope, reference_ids in facts:
            canonical = canonicalize_fact_value(fact_kind, raw_value)
            entry_id = knowledge_entry_id(fact_kind, "x86", canonical)
            current = entries.get(entry_id)
            source_ids = (source.id,) if current is None else (*current.source_ids, source.id)
            metadata = {"identityVersion": 1} if current is None else dict(current.metadata or {})
            if fact_kind not in FACT_KINDS[:6]:
                metadata["semanticScope"] = scope
            if reference_ids:
                metadata["referenceIds"] = sorted(set(metadata.get("referenceIds", [])) | set(reference_ids))
            entries[entry_id] = KnowledgeEntry(
                id=entry_id,
                fact_kind=fact_kind,
                architecture_family="x86",
                canonical_value=canonical,
                source_ids=source_ids,
                metadata=metadata,
            )


def _read_declared_json(
    root: Path, model: GeneratedSourceModel, logical_path: str, expected_hash: str,
) -> bytes | Diagnostic:
    path = (root / logical_path).resolve()
    if not path.is_relative_to(root):
        return _source_diagnostic(model, "knowledge.source-path-escape", "Knowledge source resolves outside the rule pack")
    try:
        content = path.read_bytes()
    except OSError as exc:
        return _source_diagnostic(model, "knowledge.source-unreadable", f"Knowledge source is unreadable: {type(exc).__name__}")
    if content_sha256(content) != expected_hash:
        return _source_diagnostic(model, "knowledge.source-hash-mismatch", "Knowledge source digest does not match manifest")
    return content


def _source_diagnostic(model: GeneratedSourceModel, code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        stage="knowledge",
        severity=DiagnosticSeverity.WARNING,
        message=f"{model.sourceId}: {message}",
        producer="generated-facts-knowledge-provider",
        details={"sourceId": model.sourceId, "logicalPath": model.path},
    )


def _failed(code: str, message: str, *, diagnostics: tuple[Diagnostic, ...] = ()) -> StageResult[KnowledgeSnapshot]:
    fatal = Diagnostic(
        code=code, stage="knowledge", severity=DiagnosticSeverity.ERROR, message=message,
        producer="generated-facts-knowledge-provider", affects_exit_code=True,
    )
    return StageResult(value=None, status=CompletionStatus.FAILED, diagnostics=(*diagnostics, fatal))
