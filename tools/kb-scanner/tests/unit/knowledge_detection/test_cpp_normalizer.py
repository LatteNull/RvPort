from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_scanner.core import CompilationUnitContext, CompletionStatus, FrontendSnapshot
from kb_scanner.normalization import CppEvidenceNormalizer
from tests.unit.knowledge_detection.support import make_context, make_entity, make_evidence


class CppNormalizerTests(unittest.TestCase):
    def test_normalizes_all_supported_kinds_and_aggregates_producers(self) -> None:
        entity = make_entity()
        kinds = {
            "include": '"x86\\x.h"', "call_expression": "_mm_x", "type_reference": "__m128",
            "macro_definition": "__X86__", "macro_expansion": "__X86__",
            "preprocessor_condition": "defined(__X86__)", "preprocessor_branch": "else",
            "inline_asm": "asm  pause", "comment": "// AVX", "declaration_attribute": "target(\"avx\")",
        }
        evidence = [make_evidence(entity, kind, value, line=index + 1) for index, (kind, value) in enumerate(kinds.items())]
        baseline_evidence = tuple(evidence)
        evidence.append(make_evidence(entity, "call_expression", "_mm_x", producer="clang", line=2))
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            baseline = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), baseline_evidence))
            result = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), tuple(evidence)))
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertEqual({item.kind for item in result.value.facts}, {
            "include", "symbol", "type", "macro", "preprocessor", "inline_asm", "comment", "declaration_attribute",
        })
        include = next(item for item in result.value.facts if item.kind == "include")
        self.assertEqual(include.canonical_value, "x86/x.h")
        symbol = next(item for item in result.value.facts if item.kind == "symbol")
        baseline_symbol = next(item for item in baseline.value.facts if item.kind == "symbol")
        self.assertEqual(symbol.id, baseline_symbol.id)
        self.assertEqual(set(symbol.producers), {"test", "clang"})
        self.assertEqual(len(symbol.evidence_ids), 2)

    def test_compiler_tokens_become_derived_evidence_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.c"
            source.write_text("int main(void);", encoding="utf-8")
            entity = make_entity()
            unit = CompilationUnitContext(
                path=source,
                tokens=("clang", "-mavx2", "-D__X86__", "@secret.rsp", "-Xclang", "-load", "plugin.so"),
                raw_command="must not be parsed",
                directory=root,
            )
            context = make_context(root, compile_contexts=(unit,))
            first = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), ()))
            second = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), ()))
        arguments = [item for item in first.value.facts if item.kind == "compiler_argument"]
        self.assertEqual(len(arguments), 6)
        self.assertIn("@secret.rsp", {item.canonical_value for item in arguments})
        self.assertEqual(first, second)
        self.assertTrue(all(item.context_ids for item in arguments))
        self.assertTrue(all(item.scope.startswith("compile:") for item in arguments))

    def test_unknown_non_string_empty_and_missing_context_subject_are_partial(self) -> None:
        entity = make_entity()
        evidence = (
            make_evidence(entity, "unknown", "x", line=1),
            make_evidence(entity, "comment", 3, line=2),
            make_evidence(entity, "comment", " ", line=3),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = CompilationUnitContext(path=root / "missing.c", tokens=("clang", "-mavx"), directory=root)
            result = CppEvidenceNormalizer().normalize(
                make_context(root, compile_contexts=(unit,)), FrontendSnapshot((entity,), evidence)
            )
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.value.facts, ())
        self.assertEqual(
            {item.code for item in result.diagnostics},
            {"normalization.unsupported-evidence-kind", "normalization.non-string-value", "normalization.empty-value", "normalization.context-subject-missing"},
        )

    def test_invalid_subject_and_invalid_fact_are_failed(self) -> None:
        entity = make_entity()
        other = make_entity("other.c")
        invalid_reference = make_evidence(other, "include", "x.h")
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            missing = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), (invalid_reference,)))
            valid = make_evidence(entity, "include", "x.h")
            with patch("kb_scanner.normalization.cpp.NormalizedFact", side_effect=ValueError("bad")):
                invalid = CppEvidenceNormalizer().normalize(context, FrontendSnapshot((entity,), (valid,)))
        self.assertEqual(missing.status, CompletionStatus.FAILED)
        self.assertEqual(missing.diagnostics[0].code, "normalization.unknown-subject")
        self.assertEqual(invalid.status, CompletionStatus.FAILED)
        self.assertEqual(invalid.diagnostics[0].code, "normalization.invalid-fact")

    def test_context_outside_workspace_is_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            unit = CompilationUnitContext(path=Path(other) / "main.c", tokens=("clang", "-mavx"))
            result = CppEvidenceNormalizer().normalize(
                make_context(root, compile_contexts=(unit,)), FrontendSnapshot((make_entity(),), ())
            )
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertEqual(result.diagnostics[0].code, "normalization.context-outside-workspace")

    def test_macro_attachments_are_normalized_with_definition_provenance(self) -> None:
        entity = make_entity()
        definition = make_evidence(entity, "macro_definition", "FAST", line=1)
        parameter = make_evidence(
            entity,
            "macro_parameter",
            "x",
            line=1,
            metadata={"macroDefinitionEvidenceId": definition.id, "ordinal": 0, "tokenRole": "parameter"},
        )
        replacement = make_evidence(
            entity,
            "macro_replacement_token",
            "_mm_add_ps",
            line=2,
            metadata={
                "macroDefinitionEvidenceId": definition.id,
                "ordinal": 0,
                "tokenRole": "call_candidate",
                "unsupportedSemantics": [],
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = CppEvidenceNormalizer().normalize(
                make_context(Path(tmp)), FrontendSnapshot((entity,), (definition, parameter, replacement))
            )
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        facts = {item.kind: item for item in result.value.facts}
        self.assertTrue({"macro", "macro_parameter", "macro_replacement"} <= set(facts))
        self.assertEqual(facts["macro_replacement"].metadata["macroDefinitionEvidenceIds"], (definition.id,))
        self.assertEqual(facts["macro_replacement"].metadata["tokenRole"], "call_candidate")

    def test_tree_sitter_and_clang_macro_tokens_merge_without_changing_fact_identity(self) -> None:
        entity = make_entity()
        tree_definition = make_evidence(entity, "macro_definition", "FAST", producer="tree-sitter", line=1)
        clang_definition = make_evidence(entity, "macro_definition", "FAST", producer="clang", line=1)
        tree_token = make_evidence(
            entity,
            "macro_replacement_token",
            "_mm_add_ps",
            producer="tree-sitter",
            line=2,
            metadata={"macroDefinitionEvidenceId": tree_definition.id, "ordinal": 0, "tokenRole": "call_candidate"},
        )
        clang_token = make_evidence(
            entity,
            "macro_replacement_token",
            "_mm_add_ps",
            producer="clang",
            line=2,
            metadata={"macroDefinitionEvidenceId": clang_definition.id, "ordinal": 0, "tokenRole": "call_candidate"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            context = make_context(Path(tmp))
            baseline = CppEvidenceNormalizer().normalize(
                context,
                FrontendSnapshot((entity,), (tree_definition, tree_token)),
            )
            merged = CppEvidenceNormalizer().normalize(
                context,
                FrontendSnapshot((entity,), (tree_definition, clang_definition, tree_token, clang_token)),
            )
        baseline_fact = next(item for item in baseline.value.facts if item.kind == "macro_replacement")
        merged_fact = next(item for item in merged.value.facts if item.kind == "macro_replacement")
        self.assertEqual(merged_fact.id, baseline_fact.id)
        self.assertEqual(set(merged_fact.producers), {"tree-sitter", "clang"})
        self.assertEqual(
            set(merged_fact.metadata["macroDefinitionEvidenceIds"]),
            {tree_definition.id, clang_definition.id},
        )

    def test_macro_attachment_with_unknown_definition_fails(self) -> None:
        entity = make_entity()
        attachment = make_evidence(
            entity,
            "macro_replacement_token",
            "_mm_add_ps",
            metadata={"macroDefinitionEvidenceId": "a" * 64, "ordinal": 0, "tokenRole": "call_candidate"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = CppEvidenceNormalizer().normalize(
                make_context(Path(tmp)), FrontendSnapshot((entity,), (attachment,))
            )
        self.assertEqual(result.status, CompletionStatus.FAILED)
        self.assertEqual(result.diagnostics[0].code, "normalization.invalid-macro-definition-reference")


if __name__ == "__main__":
    unittest.main()
