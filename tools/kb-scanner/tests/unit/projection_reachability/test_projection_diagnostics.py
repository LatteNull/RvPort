from __future__ import annotations

import unittest

from kb_scanner.core import Diagnostic, DiagnosticSeverity, SourceLocation
from kb_scanner.projection.diagnostics import aggregate_diagnostics
from kb_scanner.projection.renderers import render_html, render_log
from tests.unit.compatible_cutover.support import payload


class ProjectionDiagnosticTests(unittest.TestCase):
    def test_aggregates_same_reason_and_preserves_locations_and_references(self) -> None:
        first = Diagnostic("graph.x", "graph", DiagnosticSeverity.WARNING, "same <message>", SourceLocation("a.c", 1, 2), details={"reason": "r", "relationKind": "includes", "evidenceId": "a" * 64})
        second = Diagnostic("graph.x", "graph", DiagnosticSeverity.WARNING, "same <message>", SourceLocation("b.c", 2, 3), details={"reason": "r", "relationKind": "includes", "evidenceIds": ("b" * 64,)})
        output = aggregate_diagnostics((second, first))
        self.assertEqual(1, len(output))
        self.assertIn('"count":2', output[0])
        self.assertIn("a.c:1:2", output[0])
        self.assertIn("b" * 64, output[0])
        value = payload(); value["diagnostics"] = output
        self.assertIn("&lt;message&gt;", render_html(value).decode())
        self.assertIn('"count":2', render_log(value).decode())

    def test_keeps_different_groups_and_single_message_compatible(self) -> None:
        one = Diagnostic("a", "x", DiagnosticSeverity.INFO, "one", details={"reason": "r"})
        two = Diagnostic("a", "x", DiagnosticSeverity.ERROR, "one", details={"reason": "r"})
        three = Diagnostic("b", "x", DiagnosticSeverity.INFO, "three")
        output = aggregate_diagnostics((three, two, one))
        self.assertEqual(3, len(output))
        self.assertIn("three", output)
        self.assertEqual([], aggregate_diagnostics(()))


if __name__ == "__main__":
    unittest.main()
