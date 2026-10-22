import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "main" / "resources" / "bitcode" / "produce_bitcode.py"
SPEC = importlib.util.spec_from_file_location("produce_bitcode", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IncludeSearchParsingTests(unittest.TestCase):
    def test_canonical_identity_matches_java_vector(self):
        vector = {
            "path": "src/目录/a.c",
            "profile": {"name": "source-preserving", "version": "1"},
            "capabilities": ["memory.fence", "fp.operations"],
        }
        self.assertEqual(
            MODULE.digest(vector),
            "4f3fa09da25853b5937198db216e813fbec940151f6f146fef0c0e575ed275ce",
        )

    def test_identity_ignores_excluded_fields_and_normalizes_array_order(self):
        left = {"stable": 1, "generated_at": "first", "values": ["乙", "甲"]}
        right = {"values": ["甲", "乙"], "generated_at": "second", "stable": 1}
        self.assertEqual(MODULE.digest(left, "generated_at"), MODULE.digest(right, "generated_at"))

    def test_language_standard_and_optimization_are_explicit(self):
        self.assertEqual(MODULE.language_standard(["-std=gnu11"], "c"), {
            "standard": "c11", "dialect": "gnu", "standard_source": "explicit",
            "standard_option": "-std=gnu11"})
        self.assertEqual(MODULE.language_standard(["-std=c++20"], "c++")["standard"], "c++20")
        self.assertEqual(MODULE.optimization(["-O2", "-O3"]), "O3")
        self.assertEqual(MODULE.optimization([]), "unknown")

    def test_legacy_aliases_and_compiler_default_are_not_silently_upgraded(self):
        self.assertEqual(MODULE.language_standard(["-std=c90"], "c")["standard"], "c89")
        self.assertEqual(MODULE.language_standard(["-std=gnu99"], "c")["dialect"], "gnu")
        self.assertEqual(MODULE.language_standard(["-std=c++03"], "c++")["standard"], "c++03")
        default = MODULE.language_standard([], "c")
        self.assertEqual(default["standard"], "compiler-default")
        self.assertEqual(default["dialect"], "compiler-default")
        self.assertEqual(default["standard_source"], "compiler-default")
        self.assertIsNone(default["standard_option"])

    def test_unknown_standard_is_marked_for_per_translation_unit_isolation(self):
        value = MODULE.language_standard(["-std=vendor-c"], "c")
        self.assertEqual(value["standard"], "unsupported")
        self.assertEqual(value["standard_option"], "-std=vendor-c")

    def test_current_clang_standards_are_preserved_without_upgrade(self):
        self.assertEqual(MODULE.language_standard(["-std=c23"], "c")["standard"], "c23")
        self.assertEqual(MODULE.language_standard(["-std=gnu++23"], "c++")["standard"], "c++23")

    def test_parses_existing_paths_and_removes_duplicates(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            stderr = "\n".join([
                'ignorable compiler output',
                '#include "..." search starts here:',
                '#include <...> search starts here:',
                f' {first}',
                f' {second} (framework directory)',
                f' {first}',
                'End of search list.',
            ])

            self.assertEqual(
                MODULE.parse_include_search(stderr),
                [str(Path(first).resolve()), str(Path(second).resolve())],
            )

    def test_ignores_relative_missing_and_unterminated_input(self):
        self.assertEqual(MODULE.parse_include_search("relative/path\nEnd of search list."), [])
        self.assertEqual(MODULE.parse_include_search("#include <...> search starts here:\n/missing/path"), [])

    def test_response_file_expansion_records_digest_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            response = root / "args.rsp"
            response.write_text("-DNAME=1 -I include", encoding="utf-8")
            inputs = {}
            self.assertEqual(
                MODULE.expand_response_files(["@args.rsp"], root, root, inputs),
                ["-DNAME=1", "-I", "include"],
            )
            self.assertEqual(len(inputs["args.rsp"]), 64)
            with self.assertRaises(ValueError):
                MODULE.expand_response_files(["@../outside.rsp"], root, root, {})

    def test_final_record_identity_deduplicates_converged_compile_contexts(self):
        records = []
        record_ids = set()
        first = {"record_id": "same", "status": "produced"}
        alias = {"record_id": "same", "status": "failed"}

        self.assertTrue(MODULE.append_unique_record(records, record_ids, first))
        self.assertFalse(MODULE.append_unique_record(records, record_ids, alias))
        self.assertEqual(records, [first])


if __name__ == "__main__":
    unittest.main()
