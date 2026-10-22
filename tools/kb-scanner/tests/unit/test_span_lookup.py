"""纯 DTO 对照原包含判定，不依赖 parser。"""
from dataclasses import replace
import unittest
from kb_scanner.analyzers.span_lookup import SpanLookup
from kb_scanner.analyzers.evidence_graph import _contains
from kb_scanner.core import SourceLocation, SourceSpan
from tests.unit.evidence_graph.support import evidence, file


class SpanLookupTests(unittest.TestCase):
    def test_nested_adjacent_equal_missing_foreign_and_reverse_order(self):
        source, foreign = file('a.c'), file('b.c')
        rows = [evidence(source, 'selection_condition', str(i), i+1, end_line=i+3) for i in range(30)]
        rows += [evidence(source, 'selection_condition', 'outer', 1, end_line=40),
                 evidence(foreign, 'selection_condition', 'other', 1, end_line=40),
                 replace(rows[0], location=None)]
        probes = [evidence(source, 'enum_member_reference', str(i), i+1) for i in range(43)]
        probes += [replace(probes[0], location=None), evidence(file('c.c'), 'enum_member_reference', 'x', 1)]
        probes.append(replace(probes[0], location=SourceSpan(SourceLocation('a.c', 1), SourceLocation('a.c', 2))))
        for values in (rows, list(reversed(rows))):
            lookup = SpanLookup(values)
            for probe in probes:
                self.assertEqual(tuple(row for row in values if row.subject_id == probe.subject_id
                    and _contains(row.location, probe.location)), lookup.containing(probe))
        self.assertEqual((), SpanLookup(()).containing(probes[0]))
