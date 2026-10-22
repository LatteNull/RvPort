from __future__ import annotations

import tempfile
import unittest
import weakref
from pathlib import Path
from types import SimpleNamespace

from kb_scanner.core import CompilationUnitContext, CompletionStatus, DiagnosticSeverity, WorkspaceSnapshot
from kb_scanner.frontends.cpp.clang_adapter import (
    ClangCppAdapter,
    _clang_location,
    _cursor_kind,
    _cursor_span,
    _cursor_value,
    _diagnostic_severity,
    _redact_project_path,
    _walk_cursor,
)
from kb_scanner.frontends.cpp.vocabulary import make_source_file_entity
from tests.unit.frontends.cpp.support import make_context


class Point:
    def __init__(self, file=None, line=1, column=1):
        self.file, self.line, self.column = file, line, column


class Cursor:
    def __init__(self, kind="CALL_EXPR", *, file=None, spelling="call", displayname="", children=(), tokens=(), start=(1, 1), end=(1, 5)):
        self.kind = SimpleNamespace(name=kind)
        self.location = Point(file, start[0], start[1])
        self.extent = SimpleNamespace(start=Point(file, *start), end=Point(file, *end))
        self.spelling, self.displayname = spelling, displayname
        self._children = list(children)
        self._tokens = list(tokens)

    def get_children(self):
        return iter(self._children)

    def get_tokens(self):
        return iter(self._tokens)


class Token:
    def __init__(self, spelling, start, end):
        self.spelling = spelling
        self.extent = SimpleNamespace(start=Point(None, *start), end=Point(None, *end))


class TranslationUnit:
    def __init__(self, cursor, diagnostics=()):
        self.cursor, self.diagnostics = cursor, list(diagnostics)


class FakeCIndex:
    class TranslationUnit:
        PARSE_DETAILED_PROCESSING_RECORD = 77

    class Diagnostic:
        Warning, Error, Fatal = 2, 3, 4

    def __init__(self, translation_unit=None, *, create_error=None, parse_error=None):
        self.translation_unit = translation_unit
        self.create_error = create_error
        self.parse_error = parse_error
        self.calls = []
        owner = self

        class Index:
            @staticmethod
            def create():
                if owner.create_error:
                    raise owner.create_error
                return SimpleNamespace(parse=owner.parse)

        self.Index = Index

    def parse(self, path, args, options):
        self.calls.append((path, tuple(args), options))
        if self.parse_error:
            raise self.parse_error
        return self.translation_unit


class ClangAdapterTests(unittest.TestCase):
    def test_standard_assert_profile_is_copied_with_observed_tu_not_native_cursor(self):
        from tests.unit.test_assert_profile import cursor as profile_cursor, _BODIES
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            unit,workspace,entities=self.fixture(root,tokens=("clang","main.c"))
            child=Cursor("MACRO_INSTANTIATION",file=root/"main.c",spelling="assert")
            child.referenced=profile_cursor(next(iter(_BODIES))).referenced
            fake=FakeCIndex(TranslationUnit(Cursor("ROOT",children=(child,))))
            result=ClangCppAdapter(lambda:fake).enrich(make_context(root),workspace,unit,entities)
            copied=next(e for e in result.value if e.value=="assert")
            self.assertEqual("disabled",copied.metadata["standardAssert"]["status"])
            self.assertEqual("observed-compilation-unit",copied.metadata["standardAssert"]["scope"])
            self.assertTrue(copied.metadata["standardAssert"]["configuration"])

    def fixture(self, root: Path, tokens=("clang", "-DOK", "-o", "bad.o", "main.c")):
        source = root / "main.c"
        source.write_text("int main(void);", encoding="utf-8")
        unit = CompilationUnitContext(path=source, tokens=tokens, directory=root, entry_index=3)
        workspace = WorkspaceSnapshot(root, ("main.c",))
        entities = {"main.c": make_source_file_entity("main.c", ("c",), "1")}
        return unit, workspace, entities

    def test_fake_binding_receives_only_normalized_args_and_parse_option(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unit, workspace, entities = self.fixture(root)
            child = Cursor(file=root / "main.c")
            fake = FakeCIndex(TranslationUnit(Cursor("ROOT", children=(child,))))
            result = ClangCppAdapter(lambda: fake).enrich(make_context(root, compile_contexts=(unit,)), workspace, unit, entities)
            self.assertEqual(fake.calls, [(str(unit.path), ("-DOK",), 77)])
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertEqual(result.value[0].kind, "call_expression")

    def test_loader_create_and_parse_failures_degrade_per_translation_unit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            cases = (
                lambda: (_ for _ in ()).throw(ImportError("clang")),
                lambda: FakeCIndex(create_error=RuntimeError("create")),
                lambda: FakeCIndex(parse_error=RuntimeError("parse")),
            )
            for loader in cases:
                with self.subTest(loader=loader):
                    result = ClangCppAdapter(loader).enrich(make_context(root), workspace, unit, entities)
                    self.assertEqual(result.status, CompletionStatus.PARTIAL)
                    self.assertEqual(result.value, ())
                    self.assertEqual(result.diagnostics[-1].code, "clang.translation-unit-unavailable")
                    self.assertEqual(result.diagnostics[-1].details["entryIndex"], 3)

    def test_diagnostic_severity_locations_redaction_and_error_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root, outside = Path(raw), Path(outside_raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            diagnostics = [
                SimpleNamespace(severity=1, location=Point(), spelling="note"),
                SimpleNamespace(severity=2, location=Point(root / "main.c", 1, 0), spelling=f"warning {root}"),
                SimpleNamespace(severity=3, location=Point(outside / "x.h", 2, 2), spelling="error"),
                SimpleNamespace(severity=4, location=None, spelling="fatal"),
            ]
            child = Cursor(file=root / "main.c")
            fake = FakeCIndex(TranslationUnit(Cursor("ROOT", children=(child,)), diagnostics))
            result = ClangCppAdapter(lambda: fake).enrich(make_context(root), workspace, unit, entities)
            self.assertEqual([d.severity for d in result.diagnostics], [DiagnosticSeverity.INFO, DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR, DiagnosticSeverity.FATAL])
            self.assertEqual(result.diagnostics[1].location.column, 1)
            self.assertIsNone(result.diagnostics[2].location)
            self.assertIn("$PROJECT", result.diagnostics[1].message)
            self.assertEqual(result.value[0].confidence, "medium")
            self.assertEqual(result.status, CompletionStatus.PARTIAL)

    def test_cursor_mapping_filtering_spans_values_and_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root, outside = Path(raw), Path(outside_raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            inside_header = root / "header.h"
            inside_header.write_text("", encoding="utf-8")
            workspace = WorkspaceSnapshot(root, ("header.h", "main.c"))
            entities["header.h"] = make_source_file_entity("header.h", ("c", "cpp"), "1")
            children = [
                Cursor("MACRO_DEFINITION", file=root / "main.c", spelling="M"),
                Cursor("MACRO_INSTANTIATION", file=root / "main.c", spelling="M"),
                Cursor("MACRO_EXPANSION", file=root / "main.c", spelling="M"),
                Cursor("INCLUSION_DIRECTIVE", file=root / "main.c", spelling=str(inside_header)),
                Cursor("INCLUSION_DIRECTIVE", file=root / "main.c", spelling=str(outside / "vendor.h")),
                Cursor("CALL_EXPR", file=root / "main.c", spelling="", displayname="display"),
                Cursor("TYPE_REF", file=root / "main.c", spelling=""),
                Cursor("FUNCTION_TEMPLATE", file=root / "main.c"),
                Cursor("CLASS_TEMPLATE", file=root / "main.c"),
                Cursor("UNKNOWN", file=root / "main.c"),
                Cursor("CALL_EXPR", file=None),
                Cursor("CALL_EXPR", file=outside / "x.h"),
                Cursor("CALL_EXPR", file=root / "main.c", start=(0, 0), end=(0, 0)),
                Cursor("CALL_EXPR", file=root / "main.c", start=(2, 1), end=(1, 1)),
            ]
            fake = FakeCIndex(TranslationUnit(Cursor("ROOT", children=children)))
            result = ClangCppAdapter(lambda: fake).enrich(make_context(root), workspace, unit, entities)
            kinds = {item.kind for item in result.value}
            self.assertEqual(kinds, {"macro_definition", "macro_expansion", "include", "call_expression", "type_reference", "template_declaration"})
            self.assertTrue({"macro_parameter", "macro_replacement_token"}.isdisjoint(kinds))
            values = {item.value for item in result.value}
            self.assertIn("header.h", values)
            self.assertIn("vendor.h", values)
            self.assertIn("display", values)
            self.assertIn("TYPE_REF", values)
            self.assertEqual(len(result.value), len({item.id for item in result.value}))
            self.assertTrue(all(isinstance(item.metadata["entryIndex"], int) for item in result.value))

    def test_macro_tokens_supply_parameters_replacement_extents_and_unsupported_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            tokens = (
                Token("FAST", (1, 9), (1, 13)), Token("(", (1, 13), (1, 14)),
                Token("x", (1, 14), (1, 15)), Token(",", (1, 15), (1, 16)),
                Token("...", (1, 16), (1, 19)), Token(")", (1, 19), (1, 20)),
                Token("_mm_add_ps", (1, 21), (1, 31)), Token("(", (1, 31), (1, 32)),
                Token("x", (1, 32), (1, 33)), Token(",", (1, 33), (1, 34)),
                Token("__VA_ARGS__", (1, 34), (1, 45)), Token(")", (1, 45), (1, 46)),
            )
            macro = Cursor("MACRO_DEFINITION", file=root / "main.c", spelling="FAST", tokens=tokens, start=(1, 9), end=(1, 46))
            fake = FakeCIndex(TranslationUnit(Cursor("ROOT", children=(macro,))))
            result = ClangCppAdapter(lambda: fake).enrich(make_context(root), workspace, unit, entities)
        parameters = [item for item in result.value if item.kind == "macro_parameter"]
        replacement = [item for item in result.value if item.kind == "macro_replacement_token"]
        self.assertEqual([(item.value, item.metadata["ordinal"]) for item in parameters], [("x", 0), ("...", 1)])
        intrinsic = next(item for item in replacement if item.value == "_mm_add_ps")
        self.assertEqual((intrinsic.metadata["tokenRole"], intrinsic.location.start.column, intrinsic.location.end.column), ("call_candidate", 21, 31))
        self.assertTrue(all(item.metadata["macroDefinitionEvidenceId"] for item in (*parameters, *replacement)))
        self.assertEqual(result.status, CompletionStatus.PARTIAL)
        self.assertTrue(any(item.code == "clang.unsupported-macro-semantics" for item in result.diagnostics))

    def test_helpers_cover_order_fallbacks_external_locations_and_severity_boundaries(self) -> None:
        root_cursor = Cursor("ROOT", children=(Cursor("A"), Cursor("B")))
        self.assertEqual([item.kind.name for item in _walk_cursor(root_cursor)], ["ROOT", "A", "B"])
        for name in ("MACRO_DEFINITION", "MACRO_INSTANTIATION", "MACRO_EXPANSION", "INCLUSION_DIRECTIVE", "CALL_EXPR", "TYPE_REF", "FUNCTION_TEMPLATE", "CLASS_TEMPLATE"):
            self.assertIsNotNone(_cursor_kind(name))
        self.assertIsNone(_cursor_kind("UNKNOWN"))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertIsNone(_clang_location(None, root))
            self.assertIsNone(_clang_location(Point(None), root))
            self.assertIsNone(_clang_location(Point(root / "a.c", 0, 1), root))
            self.assertEqual(_cursor_value(Cursor("CALL_EXPR", spelling="", displayname=""), "call_expression", root), "CALL_EXPR")
            self.assertIsNone(_cursor_span("a.c", Cursor(start=(0, 1), end=(1, 1))))
            self.assertEqual(_redact_project_path(f"{root} {root.as_posix()}", root), "$PROJECT $PROJECT")
        fake = FakeCIndex()
        self.assertEqual([_diagnostic_severity(n, fake) for n in (1, 2, 3, 4)], [DiagnosticSeverity.INFO, DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR, DiagnosticSeverity.FATAL])

    def test_translation_unit_is_not_retained_and_next_call_can_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            translation_unit = TranslationUnit(Cursor("ROOT"))
            reference = weakref.ref(translation_unit)
            fake = FakeCIndex(translation_unit)
            adapter = ClangCppAdapter(lambda: fake)
            adapter.enrich(make_context(root), workspace, unit, entities)
            fake.translation_unit = None
            del translation_unit
            self.assertIsNone(reference())
            fake.translation_unit = TranslationUnit(Cursor("ROOT"))
            self.assertEqual(adapter.enrich(make_context(root), workspace, unit, entities).status, CompletionStatus.COMPLETE)

    def test_one_translation_unit_failure_does_not_poison_later_call(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            unit, workspace, entities = self.fixture(root, ("clang", "main.c"))
            calls = 0
            fake = FakeCIndex(TranslationUnit(Cursor("ROOT")))

            def loader():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("first TU unavailable")
                return fake

            adapter = ClangCppAdapter(loader)
            self.assertEqual(adapter.enrich(make_context(root), workspace, unit, entities).status, CompletionStatus.PARTIAL)
            self.assertEqual(adapter.enrich(make_context(root), workspace, unit, entities).status, CompletionStatus.COMPLETE)


if __name__ == "__main__":
    unittest.main()
