from pathlib import Path
import unittest
from unittest.mock import patch

from kb_scanner.core import StageResult, CompletionStatus
from kb_scanner.normalization.cpp import CppEvidenceNormalizer
from kb_scanner.pipeline.composite import _merge_normalized
from .support import make_context
from .test_macro_index import macro_snapshot


class CompositeIndexTests(unittest.TestCase):
    def test_merge_does_not_rebuild_global_evidence_set_per_fact(self):
        snapshot = CppEvidenceNormalizer().normalize(make_context(Path("/tmp")), macro_snapshot(100)).value
        enumerations = []
        class CountingSet(set):
            def issubset(self, other):
                if isinstance(other, dict):
                    enumerations.append(len(other))
                return super().issubset(other)
        expected = _merge_normalized(StageResult(snapshot))
        with patch("kb_scanner.pipeline.composite.set", CountingSet, create=True):
            actual = _merge_normalized(StageResult(snapshot))
        self.assertEqual(expected, actual)
        self.assertEqual(CompletionStatus.COMPLETE, actual.status)
        self.assertLessEqual(sum(enumerations), len(snapshot.evidence))
