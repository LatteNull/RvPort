from __future__ import annotations

from dataclasses import dataclass

from ..core.protocols import (
    Analyzer,
    Assessor,
    Classifier,
    Detector,
    Frontend,
    KnowledgeProvider,
    Normalizer,
    PipelineRunner,
    ReportProjector,
    ScanContextFactory,
    WorkspaceCollector,
)


@dataclass(frozen=True, slots=True)
class ApplicationProfile:
    context_factory: ScanContextFactory
    runner: PipelineRunner

    def __post_init__(self) -> None:
        if self.context_factory is None or self.runner is None:
            raise ValueError("application profile requires a context factory and runner")


@dataclass(frozen=True, slots=True)
class PipelineProfile:
    workspace_collector: WorkspaceCollector
    knowledge_provider: KnowledgeProvider
    frontend: Frontend
    normalizer: Normalizer
    analyzer: Analyzer
    detector: Detector
    classifier: Classifier
    assessor: Assessor
    report_projector: ReportProjector

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if getattr(self, name) is None:
                raise ValueError(f"pipeline profile component {name} must not be None")
