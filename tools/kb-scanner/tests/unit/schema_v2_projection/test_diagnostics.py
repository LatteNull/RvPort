from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.core import Diagnostic, DiagnosticSeverity, SourceLocation
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.diagnostics import V2DiagnosticProjector


class DiagnosticProjectionTests(unittest.TestCase):
    def test_only_complete_aggregation_key_merges_and_preserves_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.c").write_text("token\n", encoding="utf-8")
            location = SourceLocation("a.c", 1, 1)
            first = Diagnostic("x", "analysis", DiagnosticSeverity.WARNING, "same", location, "p", {"reason": "missing-reference", "evidenceId": "e1"})
            second = Diagnostic("x", "analysis", DiagnosticSeverity.WARNING, "same", location, "p", {"reason": "missing-reference", "evidenceId": "e2"})
            other = Diagnostic("x", "frontend", DiagnosticSeverity.ERROR, "different", producer="p", affects_exit_code=True)
            result = V2DiagnosticProjector(SourceContextProjector(root)).project((first, second, other))
            self.assertEqual(2, len(result))
            merged = next(item for item in result if item.stage == "analysis")
            self.assertEqual(2, merged.count)
            self.assertEqual({"e1", "e2"}, {item.id for item in merged.refs})
            self.assertIsNotNone(merged.representativeLocation)
            self.assertEqual("unknown", next(item for item in result if item.stage == "frontend").status)

    def test_unknown_reason_is_normalized(self):
        with tempfile.TemporaryDirectory() as temp:
            item = Diagnostic("x", "s", DiagnosticSeverity.INFO, "m", details={"reason": "free text"})
            result = V2DiagnosticProjector(SourceContextProjector(Path(temp))).project((item,))
            self.assertEqual(("missing_input",), result[0].reasonCodes)
