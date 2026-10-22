from __future__ import annotations

import ast
import hashlib
import inspect
import unittest
from pathlib import Path

import kb_scanner.frontends.cpp as public_frontend


ROOT = Path(__file__).resolve().parents[1]
FORMAL_PACKAGE = ROOT / "kb_scanner" / "frontends"
# 原归档不随开源仓库交付；摘要从原归档逐文件核对后冻结，继续保护保留实现的字节。
LEGACY_FILE_HASHES = {
    "compile_commands.py": "5b3c61ce0b6e83921eb5a501b7b4375894faff48196a39edbd9f456c572f72f1",
    "cpp_frontend.py": "cb3033b848b7b56e71eaff4438423146828963ef2df053d07897124489974927",
    "models.py": "1f5ffa70094424ade923dbd9346630d448445f0204e9c7bb9fbc3e387d95b2e8",
    "rules.py": "cb1902f4fc8ca329cb4d3d23ef09d1b6899b3380383a479902704e192c18c7f4",
    "report.py": "2e9be6a9bf04692375b712e5d4e062ba1546dbadb795feaa7142a518b5cb4450"
}
EXPECTED_FACT_HASHES = {
    "clang-x86-entries.json": "adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7",
    "gcc-x86-entries.json": "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191",
}


class FormalFrontendBoundaryTests(unittest.TestCase):
    def test_legacy_implementation_files_keep_verified_archive_hashes(self) -> None:
        for relative_path, expected_hash in LEGACY_FILE_HASHES.items():
            with self.subTest(relative_path=relative_path):
                current = ROOT / "kb_scanner" / relative_path
                self.assertEqual(hashlib.sha256(current.read_bytes()).hexdigest(), expected_hash)

    def test_formal_package_does_not_import_legacy_or_technology_modules(self) -> None:
        forbidden_modules = {
            "kb_scanner.technology",
            "kb_scanner.models",
            "kb_scanner.cpp_frontend",
            "kb_scanner.compile_commands",
            "kb_scanner.rules",
            "kb_scanner.report",
        }
        for path in FORMAL_PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for imported in imports:
                with self.subTest(path=path.name, imported=imported):
                    self.assertFalse(any(imported == token or imported.startswith(f"{token}.") for token in forbidden_modules))

    def test_public_api_exposes_scanner_types_not_parser_objects(self) -> None:
        forbidden_type_modules = ("tree_sitter", "clang.cindex")
        for name in public_frontend.__all__:
            value = getattr(public_frontend, name)
            with self.subTest(name=name):
                self.assertFalse(getattr(value, "__module__", "").startswith(forbidden_type_modules))
                if callable(value):
                    for parameter in inspect.signature(value).parameters.values():
                        annotation_module = getattr(parameter.annotation, "__module__", "")
                        self.assertFalse(annotation_module.startswith(forbidden_type_modules))

    def test_existing_compiler_fact_files_keep_exact_hashes(self) -> None:
        generated = ROOT / "rulesets" / "riscv-porting" / "generated"
        for filename, expected_hash in EXPECTED_FACT_HASHES.items():
            with self.subTest(filename=filename):
                self.assertEqual(hashlib.sha256((generated / filename).read_bytes()).hexdigest(), expected_hash)

    def test_formal_frontend_has_no_knowledge_detection_or_reporting_dependency(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in FORMAL_PACKAGE.rglob("*.py"))
        for forbidden in (
            "generatedSet",
            "clang-x86-entries",
            "gcc-x86-entries",
            "Finding",
            "readiness",
            "evaluate_rules",
            "write_reports",
            "subprocess",
            "os.system",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
