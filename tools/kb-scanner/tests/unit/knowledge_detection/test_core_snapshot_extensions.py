from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from kb_scanner.core import (
    KnowledgeEntry,
    KnowledgeSnapshot,
    KnowledgeSource,
    AnalysisSnapshot,
    ArtifactRef,
    Assessment,
    AssessmentSnapshot,
    ClassificationSnapshot,
    CompletionStatus,
    DetectionSnapshot,
    Diagnostic,
    DiagnosticSeverity,
    Entity,
    Evidence,
    FrontendSnapshot,
    NormalizedFact,
    NormalizedSnapshot,
    Observation,
    PipelineResult,
    Relation,
    StageResult,
    WorkspaceSnapshot,
    stable_id,
)


class CoreSnapshotExtensionTests(unittest.TestCase):
    def test_legacy_snapshot_construction_keeps_empty_defaults(self) -> None:
        knowledge = KnowledgeSnapshot("legacy", "1")
        normalized = NormalizedSnapshot()
        observation = Observation(stable_id("o"), "d", "k")
        self.assertEqual((knowledge.sources, knowledge.entries, normalized.facts, observation.knowledge_ids), ((), (), (), ()))

    def test_snapshots_and_observation_freeze_new_tuples(self) -> None:
        source = KnowledgeSource(stable_id("s"), "s", "generated-json", "s.json", "a" * 64)
        entry = KnowledgeEntry(stable_id("e"), "headers", "x86", "x.h", (source.id,))
        evidence_id = stable_id("ev")
        fact = NormalizedFact(stable_id("f"), "include", stable_id("subject"), "x.h", "source:x", (evidence_id,))
        knowledge = KnowledgeSnapshot(stable_id("ks"), "1", [source], [entry])  # type: ignore[arg-type]
        normalized = NormalizedSnapshot(facts=[fact])  # type: ignore[arg-type]
        observation = Observation(stable_id("o"), "d", "k", (evidence_id,), knowledge_ids=(entry.id, entry.id))
        self.assertEqual(knowledge.sources, (source,))
        self.assertEqual(knowledge.entries, (entry,))
        self.assertEqual(normalized.facts, (fact,))
        self.assertEqual(observation.knowledge_ids, (entry.id,))

    def test_observation_rejects_bad_knowledge_reference(self) -> None:
        with self.assertRaises(ValueError):
            Observation(stable_id("o"), "d", "k", knowledge_ids=("bad",))

    def test_observation_and_assessment_validate_all_references_and_fields(self) -> None:
        evidence_id = stable_id("ev")
        relation_id = stable_id("rel")
        knowledge_id = stable_id("knowledge")
        observation = Observation(
            stable_id("o"), "d", "k", (evidence_id,), (relation_id,), "high", "candidate", {"ok": True}, (knowledge_id,)
        )
        assessment = Assessment(stable_id("a"), "migration", "unknown", (evidence_id,), (relation_id,), "low", {"ok": True})
        self.assertEqual(observation.knowledge_ids, (knowledge_id,))
        self.assertEqual(assessment.state, "unknown")
        invalid_observations = (
            dict(detector_id=""), dict(kind=""), dict(confidence=""), dict(status=""),
            dict(evidence_ids=("bad",)), dict(relation_ids=("bad",)), dict(metadata={"bad": object()}),
        )
        base = dict(id=stable_id("base-o"), detector_id="d", kind="k")
        for changes in invalid_observations:
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                Observation(**(base | changes))
        invalid_assessments = (
            dict(kind=""), dict(state=""), dict(confidence=""), dict(evidence_ids=("bad",)),
            dict(relation_ids=("bad",)), dict(metadata={"bad": object()}),
        )
        base_assessment = dict(id=stable_id("base-a"), kind="k", state="unknown")
        for changes in invalid_assessments:
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                Assessment(**(base_assessment | changes))

    def test_result_contracts_cover_valid_and_invalid_states(self) -> None:
        diagnostic = Diagnostic("d", "s", DiagnosticSeverity.INFO, "m")
        self.assertEqual(StageResult("value", diagnostics=[diagnostic]).diagnostics, (diagnostic,))  # type: ignore[arg-type]
        for status in (CompletionStatus.COMPLETE, CompletionStatus.PARTIAL):
            with self.subTest(status=status), self.assertRaises(ValueError):
                StageResult(value=None, status=status)
        self.assertIsNone(StageResult(value=None, status=CompletionStatus.UNAVAILABLE).value)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = ArtifactRef("report", root / "report.json", "a" * 64)
            workspace = WorkspaceSnapshot(root, ["b.c", "a.c"])  # type: ignore[arg-type]
        self.assertTrue(artifact.path.is_absolute())
        self.assertEqual(workspace.files, ("b.c", "a.c"))
        with self.assertRaises(ValueError):
            ArtifactRef("", Path("x"), "a" * 64)
        with self.assertRaises(ValueError):
            ArtifactRef("x", Path("x"), "bad")

        entity = Entity(stable_id("entity"), "file", "a.c")
        evidence = Evidence(stable_id("evidence"), "include", entity.id, "x.h", "p", "m", "h")
        relation = Relation(stable_id("relation"), "calls", entity.id, entity.id)
        observation = Observation(stable_id("observation"), "d", "k")
        assessment = Assessment(stable_id("assessment"), "k", "unknown")
        self.assertEqual(FrontendSnapshot([entity], [evidence]).entities, (entity,))  # type: ignore[arg-type]
        self.assertEqual(NormalizedSnapshot([entity], [evidence], []).evidence, (evidence,))  # type: ignore[arg-type]
        self.assertEqual(AnalysisSnapshot([relation]).relations, (relation,))  # type: ignore[arg-type]
        self.assertEqual(DetectionSnapshot([observation]).observations, (observation,))  # type: ignore[arg-type]
        self.assertEqual(ClassificationSnapshot([observation]).observations, (observation,))  # type: ignore[arg-type]
        self.assertEqual(AssessmentSnapshot([assessment]).assessments, (assessment,))  # type: ignore[arg-type]
        result = PipelineResult(True, 0, CompletionStatus.COMPLETE, [diagnostic], [artifact])  # type: ignore[arg-type]
        self.assertEqual(result.diagnostics, (diagnostic,))
        self.assertEqual(result.artifacts, (artifact,))
        with self.assertRaises(ValueError):
            PipelineResult(False, -1, CompletionStatus.FAILED)
        with self.assertRaises(ValueError):
            PipelineResult(False, 0, CompletionStatus.COMPLETE)


if __name__ == "__main__":
    unittest.main()
