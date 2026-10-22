from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from ..core import (
    AnalysisSnapshot, ArtifactRef, AssessmentSnapshot, ClassificationSnapshot, CompletionStatus,
    DetectionSnapshot, Diagnostic, DiagnosticSeverity, FrontendSnapshot, KnowledgeSnapshot,
    NormalizedSnapshot, ScanContext, StageResult, WorkspaceSnapshot,
)
from .contract import validate_payload
from .mapper import CompatibilityMapper
from .renderers import render_html, render_json, render_log
from ..core.candidate_contract import CandidateAdmissionError, validate_candidates


class CompatibleReportProjector:
    __slots__ = ("_mapper", "_replace")

    def __init__(self, mapper: CompatibilityMapper | None = None, replace=os.replace) -> None:
        self._mapper = mapper or CompatibilityMapper()
        self._replace = replace

    def project(
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
    ) -> StageResult[tuple[ArtifactRef, ...]]:
        staging: Path | None = None
        try:
            validate_candidates(detections, classifications)
            payload = self._mapper.map(context, workspace, knowledge, frontend, facts, analysis, detections, classifications, assessments, diagnostics)
            validate_payload(payload)
            rendered: dict[str, bytes] = {}
            if "json" in context.formats:
                rendered["scan-result.json"] = render_json(payload)
                validate_payload(json.loads(rendered["scan-result.json"]))
            if "html" in context.formats:
                rendered["scan-report.html"] = render_html(payload)
            rendered["scan.log"] = render_log(payload)
            context.output_dir.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".kb-scanner-stage-", dir=context.output_dir))
            for name, content in rendered.items():
                (staging / name).write_bytes(content)
            self._publish(context.output_dir, staging, tuple(rendered))
            artifacts = tuple(
                ArtifactRef(name, context.output_dir / name, hashlib.sha256(content).hexdigest())
                for name, content in rendered.items()
            )
            return StageResult(artifacts)
        except Exception as exc:  # noqa: BLE001 - projection is the artifact boundary
            return StageResult(
                None,
                CompletionStatus.FAILED,
                (Diagnostic(
                    "projection.invalid-candidate-admission" if isinstance(exc, CandidateAdmissionError) else "projection.failed", "projector", DiagnosticSeverity.ERROR,
                    f"Compatible report projection failed: {type(exc).__name__}",
                    producer="compatible-report-projector", affects_exit_code=True,
                ),),
            )
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)

    def _publish(self, output: Path, staging: Path, names: tuple[str, ...]) -> None:
        backup = staging / ".backup"
        backup.mkdir()
        published: list[str] = []
        try:
            for name in names:
                target = output / name
                if target.exists():
                    self._replace(target, backup / name)
                self._replace(staging / name, target)
                published.append(name)
        except Exception:
            for name in reversed(published):
                target = output / name
                if target.exists():
                    target.unlink()
            for name in names:
                saved = backup / name
                if saved.exists():
                    self._replace(saved, output / name)
            raise
