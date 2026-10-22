from __future__ import annotations

import unittest

from kb_scanner.core import KnowledgeEntry, KnowledgeSnapshot, KnowledgeSource, NormalizedFact, stable_id
from kb_scanner.detectors.definitions import DetectorDefinition
from kb_scanner.detectors.matchers import KnowledgeIndex, match_fact


def knowledge() -> KnowledgeSnapshot:
    source = KnowledgeSource(stable_id("source"), "compiler", "generated-json", "facts.json", "a" * 64)
    entries = tuple(
        KnowledgeEntry(stable_id("entry", kind, value), kind, "x86", value, (source.id,))
        for kind, value in (
            ("headers", "immintrin.h"), ("intrinsics", "_mm_add_ps"), ("builtins", "__builtin_ia32_pause"),
            ("vectorTypes", "__m128"), ("platformMacros", "__AVX__"), ("compilerFlags", "-mavx2"),
            ("assemblyInstructions", "pause"), ("registerNames", "rax"), ("cpuPlatformApis", "__cpuid"),
            ("targetFeatures", "avx2"), ("architectureAliases", "i386"),
            ("vectorWidthMarkers", "vector_size(16)"),
        )
    )
    return KnowledgeSnapshot(stable_id("snapshot"), "1", (source,), entries)


def fact(kind: str, value: str) -> NormalizedFact:
    return NormalizedFact(stable_id("fact", kind, value), kind, stable_id("subject"), value, "scope", (stable_id("evidence", kind, value),))


class LocalMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = KnowledgeIndex(knowledge())

    def test_exact_token_and_flag_matchers_use_generated_facts(self) -> None:
        cases = (
            (DetectorDefinition("h", "include", ("headers",), "o", "exact"), fact("include", "immintrin.h")),
            (DetectorDefinition("i", "symbol", ("intrinsics",), "o", "exact"), fact("symbol", "_mm_add_ps")),
            (DetectorDefinition("b", "symbol", ("builtins",), "o", "exact"), fact("symbol", "__builtin_ia32_pause")),
            (DetectorDefinition("v", "type", ("vectorTypes",), "o", "token"), fact("type", "const __m128 *")),
            (DetectorDefinition("m", "preprocessor", ("platformMacros",), "o", "token"), fact("preprocessor", "defined(__AVX__)")),
            (DetectorDefinition("f", "compiler_argument", ("compilerFlags",), "o", "flag"), fact("compiler_argument", "-mavx2=yes")),
        )
        for definition, item in cases:
            with self.subTest(definition=definition.detector_id):
                result = match_fact(definition, item, self.index)
                self.assertEqual(result.status, "confirmed_local")
                self.assertEqual(len(result.knowledge_ids), 1)

    def test_token_boundaries_wrong_kind_and_near_misses_do_not_match(self) -> None:
        token = DetectorDefinition("v", "type", ("vectorTypes",), "o", "token")
        self.assertIsNone(match_fact(token, fact("type", "my__m128suffix"), self.index))
        self.assertIsNone(match_fact(token, fact("symbol", "__m128"), self.index))
        exact = DetectorDefinition("h", "include", ("headers",), "o", "exact")
        self.assertIsNone(match_fact(exact, fact("include", "other.h"), self.index))

    def test_structural_comment_and_architecture_candidate_have_no_fake_knowledge(self) -> None:
        cases = (
            (DetectorDefinition("s", "inline_asm", (), "o", "structural", "candidate"), fact("inline_asm", "asm(pause)"), "candidate"),
            (DetectorDefinition("c", "comment", (), "o", "comment_hint", "hint"), fact("comment", "AVX optimized"), "hint"),
            (DetectorDefinition("a", "macro", (), "o", "architecture_candidate", "candidate"), fact("macro", "LOCAL_X86_PATH"), "candidate"),
        )
        for definition, item, status in cases:
            result = match_fact(definition, item, self.index)
            self.assertEqual(result.status, status)
            self.assertEqual(result.knowledge_ids, ())
        self.assertIsNone(match_fact(cases[1][0], fact("comment", "portable implementation"), self.index))
        self.assertIsNone(match_fact(cases[2][0], fact("macro", "LOCAL_PORTABLE_PATH"), self.index))

    def test_new_knowledge_matchers_observe_boundaries_case_and_vector_spacing(self) -> None:
        cases = (
            (DetectorDefinition("asm", "inline_asm", ("assemblyInstructions",), "o", "token"), fact("inline_asm", 'asm("PAUSE %RAX")')),
            (DetectorDefinition("reg", "inline_asm", ("registerNames",), "o", "token"), fact("inline_asm", 'asm("pause %RAX")')),
            (DetectorDefinition("api", "symbol", ("cpuPlatformApis",), "o", "exact"), fact("symbol", "__cpuid")),
            (DetectorDefinition("target", "declaration_attribute", ("targetFeatures",), "o", "token"), fact("declaration_attribute", 'target("AVX2")')),
            (
                DetectorDefinition("alias", "declaration_attribute", ("architectureAliases",), "o", "token"),
                fact("declaration_attribute", 'target("arch=I386")'),
            ),
            (
                DetectorDefinition("width", "declaration_attribute", ("vectorWidthMarkers",), "o", "token", "candidate"),
                fact("declaration_attribute", "__attribute__((vector_size ( 16 )))"),
            ),
        )
        for definition, item in cases:
            with self.subTest(definition=definition.detector_id):
                self.assertIsNotNone(match_fact(definition, item, self.index))
        api = cases[2][0]
        width = cases[-1][0]
        self.assertIsNone(match_fact(api, fact("symbol", "__cpuid_helper"), self.index))
        self.assertIsNone(match_fact(width, fact("declaration_attribute", "aligned(16)"), self.index))


if __name__ == "__main__":
    unittest.main()
