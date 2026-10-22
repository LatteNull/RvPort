from __future__ import annotations

from ..adapters.cli import StagedContextFactory
from ..assessors import MigrationAssessor
from ..classifiers import MigrationClassifier
from ..frontends.build import ProjectWorkspaceCollector
from ..knowledge import GeneratedFactsKnowledgeProvider
from ..projection import VersionedReportProjector
from .application import ScanApplication
from .composite import CompositeAnalyzer, CompositeDetector, CompositeNormalizer, CompositeProjectFrontend
from .orchestrator import StagedPipelineRunner
from .profile import ApplicationProfile, PipelineProfile


def create_default_profile() -> PipelineProfile:
    return PipelineProfile(
        workspace_collector=ProjectWorkspaceCollector(),
        knowledge_provider=GeneratedFactsKnowledgeProvider(),
        frontend=CompositeProjectFrontend(),
        normalizer=CompositeNormalizer(),
        analyzer=CompositeAnalyzer(),
        detector=CompositeDetector(),
        classifier=MigrationClassifier(),
        assessor=MigrationAssessor(),
        report_projector=VersionedReportProjector(),
    )


def create_default_application() -> ScanApplication:
    return ScanApplication(ApplicationProfile(StagedContextFactory(), StagedPipelineRunner(create_default_profile())))
