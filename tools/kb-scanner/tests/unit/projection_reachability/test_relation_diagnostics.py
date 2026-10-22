from __future__ import annotations

import unittest

from kb_scanner.analyzers.relation_diagnostics import relation_diagnostic
from kb_scanner.core import DiagnosticSeverity, Entity, Evidence, SourceLocation, SourceSpan, stable_id


class RelationDiagnosticTests(unittest.TestCase):
    def test_structured_relation_diagnostic_preserves_reason_location_and_reference(self) -> None:
        source = Entity(stable_id("source"), "source_file", "a.c")
        span = SourceSpan(SourceLocation("a.c", 2, 3), SourceLocation("a.c", 2, 4))
        evidence = Evidence(stable_id("evidence"), "include", source.id, "x.h", "unit", "ast", "high", span)
        item = relation_diagnostic("graph.include-unresolved", evidence, "unresolved-include", "includes")
        self.assertEqual(DiagnosticSeverity.WARNING, item.severity)
        self.assertEqual(evidence.id, item.details["evidenceId"])
        self.assertEqual("includes", item.details["relationKind"])
        self.assertEqual(span.start, item.location)
        error = relation_diagnostic("x", evidence, "failed", "calls", severity=DiagnosticSeverity.ERROR)
        self.assertEqual(DiagnosticSeverity.ERROR, error.severity)


if __name__ == "__main__":
    unittest.main()
