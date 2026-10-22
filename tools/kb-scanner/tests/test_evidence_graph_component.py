from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.analyzers import EvidenceGraphAnalyzer
from kb_scanner.core import CompletionStatus, KnowledgeSnapshot, stable_id
from kb_scanner.frontends.cpp import CppFrontend, CppWorkspaceCollector
from kb_scanner.normalization import CppEvidenceNormalizer
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "evidence-graph" / "component"


class EvidenceGraphComponentTests(unittest.TestCase):
    def test_real_tree_sitter_builds_macro_branch_alternative_and_cycle_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            context = make_context(FIXTURE, rule_dir=Path(raw) / "rules")
            workspace = CppWorkspaceCollector().collect(context).value
            frontend = CppFrontend().analyze(context, workspace)
            normalized = CppEvidenceNormalizer().normalize(context, frontend.value)
            analysis = EvidenceGraphAnalyzer().analyze(
                context,
                normalized.value,
                KnowledgeSnapshot(stable_id("knowledge"), "1"),
            )
        self.assertEqual(set(workspace.files), {"main.c", "support.h"})
        self.assertIn(frontend.status, {CompletionStatus.COMPLETE, CompletionStatus.PARTIAL})
        macro_definitions = [item for item in frontend.value.evidence if item.kind == "macro_definition"]
        function_definitions = [item for item in macro_definitions if item.metadata["nodeType"] == "preproc_function_def"]
        replacement_calls = [
            item
            for item in frontend.value.evidence
            if item.kind == "macro_replacement_token" and item.metadata["tokenRole"] == "call_candidate"
        ]
        self.assertEqual({item.value for item in function_definitions}, {"FAST", "WRAP", "LOOP_A", "LOOP_B"})
        self.assertEqual({item.value for item in replacement_calls}, {"_mm_add_ps", "FAST", "LOOP_A", "LOOP_B"})
        self.assertFalse(
            any(
                item.kind == "call_expression"
                and item.location.start.path == "support.h"
                and item.location.start.line in {4, 5, 6, 7}
                for item in frontend.value.evidence
            )
        )
        relation_kinds = {item.kind for item in analysis.value.relations}
        self.assertTrue({"includes", "defines", "invokes_macro", "expands_to", "calls", "has_branch", "guarded_by", "alternative_to"} <= relation_kinds)
        self.assertTrue(analysis.value.proof_paths)
        self.assertEqual(analysis.status, CompletionStatus.PARTIAL)

    def test_real_parser_retains_only_x86_unsupported_and_ambiguous_inputs_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "dup.h").write_text("#define LEFT 1\n", encoding="utf-8")
            (root / "b" / "dup.h").write_text("#define RIGHT 1\n", encoding="utf-8")
            (root / "main.c").write_text(
                '#include "dup.h"\n#include "missing.h"\n'
                "#define JOIN(a, b) _mm_add_ps(a ## b)\n"
                "#if defined(__AVX__)\nint only_x86(void) { return JOIN(1, 2); }\n#endif\n",
                encoding="utf-8",
            )
            context = make_context(root, rule_dir=root / "rules")
            workspace = CppWorkspaceCollector().collect(context).value
            frontend = CppFrontend().analyze(context, workspace)
            normalized = CppEvidenceNormalizer().normalize(context, frontend.value)
            analysis = EvidenceGraphAnalyzer().analyze(
                context,
                normalized.value,
                KnowledgeSnapshot(stable_id("knowledge"), "1"),
            )
        self.assertEqual(frontend.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.code == "tree-sitter.unsupported-macro-semantics" for item in frontend.diagnostics))
        self.assertTrue(
            {"graph.include-ambiguous-include", "graph.include-unresolved-include"}
            <= {item.code for item in analysis.diagnostics}
        )
        self.assertFalse(any(item.kind == "alternative_to" for item in analysis.value.relations))
        self.assertTrue(
            any(
                item.status == "partial"
                and "unsupported-preprocessor-semantics" in str(item.metadata.get("reason"))
                for item in analysis.value.relations
            )
        )


if __name__ == "__main__":
    unittest.main()
