"""Real frontend/CLI family contract tests, excluded from isolated unit coverage."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kb_scanner.core import ScanRequest, StageResult
from kb_scanner.pipeline.default import create_default_application
from kb_scanner.projection.v2.families import NAMESPACE
from kb_scanner.projection.v2.models import SchemaV2Report
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureFamilyComponentTests(unittest.TestCase):
    def scan(self, files, version="2.0", family=True, exclude=()):
        with tempfile.TemporaryDirectory() as temporary:
            root, output = Path(temporary)/"input", Path(temporary)/"out"
            root.mkdir()
            for name, text in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            before = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob("*") if p.is_file()}
            app = create_default_application()
            with patch("subprocess.run", side_effect=AssertionError("project execution forbidden")):
                if family:
                    result = app.run(ScanRequest(str(root), str(ROOT/"rulesets/riscv-porting"), str(output), schema_version=version, exclude_paths=exclude))
                else:
                    with patch("kb_scanner.analyzers.architecture_family.ArchitectureFamilyAnalyzer.analyze", side_effect=lambda c,f,k,b: StageResult(b)):
                        result = app.run(ScanRequest(str(root), str(ROOT/"rulesets/riscv-porting"), str(output), schema_version=version, exclude_paths=exclude))
            self.assertEqual(0, result.exit_code, result.diagnostics)
            self.assertEqual(before, {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertEqual({"scan-result.json", "scan-report.html", "scan.log"}, {p.name for p in output.iterdir()})
            report = json.loads((output/"scan-result.json").read_text())
            if version == "2.0":
                V2ReferentialIntegrityValidator().validate(SchemaV2Report.model_validate(report))
            return report, (output/"scan-report.html").read_text()

    def test_empty_path_only_family_and_foreign_context(self):
        files = {"arch/x86/foo.cpp":"", "arch/riscv/foo.cpp":"", "arch/arm/foo.cpp":""}
        report, html = self.scan(files)
        self.assertEqual([], report["findings"])
        catalog = report["extensions"][NAMESPACE]
        self.assertEqual(1, len(catalog["families"]))
        self.assertEqual({"x86", "riscv", "foreign"}, {m["roleHint"] for m in catalog["families"][0]["members"]})
        self.assertIn("架构实现候选家族", html)
        old, _ = self.scan(files, "1.0")
        self.assertEqual([], old["findings"])
        self.assertNotIn("extensions", old)

    def test_cmake_selection_and_existing_conclusions_unchanged(self):
        files = {"CMakeLists.txt": 'if(CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")\nadd_library(v foo_x86.cpp)\nelse()\nadd_library(v foo_generic.cpp)\nendif()\n',
                 "foo_x86.cpp":"void f(){_mm256_setzero_ps();}\n", "foo_generic.cpp":"int f(){return 0;}\n"}
        report, _ = self.scan(files)
        before, _ = self.scan(files, family=False)
        self.assertEqual(before["summary"], report["summary"])
        self.assertEqual(len(before["findings"]), len(report["findings"]))
        for old, new in zip(before["findings"], report["findings"]):
            self.assertEqual(old["conclusion"], new["conclusion"])
            self.assertEqual(old["occurrences"], new["occurrences"])
            self.assertEqual(old["evidenceChain"], new["evidenceChain"])
        members = report["extensions"][NAMESPACE]["families"][0]["members"]
        self.assertEqual({"selected"}, {b["selectionStatus"] for m in members if m["roleHint"] == "generic" for b in m["bindings"]})
        self.assertEqual({"inactive"}, {b["selectionStatus"] for m in members if m["roleHint"] == "x86" for b in m["bindings"]})
        hit = next(f for f in report["findings"] if f["fact"]["symbol"] == "_mm256_setzero_ps")
        self.assertIn(NAMESPACE, hit["fact"]["extensions"])

    def test_unselected_generic_name_cannot_remove_blocker(self):
        files = {"CMakeLists.txt":"add_library(v foo_x86.cpp)\n", "foo_x86.cpp":"void f(){_mm256_setzero_ps();}\n", "foo_generic.cpp":"void g(){_mm256_setzero_ps();}\n"}
        report, _ = self.scan(files)
        original, _ = self.scan(files, family=False)
        self.assertGreater(report["summary"]["blocking"], 0)
        self.assertEqual(original["summary"], report["summary"])
        generic = next(m for m in report["extensions"][NAMESPACE]["families"][0]["members"] if m["roleHint"] == "generic")
        self.assertEqual([], generic["bindings"])
        self.assertEqual("unknown", generic["candidateStatus"])
        first, _ = self.scan(files, "1.0")
        second, _ = self.scan(files, "1.0", family=False)
        # V1 intentionally contains absolute workspace paths, unlike stable IDs.
        first_json = json.dumps(first).replace(first["project"]["root"], "/same-input")
        second_json = json.dumps(second).replace(second["project"]["root"], "/same-input")
        self.assertEqual(first_json, second_json)

    def test_make_and_autoconf_bindings_are_not_invented(self):
        for build in ({"Makefile":"SOURCES = foo_x86.cpp\n"},
                      {"configure":'case "$(uname -m)" in\nx86_64) SOURCES=foo_x86.cpp ;;\n*) SOURCES=foo_generic.cpp ;;\nesac\n'}):
            report, _ = self.scan({**build, "foo_x86.cpp":"int x;\n", "foo_generic.cpp":"int g;\n"})
            members = report["extensions"][NAMESPACE]["families"][0]["members"]
            if "Makefile" in build:
                self.assertTrue(any(m["bindings"] for m in members))
            for member in members:
                for binding in member["bindings"]:
                    self.assertTrue(binding["sources"])
                    self.assertTrue(all(s["path"] in build for s in binding["sources"]))
            self.assertEqual("unknown", report["extensions"][NAMESPACE]["families"][0]["alternativeStatus"])

    def test_excluded_and_damaged_file_do_not_prove_absence(self):
        report, _ = self.scan({"arch/x86/foo.cpp":"void broken( {\n", "arch/generic/foo.cpp":"int f;\n"}, exclude=("arch/generic",))
        family = report["extensions"][NAMESPACE]["families"][0]
        self.assertEqual(1, family["memberCount"])
        self.assertEqual("unknown", family["alternativeStatus"])
        self.assertEqual("unknown", family["members"][0]["observation"]["parseStatus"])

    def test_outside_symlink_is_not_a_candidate_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, out = Path(temporary)/"input", Path(temporary)/"report"
            root.mkdir()
            (root/"foo_x86.cpp").write_text("int x;\n")
            secret = Path(temporary)/"outside.cpp"
            secret.write_text("int hidden;\n")
            (root/"foo_generic.cpp").symlink_to(secret)
            result = create_default_application().run(ScanRequest(str(root), str(ROOT/"rulesets/riscv-porting"), str(out)))
            self.assertEqual(0, result.exit_code)
            report = json.loads((out/"scan-result.json").read_text())
            family = report["extensions"][NAMESPACE]["families"][0]
            self.assertEqual(["foo_x86.cpp"], [m["path"] for m in family["members"]])
            self.assertEqual("unknown", family["alternativeStatus"])


if __name__ == "__main__":
    unittest.main()
