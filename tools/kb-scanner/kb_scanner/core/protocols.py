from __future__ import annotations

from typing import Protocol

from .context import ScanContext, ScanRequest
from .diagnostics import Diagnostic
from .results import (
    AnalysisSnapshot,
    ArtifactRef,
    AssessmentSnapshot,
    ClassificationSnapshot,
    DetectionSnapshot,
    FrontendSnapshot,
    KnowledgeSnapshot,
    NormalizedSnapshot,
    PipelineResult,
    StageResult,
    WorkspaceSnapshot,
)


class ScanContextFactory(Protocol):
    def build(self, request: ScanRequest) -> StageResult[ScanContext]: ...


class PipelineRunner(Protocol):
    def run(self, context: ScanContext, initial_diagnostics: tuple[Diagnostic, ...] = ()) -> PipelineResult: ...


class WorkspaceCollector(Protocol):
    def collect(self, context: ScanContext) -> StageResult[WorkspaceSnapshot]: ...


class KnowledgeProvider(Protocol):
    def load(self, context: ScanContext) -> StageResult[KnowledgeSnapshot]: ...


class Frontend(Protocol):
    def analyze(self, context: ScanContext, workspace: WorkspaceSnapshot) -> StageResult[FrontendSnapshot]: ...


class Normalizer(Protocol):
    def normalize(self, context: ScanContext, frontend: FrontendSnapshot) -> StageResult[NormalizedSnapshot]: ...


class Analyzer(Protocol):
    def analyze(
        self,
        context: ScanContext,
        facts: NormalizedSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> StageResult[AnalysisSnapshot]: ...


class Detector(Protocol):
    def detect(
        self,
        context: ScanContext,
        facts: NormalizedSnapshot,
        analysis: AnalysisSnapshot,
        knowledge: KnowledgeSnapshot,
    ) -> StageResult[DetectionSnapshot]: ...


class Classifier(Protocol):
    def classify(
        self,
        context: ScanContext,
        detections: DetectionSnapshot,
        analysis: AnalysisSnapshot,
    ) -> StageResult[ClassificationSnapshot]: ...


class Assessor(Protocol):
    def assess(
        self,
        context: ScanContext,
        classifications: ClassificationSnapshot,
        analysis: AnalysisSnapshot,
    ) -> StageResult[AssessmentSnapshot]: ...


class ReportProjector(Protocol):
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
    ) -> StageResult[tuple[ArtifactRef, ...]]: ...
