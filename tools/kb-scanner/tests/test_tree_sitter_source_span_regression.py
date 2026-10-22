from __future__ import annotations

import unittest
from pathlib import Path

from kb_scanner.core import CompletionStatus
from kb_scanner.frontends.cpp import TreeSitterCppAdapter, make_source_file_entity
from tests.unit.frontends.cpp.support import make_context


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "tests" / "fixtures" / "tree-sitter-regressions"


class TreeSitterSourceSpanRegressionTests(unittest.TestCase):
    def test_long_single_line_call_has_stable_project_relative_span(self) -> None:
        relative_path = "long-line-call.c"
        context = make_context(SOURCE_ROOT)
        entity = make_source_file_entity(relative_path, ("c",), context.scanner_version)
        result = TreeSitterCppAdapter().analyze_file(context, SOURCE_ROOT, relative_path, entity)

        self.assertEqual(result.status, CompletionStatus.COMPLETE)
        call = next(item for item in result.value if item.kind == "call_expression")
        source_line = (SOURCE_ROOT / relative_path).read_text(encoding="utf-8").splitlines()[3]
        self.assertEqual(call.value, "printf")
        self.assertEqual(call.location.start.path, relative_path)
        self.assertEqual(call.location.start.column, source_line.index("printf") + 1)
        self.assertEqual(call.location.end.column, source_line.index(";") + 1)
        self.assertGreater(call.location.end.column, 365)


if __name__ == "__main__":
    unittest.main()
