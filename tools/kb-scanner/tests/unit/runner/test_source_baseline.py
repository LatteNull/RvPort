"""用最小事实样例验证字节冻结失败路径。"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests.source_baseline import validate_fact_file


class SourceBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "facts.json"
        self.data = {"source": {"name": "fixture"}, "headers": ["x.h"], "intrinsics": []}
        self.raw = (json.dumps(self.data, indent=2) + "\n").encode()
        self.expected = self.baseline(self.raw)
        self.path.write_bytes(self.raw)

    def baseline(self, raw):
        return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "counts": {"headers": 1, "intrinsics": 0}, "source": {"name": "fixture"}}

    def validate(self, expected=None, manifest=None):
        expected = self.expected if expected is None else expected
        return validate_fact_file(self.path, expected, expected["sha256"] if manifest is None else manifest)

    def test_lf_bytes_and_empty_category_are_accepted(self):
        self.assertEqual(self.data, self.validate())
        self.assertEqual(self.raw, self.path.read_bytes())

    def test_crlf_and_lone_cr_are_rejected_without_rewriting(self):
        for raw in (self.raw.replace(b"\n", b"\r\n"), self.raw + b"\r"):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, r"facts.json.*CR/CRLF"):
                    self.validate(self.baseline(raw))
                self.assertEqual(raw, self.path.read_bytes())

    def test_missing_empty_and_truncated_files_fail(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "无法读取"):
            self.validate()
        for raw in (b"", self.raw[:-1]):
            self.path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "字节数不一致"):
                self.validate()

    def test_same_length_content_tampering_and_manifest_mismatch_fail(self):
        self.path.write_bytes(self.raw.replace(b"x.h", b"y.h"))
        with self.assertRaisesRegex(ValueError, "SHA-256 不一致"):
            self.validate()
        self.path.write_bytes(self.raw)
        with self.assertRaisesRegex(ValueError, "knowledge-manifest"):
            self.validate(manifest="0" * 64)

    def test_invalid_json_encoding_and_non_object_fail(self):
        for raw, reason in ((b"{", "JSON 无效"), (b"\xff", "JSON 无效"), (b"[]", "必须是对象")):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate(self.baseline(raw))

    def test_source_count_missing_category_and_wrong_type_fail(self):
        for field, value, reason in (("source", {}, "来源"), ("headers", [], "分类"),
                                     ("headers", "x.h", "分类"), ("intrinsics", None, "分类")):
            with self.subTest(field=field, value=value):
                payload = dict(self.data, **{field: value})
                if value is None:
                    del payload[field]
                raw = json.dumps(payload).encode()
                self.path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate(self.baseline(raw))
