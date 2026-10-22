import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kb_scanner.core import CompletionStatus, WorkspaceSnapshot
from kb_scanner.frontends.build.frontend import BuildFrontend
from kb_scanner.frontends.build.autoconf.project import analyze_project, auxiliary_pair, declarations
from kb_scanner.frontends.build.workspace import build_input_kind
from tests.unit.build_selection.support import context
from .support import command, source


class ProjectTests(unittest.TestCase):
    def test_bound_helper_keeps_raw_facts_without_duplicate_unbound_outcomes(self):
        scripts = {"configure": source(command("./config.sub"), path="configure"),
                   "config.sub": source(command("exit", "1"), path="config.sub")}
        with patch("kb_scanner.frontends.build.autoconf.project.parse", side_effect=lambda text, path: scripts[path]):
            result = analyze_project({path: item.data.decode() for path, item in scripts.items()}, "riscv64")
        self.assertFalse(any(record.metadata["autoconf"].get("outcome") for record in result["config.sub"].records))
        self.assertTrue(any(record.metadata["autoconf"].get("raw") for record in result["config.sub"].records))
        self.assertEqual(next(record.metadata["autoconf"]["outcome"] for record in result["configure"].records if record.metadata["autoconf"].get("outcome")), "rejected")
    def test_m4_balanced_macros_comments_multiline_opaque_and_dynamic(self):
        text = """# AC_CANONICAL_TARGET
dnl AC_CANONICAL_BUILD
[AC_CANONICAL_HOST]
AC_DEFUN([macro], [AC_CANONICAL_TARGET])
AC_CANONICAL_HOST
AC_CONFIG_AUX_DIR(
 [build-aux]
)
AC_CONFIG_SUBDIRS([vendor/a vendor/b])
AC_CONFIG_AUX_DIR([$variable])
AC_CONFIG_AUX_DIR([broken]
"""
        found = declarations(text)
        self.assertEqual([item.name for item in found], ["AC_CANONICAL_HOST", "AC_CONFIG_AUX_DIR", "AC_CONFIG_SUBDIRS", "AC_CONFIG_AUX_DIR", "AC_CONFIG_AUX_DIR"])
        self.assertEqual([item.argument for item in found], ["", "build-aux", "vendor/a vendor/b", None, None])
        self.assertIn("AC_CANONICAL_HOST", text.encode()[found[0].start:found[0].end].decode())
        self.assertEqual(declarations("[broken quote"), ())
        self.assertEqual(declarations("AC_CONFIG_AUX_DIR([$x])]")[0].argument, None)
        with self.assertRaisesRegex(ValueError, "declaration-budget"):
            declarations("AC_CANONICAL_HOST", max_declarations=0)

    def test_pair_defaults_explicit_parent_escape_dynamic_and_no_mixed_vendors(self):
        files = {"config.guess", "config.sub", "vendor/config.guess", "vendor/aux/config.sub"}
        self.assertEqual(auxiliary_pair("vendor/configure.ac", files, ())[0], ("config.guess", "config.sub"))
        self.assertIsNone(auxiliary_pair("vendor/configure.ac", files - {"config.guess", "config.sub"}, ())[0])
        for argument, reason in (("../..", "outside-workspace"), ("/tmp", "unavailable"), ("", "unavailable"), ("[$dynamic]", "dynamic")):
            found = declarations(f"AC_CONFIG_AUX_DIR({argument})")
            self.assertIn(reason, auxiliary_pair("vendor/configure.ac", files, found)[1])
        found = declarations("AC_CONFIG_AUX_DIR([../])")
        self.assertEqual(auxiliary_pair("vendor/configure.ac", files, found)[0], ("config.guess", "config.sub"))
        found = declarations("AC_CONFIG_AUX_DIR([a]) AC_CONFIG_AUX_DIR([b])")
        self.assertIn("conflicting", auxiliary_pair("configure.ac", files, found)[1])
        self.assertIn("unavailable", auxiliary_pair("configure.ac", files, declarations("AC_CONFIG_AUX_DIR([missing])"))[1])

    def test_project_scopes_m4_unknown_local_results_and_budget(self):
        scripts = {"configure": source(command("exit", "1"), path="configure"),
                   "config.guess": source(command("echo", "riscv64-unknown-linux"))}
        contents = {path: item.data.decode() for path, item in scripts.items()}
        contents["configure.ac"] = "AC_CANONICAL_HOST() AC_CONFIG_AUX_DIR([aux])"
        with patch("kb_scanner.frontends.build.autoconf.project.parse", side_effect=lambda text, path: scripts[path]):
            results = analyze_project(contents, "riscv64")
            terminal = [r.metadata["autoconf"] for r in results["configure"].records if r.metadata["autoconf"].get("outcome")]
            self.assertEqual(terminal[0]["outcome"], "rejected")
            self.assertTrue(terminal[0]["bound"])
            self.assertTrue(results["configure.ac"].partial)
            self.assertFalse(results["config.guess"].partial)
            limited = analyze_project(contents, "riscv64", max_units=1)
            self.assertTrue(limited["config.guess"].partial)
        with self.assertRaises(ValueError):
            analyze_project({}, "riscv64", max_units=0)
        with patch("kb_scanner.frontends.build.autoconf.project.parse", side_effect=RuntimeError("broken")):
            self.assertTrue(analyze_project({"configure": "x"}, "riscv64")["configure"].partial)
        opaque = analyze_project({"empty.m4": "AC_INIT([p],[1])"}, "riscv64")["empty.m4"]
        self.assertTrue(opaque.partial)
        self.assertTrue(all(record.metadata["autoconf"]["raw"] for record in opaque.records))
        with patch("kb_scanner.frontends.build.autoconf.project.declarations", side_effect=ValueError("autoconf-m4-declaration-budget")):
            self.assertTrue(analyze_project({"configure.ac": "AC_CANONICAL_HOST"}, "riscv64")["configure.ac"].partial)
        project = analyze_project({"configure.ac": "AC_CONFIG_SUBDIRS([vendor])"}, "riscv64")
        record = project["configure.ac"].records[0]
        self.assertEqual(record.metadata["autoconf"]["declaredSubprojects"], ("vendor/configure",))
        self.assertEqual(record.metadata["autoconf"]["subprojectsPresent"], ())

    def test_real_reader_preserves_crlf_digest_and_bounded_content(self):
        from hashlib import sha256
        from kb_scanner.frontends.build.frontend import _read_text
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "configure.ac"
            data = b"# comment\r\nAC_CANONICAL_HOST\r\n"
            path.write_bytes(data)
            self.assertEqual(_read_text(path).encode(), data)
            self.assertEqual(len(_read_text(path, 3)), 4)
            result = BuildFrontend().analyze(context(root), WorkspaceSnapshot(root, (path.name,)))
            evidence = result.value.evidence[0]
            self.assertEqual(evidence.metadata["autoconf"]["digest"], sha256(data).hexdigest())
            self.assertEqual(evidence.location.start.line, 2)

    def test_frontend_reads_only_authorized_files_once_and_checks_budgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("configure", "config.guess", "config.sub"):
                (root / name).write_text("exit 1")
                self.assertIsNotNone(build_input_kind(name))
            snapshot = WorkspaceSnapshot(root, ("configure", "config.guess"))
            calls = []
            def reader(path):
                calls.append(path.name)
                return "exit 1"
            with patch("kb_scanner.frontends.build.autoconf.project.parse", side_effect=lambda text, path: source(command("exit", "1"), path=path)):
                result = BuildFrontend(reader=reader).analyze(context(root), snapshot)
            self.assertEqual(sorted(calls), ["config.guess", "configure"])
            self.assertEqual(result.status, CompletionStatus.COMPLETE)
            self.assertNotIn("config.sub", {item.name for item in result.value.entities})
            for frontend in (BuildFrontend(max_bytes=1), BuildFrontend(reader=lambda _: "a" * 100, max_bytes=50),
                             BuildFrontend(reader=lambda _: (_ for _ in ()).throw(UnicodeError()))):
                self.assertEqual(frontend.analyze(context(root), snapshot).status, CompletionStatus.PARTIAL)
            with tempfile.TemporaryDirectory() as external:
                target = Path(external) / "config.guess"
                target.write_text("exit 1")
                (root / "escaped").mkdir()
                (root / "escaped/config.guess").symlink_to(target)
                escaped = WorkspaceSnapshot(root, ("escaped/config.guess",))
                self.assertEqual(BuildFrontend().analyze(context(root), escaped).status, CompletionStatus.PARTIAL)
            scan_context = context(root)
            with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=65 * 1024 * 1024)):
                self.assertEqual(BuildFrontend(max_bytes=100 * 1024 * 1024).analyze(scan_context, snapshot).status, CompletionStatus.PARTIAL)
