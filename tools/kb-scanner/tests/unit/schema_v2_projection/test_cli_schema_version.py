from __future__ import annotations

import argparse
import unittest

from kb_scanner.adapters.cli import scan_request_from_namespace
from kb_scanner.core import ScanRequest


def namespace(**overrides):
    values = dict(input="in", rules="rules", output="out", language="c,cpp", exclude=".git", exclude_path=[], format="json", context_infer="auto", target_arch="riscv64", include_inactive_branches=False, no_comment_hints=False, compile_commands=None, locale="zh-CN", schema_version="2.0")
    values.update(overrides)
    return argparse.Namespace(**values)


class CliSchemaVersionTests(unittest.TestCase):
    def test_adapter_defaults_and_preserves_explicit_version(self):
        self.assertEqual("2.0", scan_request_from_namespace(namespace()).schema_version)
        self.assertEqual("1.0", scan_request_from_namespace(namespace(schema_version="1.0")).schema_version)
        delattr((legacy := namespace()), "schema_version")
        self.assertEqual("2.0", scan_request_from_namespace(legacy).schema_version)

    def test_request_rejects_unsupported_version_before_pipeline(self):
        with self.assertRaises(ValueError):
            ScanRequest("in", "rules", "out", schema_version="3.0")
