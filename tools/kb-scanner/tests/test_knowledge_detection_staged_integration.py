from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kb_scanner.adapters.legacy import LegacyPipelineRunner, create_legacy_application
from kb_scanner.core import CompletionStatus, FrontendSnapshot, StageResult
from kb_scanner.pipeline import StagedPipelineRunner, create_knowledge_detection_qualification_profile
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"
KNOWLEDGE_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge-production" / "x86-knowledge-sample.c"


class _RecordingFrontend:
    def __init__(self) -> None:
        self.called = False

    def analyze(self, *args: object) -> StageResult[FrontendSnapshot]:
        self.called = True
        return StageResult(FrontendSnapshot())


class KnowledgeDetectionStagedIntegrationTests(unittest.TestCase):
    def test_real_pipeline_reaches_detection_and_writes_no_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.c").write_bytes(KNOWLEDGE_FIXTURE.read_bytes())
            context = make_context(root, rule_dir=RULES)
            profile = create_knowledge_detection_qualification_profile()
            result = StagedPipelineRunner(profile).run(context)
            output_exists = (root / "out").exists()
            workspace = profile.workspace_collector.collect(context).value
            frontend = profile.frontend.analyze(context, workspace).value
            knowledge = profile.knowledge_provider.load(context).value
            normalized = profile.normalizer.normalize(context, frontend).value
            detections = profile.detector.detect(
                context,
                normalized,
                profile.analyzer.analyze(context, normalized, knowledge).value,
                knowledge,
            )
        self.assertTrue(result.success)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.artifacts, ())
        self.assertFalse(output_exists)
        statuses = {item.status for item in detections.value.observations}
        self.assertIn("confirmed_local", statuses)
        self.assertIn("candidate", statuses)
        self.assertIn("hint", statuses)
        confirmed = [item for item in detections.value.observations if item.status == "confirmed_local"]
        self.assertTrue(all(item.knowledge_ids and item.evidence_ids for item in confirmed))
        observed_kinds = {item.kind for item in detections.value.observations}
        self.assertTrue({
            "x86_assembly_instruction", "x86_register_reference", "x86_cpu_platform_api", "x86_target_feature",
            "fixed_vector_width_candidate",
        } <= observed_kinds)
        api_fact = next(item for item in normalized.facts if item.canonical_value == "cpuinfo_x86")
        self.assertFalse(any(set(api_fact.evidence_ids) & set(item.evidence_ids) for item in detections.value.observations))
        self.assertFalse(any(item.code == "detector.deferred-capabilities" for item in detections.diagnostics))

    def test_failed_provider_stops_before_frontend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.c").write_text("int main(void);", encoding="utf-8")
            profile = create_knowledge_detection_qualification_profile()
            recording = _RecordingFrontend()
            profile = replace(profile, frontend=recording)
            result = StagedPipelineRunner(profile).run(make_context(root, rule_dir=root / "missing-rules"))
        self.assertEqual(result.status, CompletionStatus.FAILED)
        self.assertFalse(recording.called)
        self.assertEqual(result.diagnostics[-1].code, "knowledge.invalid-manifest")

    def test_explicit_legacy_oracle_is_isolated_from_qualification(self) -> None:
        self.assertIsInstance(create_legacy_application()._profile.runner, LegacyPipelineRunner)


if __name__ == "__main__":
    unittest.main()
