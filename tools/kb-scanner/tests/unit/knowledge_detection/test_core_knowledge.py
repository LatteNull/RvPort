from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from kb_scanner.core import KnowledgeEntry, KnowledgeSource, stable_id
from kb_scanner.knowledge.identity import knowledge_entry_id, knowledge_source_id


HASH = "a" * 64


class CoreKnowledgeTests(unittest.TestCase):
    def test_source_is_frozen_slotted_normalized_and_json_safe(self) -> None:
        item = KnowledgeSource(
            knowledge_source_id("clang", "generated\\clang.json", HASH),
            "clang",
            "generated-json",
            "generated\\clang.json",
            HASH,
            {"origin": {"name": "LLVM"}},
        )
        self.assertEqual(item.logical_path, "generated/clang.json")
        self.assertFalse(hasattr(item, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            item.kind = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            item.metadata["x"] = 1  # type: ignore[index]

    def test_source_rejects_invalid_identity_path_hash_and_metadata(self) -> None:
        valid = dict(id=stable_id("source"), source_id="s", kind="generated", logical_path="a.json", sha256=HASH)
        for changes in (
            {"id": "bad"}, {"source_id": ""}, {"logical_path": "/a.json"},
            {"logical_path": "../a.json"}, {"sha256": "A" * 64}, {"metadata": {"bad": object()}},
        ):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                KnowledgeSource(**(valid | changes))

    def test_entry_deduplicates_and_sorts_sources_without_affecting_identity(self) -> None:
        first = stable_id("source", 1)
        second = stable_id("source", 2)
        identity = knowledge_entry_id("headers", "x86", "immintrin.h")
        item = KnowledgeEntry(identity, "headers", "x86", "immintrin.h", (second, first, second), {"v": 1})
        self.assertEqual(item.source_ids, tuple(sorted((first, second))))
        self.assertEqual(identity, knowledge_entry_id("headers", "x86", "immintrin.h"))

    def test_entry_rejects_empty_fields_missing_or_invalid_sources(self) -> None:
        identity = stable_id("entry")
        for args in (
            (identity, "", "x86", "v", (stable_id("s"),)),
            (identity, "headers", "x86", "", (stable_id("s"),)),
            (identity, "headers", "x86", "v", ()),
            (identity, "headers", "x86", "v", ("bad",)),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                KnowledgeEntry(*args)


if __name__ == "__main__":
    unittest.main()
