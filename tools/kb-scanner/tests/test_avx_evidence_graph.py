from __future__ import annotations

import json
import resource
import time
import unittest
from pathlib import Path

from kb_scanner.analyzers import EvidenceGraphAnalyzer
from kb_scanner.core import CompletionStatus
from kb_scanner.detectors import LocalX86Detector
from kb_scanner.frontends.cpp import CppFrontend, CppWorkspaceCollector
from kb_scanner.knowledge import GeneratedFactsKnowledgeProvider
from kb_scanner.normalization import CppEvidenceNormalizer
from kb_scanner.pipeline import StagedPipelineRunner, create_knowledge_detection_qualification_profile
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("/fixtures/avx-avx2-example-code/source")
BASELINE_PATH = ROOT / "tests" / "fixtures" / "evidence-graph" / "avx-manual-baseline.json"
RULES = ROOT / "rulesets" / "riscv-porting"


class AvxEvidenceGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE.is_dir():
            raise AssertionError("AVX fixture must be mounted read-only by compose.test.yml")
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        cls.context = make_context(FIXTURE, rule_dir=RULES)
        cls.workspace = CppWorkspaceCollector().collect(cls.context)
        cls.frontend = CppFrontend().analyze(cls.context, cls.workspace.value)
        cls.knowledge = GeneratedFactsKnowledgeProvider().load(cls.context)
        cls.normalized = CppEvidenceNormalizer().normalize(cls.context, cls.frontend.value)
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        started = time.perf_counter()
        cls.analysis = EvidenceGraphAnalyzer().analyze(cls.context, cls.normalized.value, cls.knowledge.value)
        cls.graph_seconds = time.perf_counter() - started
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        cls.graph_rss_mib = max(0, rss_after - rss_before) / 1024
        cls.detections = LocalX86Detector().detect(
            cls.context, cls.normalized.value, cls.analysis.value, cls.knowledge.value
        )

    def test_manual_local_fact_counts_are_preserved(self) -> None:
        counts = self.baseline["auditedCounts"]
        observations = self.detections.value.observations
        self.assertEqual(len(self.workspace.value.files), len(self.baseline["sourceFiles"]))
        self.assertEqual(set(self.workspace.value.files), set(self.baseline["sourceFiles"]))
        self.assertEqual(sum(item.kind == "x86_header_reference" for item in observations), counts["x86Headers"])
        self.assertEqual(sum(item.kind == "x86_vector_type_reference" for item in observations), counts["x86VectorTypes"])
        self.assertEqual(
            sum(
                item.kind == "x86_intrinsic_reference" and item.metadata.get("factKind") == "symbol"
                for item in observations
            ),
            counts["directIntrinsicCalls"],
        )
        self.assertEqual(sum(item.kind == "x86_comment_hint" for item in observations), counts["commentHints"])

    def test_manual_macro_definitions_and_replacement_calls_have_exact_locations(self) -> None:
        evidence = self.frontend.value.evidence
        definitions = [
            item
            for item in evidence
            if item.kind == "macro_definition" and item.metadata.get("nodeType") == "preproc_function_def"
        ]
        calls = [
            item
            for item in evidence
            if item.kind == "macro_replacement_token" and item.metadata.get("tokenRole") == "call_candidate"
        ]
        expected_definitions = {
            (item["path"], item["name"], item["definition"]["start"][0])
            for item in self.baseline["macroDefinitions"]
        }
        expected_calls = {
            (
                item["path"],
                call["name"],
                *call["span"]["start"],
                *call["span"]["end"],
            )
            for item in self.baseline["macroDefinitions"]
            for call in item["replacementCalls"]
        }
        actual_definitions = {(item.location.start.path, item.value, item.location.start.line) for item in definitions}
        actual_calls = {
            (
                item.location.start.path,
                item.value,
                item.location.start.line,
                item.location.start.column,
                item.location.end.line,
                item.location.end.column,
            )
            for item in calls
        }
        self.assertEqual(actual_definitions, expected_definitions)
        self.assertEqual(actual_calls, expected_calls)
        self.assertEqual(len(definitions), self.baseline["auditedCounts"]["functionLikeMacroDefinitions"])
        self.assertEqual(len(calls), self.baseline["auditedCounts"]["replacementTerminalIntrinsicReferences"])
        self.assertFalse(
            any(
                item.kind == "call_expression"
                and item.location.start.path.endswith("include/gcc_support.h")
                and item.location.start.line in {9, 10, 12, 13, 15, 16, 18, 19, 21, 22, 24, 25}
                for item in evidence
            )
        )

    def test_macro_intrinsics_and_cross_file_proofs_are_graph_backed(self) -> None:
        observations = self.detections.value.observations
        replacement_observations = [
            item
            for item in observations
            if item.kind == "x86_intrinsic_reference" and item.metadata.get("factKind") == "macro_replacement"
        ]
        self.assertEqual(
            len(replacement_observations),
            self.baseline["auditedCounts"]["replacementTerminalIntrinsicReferences"],
        )
        self.assertTrue(all(item.relation_ids for item in replacement_observations))
        self.assertTrue(self.analysis.value.proof_paths)
        relation_by_id = {item.id: item for item in self.analysis.value.relations}
        self.assertTrue(
            any(
                {relation_by_id[relation_id].kind for relation_id in proof.relation_ids}
                >= {"invokes_macro", "expands_to"}
                for proof in self.analysis.value.proof_paths
            )
        )
        self.assertEqual(self.analysis.status, CompletionStatus.PARTIAL)
        self.assertTrue(all(item.status == "unknown" for item in self.analysis.value.relations if item.kind == "reachable_from"))

    def test_graph_resource_budget_and_staged_no_artifact_boundary(self) -> None:
        self.assertLess(self.graph_seconds, 15.0)
        self.assertLess(self.graph_rss_mib, 512.0)
        result = StagedPipelineRunner(create_knowledge_detection_qualification_profile()).run(self.context)
        self.assertTrue(result.success)
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.artifacts, ())
        self.assertFalse(self.context.output_dir.exists())
        self.assertEqual(self.baseline["buildEvidence"]["status"], "implemented-build-selection")


if __name__ == "__main__":
    unittest.main()
