from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = {
    "kb_scanner.adapters.legacy",
    "kb_scanner.compile_commands",
    "kb_scanner.cpp_frontend",
    "kb_scanner.models",
    "kb_scanner.rules",
    "kb_scanner.report",
    "yaml",
}


class LegacyImportBoundaryTests(unittest.TestCase):
    def test_new_pipeline_modules_do_not_import_legacy_runtime(self) -> None:
        paths = [ROOT / "kb_scanner" / "normalization" / "cpp.py"]
        for folder in ("graph", "analyzers"):
            root = ROOT / "kb_scanner" / folder
            if root.exists():
                paths.extend(root.rglob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            for name in imported:
                with self.subTest(path=path.name, import_name=name):
                    self.assertFalse(any(name == item or name.startswith(f"{item}.") for item in FORBIDDEN))


if __name__ == "__main__":
    unittest.main()
