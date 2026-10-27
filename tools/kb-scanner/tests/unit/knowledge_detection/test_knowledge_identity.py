from __future__ import annotations

import unittest

from kb_scanner.knowledge.identity import (
    candidate_id,
    canonicalize_fact_value,
    content_sha256,
    curated_entry_id,
    knowledge_entry_id,
    knowledge_snapshot_id,
    knowledge_source_id,
    knowledge_reference_id,
    logical_path,
)


class KnowledgeIdentityTests(unittest.TestCase):
    def test_kind_specific_canonicalization_preserves_symbol_case(self) -> None:
        self.assertEqual(canonicalize_fact_value("headers", ' <x86\\foo.h> '), "x86/foo.h")
        self.assertEqual(canonicalize_fact_value("intrinsics", " _MM_X "), "_MM_X")
        self.assertNotEqual(
            knowledge_entry_id("intrinsics", "x86", "_MM_X"),
            knowledge_entry_id("intrinsics", "x86", "_mm_x"),
        )
        self.assertEqual(canonicalize_fact_value("comment", " a\n  b "), "a b")
        self.assertEqual(canonicalize_fact_value("assemblyInstructions", " PAUSE "), "pause")
        self.assertEqual(canonicalize_fact_value("registerNames", " XMM0 "), "xmm0")
        self.assertEqual(canonicalize_fact_value("architectureAliases", " X86-64 "), "x86-64")
        self.assertEqual(canonicalize_fact_value("cpuPlatformApis", " __CPUID "), "__CPUID")
        with self.assertRaises(ValueError):
            canonicalize_fact_value("", "x")
        with self.assertRaises(ValueError):
            canonicalize_fact_value("headers", " ")

    def test_logical_paths_and_source_ids_are_cross_platform_stable(self) -> None:
        digest = "a" * 64
        self.assertEqual(logical_path("generated\\clang.json"), "generated/clang.json")
        self.assertEqual(
            knowledge_source_id("clang", "generated\\clang.json", digest),
            knowledge_source_id("clang", "generated/clang.json", digest),
        )
        self.assertEqual(
            knowledge_source_id(
                "clang-x86-entries", "generated/clang-x86-entries.json",
                "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7",
            ),
            "789e09ea01e7a003765e378288fd2ff10124e6a46458d006d3493806f9be37bb",
        )
        self.assertEqual(
            knowledge_source_id(
                "clang-x86-entries", "generated/clang-x86-entries.json",
                "947e2ad0797248f8179f2bc29f4e7e0591bd7a14801ba819c9e56d31926e9a8c",
            ),
            "7f02d7f6c245f6c9d6e917d7f3ab0171107e0b8de4be9d6582a1e9675144b066",
        )
        self.assertEqual(
            knowledge_entry_id("headers", "x86", "immintrin.h"),
            "a24d20b21942e6f6ef333716ff20cdb58422d0a1e2edc99374f70002c71554e8",
        )
        for value in ("/absolute.json", "../escape.json"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                logical_path(value)

    def test_hash_and_snapshot_identity_are_deterministic_and_order_independent(self) -> None:
        self.assertEqual(content_sha256(b"x"), content_sha256(b"x"))
        sources = (knowledge_source_id("a", "a.json", "a" * 64), knowledge_source_id("b", "b.json", "b" * 64))
        entries = (knowledge_entry_id("headers", "x86", "a.h"), knowledge_entry_id("headers", "x86", "b.h"))
        self.assertEqual(
            knowledge_snapshot_id("c", "1", sources, entries),
            knowledge_snapshot_id("c", "1", tuple(reversed(sources)), tuple(reversed(entries))),
        )
        self.assertEqual(
            curated_entry_id("targetFeatures", "x86", " AVX2 "),
            knowledge_entry_id("targetFeatures", "x86", "avx2"),
        )
        self.assertEqual(candidate_id("api", " x "), candidate_id("api", "x"))
        self.assertEqual(
            knowledge_reference_id("https://example.test", "a" * 40, "section", "b" * 64),
            knowledge_reference_id("https://example.test", "a" * 40, "section", "b" * 64),
        )


if __name__ == "__main__":
    unittest.main()
