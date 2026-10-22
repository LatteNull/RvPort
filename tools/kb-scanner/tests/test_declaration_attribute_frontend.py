from __future__ import annotations

import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.frontends.cpp import TreeSitterCppAdapter, make_source_file_entity
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "tests" / "fixtures" / "declaration-attributes"


def analyze(path: str):
    context = make_context(SOURCE_ROOT, rule_dir=ROOT / "rulesets" / "riscv-porting")
    entity = make_source_file_entity(path, ("c", "cpp"), context.scanner_version)
    return TreeSitterCppAdapter().analyze_file(context, SOURCE_ROOT, path, entity)


class DeclarationAttributeFrontendTests(unittest.TestCase):
    def test_target_and_vector_size_attributes_are_bounded_syntax_evidence(self) -> None:
        result = analyze("attributes.c")
        attributes = [item for item in result.value if item.kind == "declaration_attribute"]
        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        self.assertGreaterEqual(len(attributes), 2)
        text = " ".join(str(item.value) for item in attributes)
        self.assertIn("target", text)
        self.assertIn("vector_size", text)
        self.assertTrue(all(len(str(item.value)) <= 512 for item in attributes))
        self.assertTrue(all(item.location.start.path == "attributes.c" for item in attributes))

    def test_incomplete_attribute_is_partial_and_never_guessed(self) -> None:
        result = analyze("attribute-incomplete.cpp")
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        attributes = [item for item in result.value if item.kind == "declaration_attribute"]
        self.assertTrue(attributes)
        self.assertTrue(all(item.confidence == "medium" for item in attributes))

    def test_plain_declaration_does_not_emit_attribute_or_identifier_sweep(self) -> None:
        result = analyze("plain-declaration.c")
        self.assertNotIn("declaration_attribute", {item.kind for item in result.value})
        self.assertNotIn("identifier", {item.kind for item in result.value})


if __name__ == "__main__":
    unittest.main()
