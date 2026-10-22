"""共享子树保持原有 JSON 校验、不可变性和稳定身份，不信任外部只读包装。"""
import json
from types import MappingProxyType
import unittest

from kb_scanner.core import stable_id
from kb_scanner.core.metadata import (freeze_json, freeze_metadata,
    freeze_shared_metadata, to_json_compatible, _SharedJsonMapping)


class SharedMetadataTests(unittest.TestCase):
    def test_non_mapping_metadata_is_rejected_at_runtime(self):
        for value in ("metadata", 1, True, [1], ("entry",)):
            for constructor in (freeze_metadata, freeze_shared_metadata):
                with self.subTest(value=value, constructor=constructor.__name__):
                    with self.assertRaisesRegex(TypeError, "metadata must be a mapping"):
                        constructor(value)
        self.assertEqual({}, freeze_metadata(None))
        self.assertEqual({}, freeze_metadata({}))

    def test_deep_isolation_identity_and_serialized_bytes(self):
        raw = {"records": [{"text": "中文", "span": [1, 2, 3, 4]}], "count": 1}
        expected = freeze_metadata(raw)
        shared = freeze_shared_metadata(raw)
        self.assertEqual(expected, shared)
        self.assertEqual(repr(expected), repr(shared))
        self.assertEqual(list(expected), list(shared))
        self.assertEqual(len(expected), len(shared))
        self.assertEqual(1, shared.get("count"))
        self.assertEqual(7, shared.get("missing", 7))
        self.assertIs(shared, freeze_json(shared))
        self.assertIs(shared, freeze_metadata({"usage": shared})["usage"])
        self.assertEqual(stable_id("metadata", expected), stable_id("metadata", shared))
        self.assertEqual(json.dumps(to_json_compatible(expected)), json.dumps(to_json_compatible(shared)))
        raw["records"][0]["text"] = "changed"
        raw["records"].append({})
        self.assertEqual(expected, shared)
        with self.assertRaises(TypeError):
            shared["records"][0]["text"] = "changed"
        with self.assertRaises(TypeError):
            shared._values = {}
        with self.assertRaises(TypeError):
            del shared._values
        with self.assertRaises(TypeError):
            shared.__init__({})
        self.assertEqual({}, freeze_shared_metadata({}))

    def test_external_proxy_and_subclass_are_not_trusted(self):
        raw = {"nested": [1]}
        copied = freeze_json(MappingProxyType(raw))
        raw["nested"].append(2)
        self.assertEqual((1,), copied["nested"])
        class Derived(_SharedJsonMapping):
            def items(self):
                return (("bad", object()),)
        with self.assertRaises(TypeError):
            freeze_json(Derived({}))

    def test_invalid_json_still_rejected(self):
        for raw in ({1: "bad"}, {"v": float("nan")}, {"v": float("inf")},
                    {"v": object()}, {"v": b"bytes"}, {"v": {2: 1}}):
            for constructor in (freeze_shared_metadata, freeze_metadata):
                with self.subTest(raw=repr(raw), constructor=constructor.__name__):
                    with self.assertRaises(TypeError):
                        constructor(MappingProxyType(raw))
