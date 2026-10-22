from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kb_scanner.adapters.cli import StagedContextFactory, scan_request_from_namespace
from kb_scanner.bundle import BundleError, load_bundle_descriptor
from kb_scanner.core import CompilationUnitContext, CompletionStatus, Diagnostic, DiagnosticSeverity, ScanContext, ScanRequest, StageResult


def write_bundle(root: Path, *, mutate=None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    content = b'{"schemaVersion":"1.0","sources":[]}'
    (root / "knowledge.json").write_bytes(content)
    value = {
        "schemaVersion": "1.0",
        "rulePack": {"id": "riscv-porting", "version": "1"},
        "knowledgeManifest": {"path": "knowledge.json", "sha256": hashlib.sha256(content).hexdigest()},
        "projectionPolicy": {"id": "compatible", "version": 1},
    }
    if mutate:
        mutate(value)
    (root / "scanner-manifest.json").write_text(json.dumps(value), encoding="utf-8")


class FakeDatabase:
    def __init__(self, result): self.result = result; self.calls = []
    def read(self, path, root): self.calls.append((path, root)); return self.result


class BundleCliTests(unittest.TestCase):
    def test_bundle_loads_and_identity_ignores_root_and_json_order(self) -> None:
        identities = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "rules"; write_bundle(root)
                descriptor = load_bundle_descriptor(root)
                identities.append(descriptor.identity)
                self.assertEqual("riscv-porting", descriptor.rule_pack_id)
                self.assertEqual(root.resolve(), descriptor.root)
        self.assertEqual(identities[0], identities[1])

    def test_bundle_rejects_invalid_root_shape_paths_digest_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(BundleError): load_bundle_descriptor(base / "missing")
            mutations = (
                lambda v: v.update(extra=True),
                lambda v: v.update(schemaVersion="2.0"),
                lambda v: v["knowledgeManifest"].update(path="../knowledge.json"),
                lambda v: v["knowledgeManifest"].update(sha256="f" * 64),
                lambda v: v["projectionPolicy"].update(version=0),
                lambda v: v["rulePack"].update(id=""),
            )
            for index, mutation in enumerate(mutations):
                root = base / str(index); write_bundle(root, mutate=mutation)
                with self.subTest(index=index), self.assertRaises(BundleError):
                    load_bundle_descriptor(root)
            root = base / "bad-json"; root.mkdir(); (root / "scanner-manifest.json").write_text("{")
            with self.assertRaises(BundleError): load_bundle_descriptor(root)

    def test_namespace_adapter_preserves_scan_options(self) -> None:
        ns = argparse.Namespace(
            input="in", rules="rules", output="out", language=" c,cpp, ", exclude=".git, build",
            exclude_path=[" vendor ", ""], format="json", context_infer="off", target_arch="riscv64",
            include_inactive_branches=True, no_comment_hints=True, compile_commands="cc.json", locale="zh-CN",
        )
        request = scan_request_from_namespace(ns)
        self.assertEqual(("c", "cpp"), request.languages)
        self.assertEqual(("vendor",), request.exclude_paths)
        self.assertFalse(request.include_comment_hints)
        self.assertEqual(("json",), request.formats)

    def test_context_factory_handles_modes_diagnostics_and_invalid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "src"; source.mkdir(); rules = root / "rules"; write_bundle(rules)
            output = root / "out"
            factory = StagedContextFactory(FakeDatabase(StageResult(None, CompletionStatus.UNAVAILABLE, (Diagnostic("compilation-database.missing", "db", DiagnosticSeverity.INFO, "missing"),))))
            result = factory.build(ScanRequest(str(source), str(rules), str(output), context_infer="off"))
            self.assertEqual(CompletionStatus.COMPLETE, result.status)
            self.assertEqual("syntax_scan", result.value.scan_mode)
            self.assertEqual("knowledge.json", result.value.knowledge_manifest_name)
            warning = Diagnostic("db.partial", "db", DiagnosticSeverity.WARNING, "bad entry")
            result = StagedContextFactory(FakeDatabase(StageResult((), CompletionStatus.PARTIAL, (warning,)))).build(ScanRequest(str(source), str(rules), str(output)))
            self.assertEqual(CompletionStatus.PARTIAL, result.status)
            self.assertEqual("source_context", result.value.scan_mode)
            bad = StagedContextFactory().build(ScanRequest(str(root / "missing"), str(rules), str(output)))
            self.assertEqual(CompletionStatus.FAILED, bad.status)
            broken = root / "broken"; broken.mkdir()
            bad = StagedContextFactory().build(ScanRequest(str(source), str(broken), str(output)))
            self.assertEqual("context.bundle-invalid", bad.diagnostics[0].code)

    def test_context_rejects_empty_knowledge_manifest_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                ScanContext(root, root, root, (), (), (), (), "auto", "riscv64", False, True, "en", None, (), "source", "pack", "1", "knowledge", "scanner", "1", "")

    def test_request_and_compilation_context_normalize_collections_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unit = CompilationUnitContext(root / "b.c", defines=(("Z", None), ("A", "1")), tokens=["cc"], diagnostics=["note"], directory=root)
            unit_without_directory = CompilationUnitContext(root / "a.c")
            request = ScanRequest("i", "r", "o", languages=["c"], excludes=["x"], exclude_paths=["vendor"], formats=["json"])
            self.assertEqual((("A", "1"), ("Z", None)), unit.defines)
            self.assertEqual(("c",), request.languages)
            self.assertEqual(root.resolve(), unit.directory)
            self.assertIsNone(unit_without_directory.directory)
            scan_context = ScanContext(root, root / "out", root, (), (), (), (), "auto", "riscv64", False, True, "en", root / "compile_commands.json", (unit,), "source", "pack", "1", "knowledge", "scanner", "1")
            self.assertEqual((root / "compile_commands.json").resolve(), scan_context.compile_commands_path)
            with self.assertRaises(ValueError):
                ScanRequest("i", "r", "o", context_infer="invalid")


if __name__ == "__main__":
    unittest.main()
