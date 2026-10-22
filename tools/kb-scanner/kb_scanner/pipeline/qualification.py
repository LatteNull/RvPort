from __future__ import annotations

from ..assessors import MigrationAssessor
from ..classifiers import MigrationClassifier
from ..core import StageResult
from ..frontends.build import ProjectWorkspaceCollector
from ..knowledge import GeneratedFactsKnowledgeProvider
from .composite import CompositeAnalyzer, CompositeDetector, CompositeNormalizer, CompositeProjectFrontend
from .profile import PipelineProfile


class _EmptyProjector:
    __slots__ = ()

    def project(self, *args: object) -> StageResult[tuple]:
        del args
        return StageResult(())


def create_knowledge_detection_qualification_profile() -> PipelineProfile:
    return PipelineProfile(
        workspace_collector=ProjectWorkspaceCollector(),
        knowledge_provider=GeneratedFactsKnowledgeProvider(),
        frontend=CompositeProjectFrontend(),
        normalizer=CompositeNormalizer(),
        analyzer=CompositeAnalyzer(),
        detector=CompositeDetector(),
        classifier=MigrationClassifier(),
        assessor=MigrationAssessor(),
        report_projector=_EmptyProjector(),
    )
