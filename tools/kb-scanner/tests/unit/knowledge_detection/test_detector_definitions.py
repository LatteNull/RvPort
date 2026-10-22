from __future__ import annotations

import unittest

from kb_scanner.detectors.definitions import DEFAULT_DEFINITIONS, DetectorDefinition, build_registry


class DetectorDefinitionTests(unittest.TestCase):
    def test_default_registry_is_sorted_immutable_and_code_owned(self) -> None:
        self.assertEqual(tuple(DEFAULT_DEFINITIONS), tuple(sorted(DEFAULT_DEFINITIONS)))
        self.assertTrue(DEFAULT_DEFINITIONS)
        with self.assertRaises(TypeError):
            DEFAULT_DEFINITIONS["x"] = next(iter(DEFAULT_DEFINITIONS.values()))  # type: ignore[index]
        kinds = {kind for item in DEFAULT_DEFINITIONS.values() for kind in item.knowledge_kinds}
        self.assertTrue({
            "assemblyInstructions", "registerNames", "cpuPlatformApis", "targetFeatures",
            "architectureAliases", "vectorWidthMarkers",
        } <= kinds)
        vector = DEFAULT_DEFINITIONS["C_CPP.MIGRATION.FIXED_VECTOR_WIDTH"]
        self.assertEqual(vector.status, "candidate")

    def test_registry_rejects_duplicate_ids(self) -> None:
        item = DetectorDefinition("d", "include", ("headers",), "o", "exact")
        with self.assertRaises(ValueError):
            build_registry((item, item))

    def test_definition_rejects_empty_unknown_and_inconsistent_bindings(self) -> None:
        cases = (
            ("", "include", ("headers",), "o", "exact"),
            ("d", "unknown", ("headers",), "o", "exact"),
            ("d", "include", ("headers",), "o", "unknown"),
            ("d", "include", (), "o", "exact"),
            ("d", "comment", ("headers",), "o", "comment_hint"),
        )
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                DetectorDefinition(*args)

    def test_knowledge_kinds_are_deduplicated_and_sorted(self) -> None:
        item = DetectorDefinition("d", "symbol", ("intrinsics", "builtins", "intrinsics"), "o", "exact")
        self.assertEqual(item.knowledge_kinds, ("builtins", "intrinsics"))


if __name__ == "__main__":
    unittest.main()
