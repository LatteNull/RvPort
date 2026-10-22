from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from kb_scanner.projection.versioned import VersionedReportProjector
from .support import context


class FakeProjector:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def project(self, context, *snapshots):
        self.calls.append((context, snapshots))
        return self.value


class VersionSelectorTests(unittest.TestCase):
    def test_explicit_v1_and_default_v2_delegate_once(self):
        with tempfile.TemporaryDirectory() as temp:
            v1, v2 = FakeProjector("v1"), FakeProjector("v2")
            selector = VersionedReportProjector(v1, v2)
            self.assertEqual("v1", selector.project(context(Path(temp), version="1.0"), "snapshot"))
            self.assertEqual("v2", selector.project(context(Path(temp)), "snapshot"))
            self.assertEqual((1, 1), (len(v1.calls), len(v2.calls)))

    def test_v2_failure_is_not_sent_to_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            v1, v2 = FakeProjector("v1"), FakeProjector("failed")
            self.assertEqual("failed", VersionedReportProjector(v1, v2).project(context(Path(temp)), "snapshot"))
            self.assertFalse(v1.calls)

    def test_unsupported_context_is_rejected(self):
        with self.assertRaises(ValueError):
            VersionedReportProjector(FakeProjector("v1"), FakeProjector("v2")).project(SimpleNamespace(schema_version="3.0"))
