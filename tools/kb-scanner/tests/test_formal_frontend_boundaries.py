from __future__ import annotations

import ast
import hashlib
import inspect
import unittest
from pathlib import Path

import kb_scanner.frontends.cpp as public_frontend


ROOT = Path(__file__).resolve().parents[1]
FORMAL_PACKAGE = ROOT / "kb_scanner" / "frontends"
# 原归档不随开源仓库交付；旧摘要见 1f2746d。已证明旧字节仅有 CRLF 差异，当前冻结 Git LF 字节。
LEGACY_FILE_HASHES = {
    "compile_commands.py": "2bcc6adea3b7514e1e4e18f573c87a9d1d4aa6a85acb73375ddf8798a4569401",
    "cpp_frontend.py": "116715e4a556a0dfe7102d930034b1e5ddd7f5bf8c1d0641994dcfd0cdd696ae",
    "models.py": "7cd95199530d5d7cacbcaf5175e95482bb2173f0a70a378b64dc75a792b680cd",
    "rules.py": "1088f05168fedc53b6aa224967069c9cb221f2a30aa89e77e38924b04d78b24a",
    "report.py": "34d26b43ac373d73ffce8f43dbea00a49cb9887a1896c57ff593b15d0003a5bd"
}
EXPECTED_FACT_HASHES = {
    "clang-x86-entries.json": "947e2ad0797248f8179f2bc29f4e7e0591bd7a14801ba819c9e56d31926e9a8c",
    "gcc-x86-entries.json": "22d68c2ab3c8c40c8606451af2e5f493877661d031b6b2f379eff7886c23d191",
}


class FormalFrontendBoundaryTests(unittest.TestCase):
    def test_legacy_implementation_files_keep_verified_git_hashes(self) -> None:
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
