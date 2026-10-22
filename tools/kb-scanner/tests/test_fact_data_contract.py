from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "rulesets" / "riscv-porting" / "generated"
CATEGORIES = ("headers", "intrinsics", "builtins", "vectorTypes", "platformMacros", "compilerFlags")
BASELINE = {
    "clang-x86-entries.json": {
        "sha256": "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7",
        "counts": (125, 7563, 1993, 10, 5, 216),
        "source": {
            "name": "LLVM Clang builtin headers",
            "api": "https://api.github.com/repos/llvm/llvm-project/contents/clang/lib/Headers?ref=main",
            "rawBase": "https://raw.githubusercontent.com/llvm/llvm-project/main/clang/lib/Headers",
            "options": "https://github.com/llvm/llvm-project/blob/main/clang/include/clang/Options/Options.td",
        },
    },
    "gcc-x86-entries.json": {
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
        for filename, expected in BASELINE.items():
            with self.subTest(filename=filename):
                raw = (GENERATED / filename).read_bytes()
                payload = json.loads(raw)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
                self.assertEqual(payload["source"], expected["source"])
                self.assertEqual(tuple(len(payload[name]) for name in CATEGORIES), expected["counts"])

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
