from __future__ import annotations

import json
import unittest
from pathlib import Path

from kb_scanner.core import CompilationUnitContext, CompletionStatus, ScanContext
from kb_scanner.frontends.cpp import (
    CPP_EVIDENCE_KINDS,
    TreeSitterCppAdapter,
    make_source_file_entity,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "formal-cpp-frontend"
SOURCE_ROOT = FIXTURE_ROOT / "src"


def make_context(*, comments: bool = True, compile_contexts: tuple[CompilationUnitContext, ...] = ()) -> ScanContext:
    return ScanContext(
        input_root=SOURCE_ROOT,
        output_dir=SOURCE_ROOT / "out",
        rule_dir=ROOT / "rulesets" / "riscv-porting",
        languages=("c", "cpp"),
        excludes=(".git", "build"),
        exclude_paths=(),
        formats=("json", "html"),
        context_infer="auto",
        target_arch="riscv64",
        include_inactive_branches=False,
        include_comment_hints=comments,
        locale="zh-CN",
        compile_commands_path=None,
        compile_contexts=compile_contexts,
        scan_mode="source_context",
        rule_pack_id="riscv-porting",
        rule_pack_version="1",
        knowledge_id="riscv-porting@1",
        scanner_name="kb-scanner",
        scanner_version="0.1.0",
    )


def analyze(relative_path: str, context: ScanContext | None = None):
    active_context = context or make_context()
    entity = make_source_file_entity(relative_path, ("c", "cpp"), active_context.scanner_version)
    return TreeSitterCppAdapter().analyze_file(active_context, SOURCE_ROOT, relative_path, entity)


class TreeSitterCppAdapterTests(unittest.TestCase):
    def test_vocabulary_is_explicit_and_has_no_parse_error_fact(self) -> None:
        self.assertEqual(
            CPP_EVIDENCE_KINDS,
            {
                "usage_scope",
                "preprocessor_condition",
                "preprocessor_branch",
                "include",
                "macro_definition",
                "macro_parameter",
                "macro_argument_token",
                "macro_replacement_token",
                "macro_expansion",
                "call_expression",
                "type_reference",
                "template_declaration",
                "constexpr_condition",
                "selection_condition",
                "enum_declaration",
                "enum_member_declaration",
                "enum_member_reference",
                "inline_asm",
                  "declaration_attribute",
                  "function_declaration",
                  "function_semantics",
                "comment",
            },
        )
        self.assertNotIn("parse_error", CPP_EVIDENCE_KINDS)

    def test_semantic_fixtures_produce_required_evidence_kinds(self) -> None:
        expected = json.loads((FIXTURE_ROOT / "expected-evidence.json").read_text(encoding="utf-8"))
        for relative_path, required_kinds in expected.items():
            with self.subTest(relative_path=relative_path):
                result = analyze(relative_path)
                actual = {item.kind for item in result.value}
                self.assertTrue(set(required_kinds).issubset(actual), (required_kinds, sorted(actual)))

    def test_non_enum_constexpr_does_not_emit_architecture_selection_evidence(self) -> None:
        result = analyze("complete.cpp")
        self.assertFalse(
            {"constexpr_condition", "selection_condition"}
            & {item.kind for item in result.value}
        )

    def test_complete_c_and_cpp_have_project_relative_spans_and_versioned_producers(self) -> None:
        for relative_path in ("complete.c", "complete.cpp"):
            result = analyze(relative_path)
            self.assertEqual(result.status, CompletionStatus.COMPLETE)
            self.assertTrue(result.value)
            for item in result.value:
                self.assertEqual(item.location.start.path, relative_path)
                self.assertGreaterEqual(item.location.start.line, 1)
                self.assertRegex(item.producer, r"^tree-sitter-(c|cpp)@\d")
                self.assertEqual(item.parse_mode, "tree_sitter_baseline")
                self.assertEqual(item.metadata["identityVersion"], 1)

    def test_incomplete_source_is_partial_but_retains_recovered_evidence(self) -> None:
        result = analyze("incomplete.cpp")
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertTrue(result.value)
        self.assertEqual(result.diagnostics[0].code, "tree-sitter.partial-parse")
        self.assertEqual(result.diagnostics[0].location.path, "incomplete.cpp")
        self.assertTrue(all(item.confidence == "medium" for item in result.value))

    def test_file_read_failure_is_isolated_as_partial(self) -> None:
        result = analyze("missing.cpp")
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.value, ())
        self.assertEqual(result.diagnostics[0].code, "tree-sitter.read-failed")

    def test_ambiguous_header_uses_deterministic_error_score_and_cpp_tie_break(self) -> None:
        first = analyze("ambiguous.h")
        second = analyze("ambiguous.h")
        self.assertEqual(first, second)
        self.assertEqual(first.status, CompletionStatus.COMPLETE)
        self.assertTrue(first.value)
        self.assertEqual({item.metadata["language"] for item in first.value}, {"cpp"})
        self.assertEqual({item.metadata["languageSource"] for item in first.value}, {"ambiguous_header"})

    def test_direct_compilation_context_selects_header_grammar(self) -> None:
        unit = CompilationUnitContext(
            path=SOURCE_ROOT / "ambiguous.h",
            tokens=("clang", "-x", "c", "ambiguous.h"),
            compiler="clang",
            directory=SOURCE_ROOT,
        )
        result = analyze("ambiguous.h", make_context(compile_contexts=(unit,)))
        self.assertEqual({item.metadata["language"] for item in result.value}, {"c"})
        self.assertEqual({item.metadata["languageSource"] for item in result.value}, {"compilation_context"})
        self.assertEqual(result.status, CompletionStatus.PARTIAL)

    def test_comment_switch_and_stable_deduplication(self) -> None:
        enabled = analyze("comments.c", make_context(comments=True))
        repeated = analyze("comments.c", make_context(comments=True))
        disabled = analyze("comments.c", make_context(comments=False))
        self.assertEqual(enabled, repeated)
        self.assertIn("comment", {item.kind for item in enabled.value})
        self.assertNotIn("comment", {item.kind for item in disabled.value})
        self.assertEqual(len(enabled.value), len({item.id for item in enabled.value}))


if __name__ == "__main__":
    unittest.main()
