from __future__ import annotations

import json
import unittest
from pathlib import Path
from tests.source_baseline import validate_fact_file


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "rulesets" / "riscv-porting" / "generated"
CATEGORIES = ("headers", "intrinsics", "builtins", "vectorTypes", "platformMacros", "compilerFlags")
BASELINE = {
    "clang-x86-entries.json": {
        "bytes": 293356,
        "sha256": "947e2ad0797248f8179f2bc29f4e7e0591bd7a14801ba819c9e56d31926e9a8c",
        "counts": (125, 7563, 1993, 10, 5, 216),
        "source": {
            "name": "LLVM Clang builtin headers",
            "api": "https://api.github.com/repos/llvm/llvm-project/contents/clang/lib/Headers?ref=main",
            "rawBase": "https://raw.githubusercontent.com/llvm/llvm-project/main/clang/lib/Headers",
            "options": "https://github.com/llvm/llvm-project/blob/main/clang/include/clang/Options/Options.td",
        },
    },
    "gcc-x86-entries.json": {
        "bytes": 350593,
        "sha256": "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191",
        "counts": (120, 7602, 3438, 10, 47, 225),
        "source": {
            "name": "GCC i386 backend and intrinsic headers",
            "path": "vendor/gcc/gcc/config/i386",
        },
    },
}


class FactDataContractTests(unittest.TestCase):
    def test_compiler_fact_files_remain_byte_and_shape_compatible(self) -> None:
        manifest = json.loads((GENERATED.parent / "knowledge-manifest.json").read_text())
        declared = {item["path"]: item["sha256"] for item in manifest["sources"]}
        for filename, expected in BASELINE.items():
            with self.subTest(filename=filename):
                validate_fact_file(GENERATED / filename,
                                   dict(expected, counts=dict(zip(CATEGORIES, expected["counts"]))),
                                   declared[f"generated/{filename}"])

    def test_generated_set_rules_still_reference_all_six_fact_categories(self) -> None:
        import yaml

        rule_root = GENERATED.parent / "rules"
        generated_sets = set()
        for path in rule_root.rglob("*.yaml"):
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            for matcher in payload.get("match", {}).get("any", []):
                for value in matcher.values():
                    if isinstance(value, dict) and "generatedSet" in value:
                        generated_sets.add(value["generatedSet"])
        self.assertEqual(generated_sets, set(CATEGORIES))


if __name__ == "__main__":
    unittest.main()
