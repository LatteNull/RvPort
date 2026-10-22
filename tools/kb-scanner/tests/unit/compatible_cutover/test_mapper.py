from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kb_scanner.core import AssessmentSnapshot, ClassificationSnapshot, Diagnostic, DiagnosticSeverity, FrontendSnapshot
from kb_scanner.projection.mapper import CompatibilityMapper, ProjectionError

from .support import graph


class MapperTests(unittest.TestCase):
    def test_maps_finding_trace_summary_and_static_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = graph(Path(tmp))
            diagnostic = Diagnostic("unit.note", "unit", DiagnosticSeverity.INFO, "hello")
            value = CompatibilityMapper().map(*args[:-1], (diagnostic,))
        finding = value["findings"][0]
        self.assertEqual((str(Path(tmp).resolve() / "src/main.c"), 7, 3), (finding["file"], finding["line"], finding["column"]))
        self.assertEqual("_mm_add_ps", finding["snippet"])
        self.assertEqual("_mm_add_ps", finding["symbol"])
        self.assertEqual({"line": 7, "column": 3}, finding["trace"]["primarySpan"]["start"])
        self.assertEqual({"line": 7, "column": 8}, finding["trace"]["primarySpan"]["end"])
        self.assertEqual(1, finding["trace"]["occurrenceCount"])
        self.assertEqual("complete", finding["trace"]["referenceClosure"]["status"])
        self.assertEqual("C_CPP.X86.INTRINSIC_CALL", finding["rule_id"])
        self.assertTrue(finding["is_blocking"])
        self.assertEqual(1, value["summary"]["blocking"])
        self.assertEqual("riscv_blocked", value["summary"]["readiness"]["state"])
        self.assertFalse(value["summary"]["readiness"]["compiled"])
        self.assertEqual(["hello"], value["diagnostics"])
        self.assertEqual("compiler-facts", finding["trace"]["knowledge"][0]["producers"][0])

    def test_mapping_impacts_and_optional_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for impact, finding_type in (("actionable_non_blocking", "issue"), ("guarded_inactive", "guarded"), ("hint", "hint"), ("unknown", "issue")):
                args = graph(Path(tmp), impact=impact, with_assessment=False)
                value = CompatibilityMapper().map(*args)
                self.assertEqual(finding_type, value["findings"][0]["finding_type"])
                self.assertNotIn("readiness", value["summary"])

    def test_broken_reference_empty_evidence_and_assessment_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = list(graph(Path(tmp)))
            cls = args[7].classifications[0]
            args[7] = ClassificationSnapshot(args[7].observations, (replace(cls, observation_ids=("0" * 64,)),))
            with self.assertRaises(ProjectionError):
                CompatibilityMapper().map(*args)
            args = list(graph(Path(tmp)))
            cls = args[7].classifications[0]
            args[7] = ClassificationSnapshot(args[7].observations, (replace(cls, evidence_ids=()),))
            value = CompatibilityMapper().map(*args)
            self.assertEqual([], value["findings"])
            self.assertIn("no locatable evidence", value["diagnostics"][0])
            args = list(graph(Path(tmp)))
            assessment = args[8].assessments[0]
            args[8] = AssessmentSnapshot((assessment, assessment))
            with self.assertRaisesRegex(ProjectionError, "exactly one"):
                CompatibilityMapper().map(*args)

    def test_unknown_evidence_knowledge_relation_and_proof_preserve_partial_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for field in ("evidence_ids", "knowledge_ids", "relation_ids", "proof_path_ids"):
                args = list(graph(Path(tmp)))
                cls = args[7].classifications[0]
                values = (*getattr(cls, field), "f" * 64)
                args[7] = ClassificationSnapshot(args[7].observations, (replace(cls, **{field: values}),))
                value = CompatibilityMapper().map(*args)
                with self.subTest(field=field):
                    self.assertEqual(1, len(value["findings"]))
                    closure = value["findings"][0]["trace"]["referenceClosure"]
                    self.assertEqual("partial", closure["status"])
                    self.assertIn("f" * 64, closure["missingIds"])
                    self.assertTrue(any("partial reference closure" in item for item in value["diagnostics"]))

    def test_build_branch_compatibility_fields_and_compile_source_are_projected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = list(graph(Path(tmp), detector="BUILD.SELECTION", kind="build_selected_x86_dependency"))
            evidence = replace(args[3].evidence[0], kind="build_argument", producer="compilation-database-build-bridge", location=None)
            args[3] = FrontendSnapshot(args[3].entities, (evidence,))
            observation = replace(args[7].observations[0], metadata={
                "branchGroupId": "branch", "branchRole": "x86", "compatibleSiblingBranch": True,
                "compatibleBranchKind": "riscv", "conditionExpression": "defined(__x86_64__) && USE_SIMD",
                "selectionStatus": "selected", "reason": "target-argument",
            })
            args[6] = replace(args[6], observations=(observation,))
            args[7] = ClassificationSnapshot((observation,), args[7].classifications)
            value = CompatibilityMapper().map(*args)
        finding = value["findings"][0]
        self.assertEqual("compile_command", finding["source_kind"])
        self.assertEqual("branch", finding["branch_group_id"])
        self.assertEqual("riscv", finding["compatible_branch_kind"])
        self.assertTrue(finding["alternative_impl"]["has_compatible_alternative"])
        self.assertEqual("selected", finding["build_context"]["selectionStatus"])
        self.assertEqual(["USE_SIMD", "__x86_64__"], finding["condition_macros"])


if __name__ == "__main__":
    unittest.main()
