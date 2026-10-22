from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kb_scanner.core import CompilationUnitContext, CompletionStatus
from kb_scanner.frontends.cpp.source_positions import SourceByteIndex
from kb_scanner.frontends.cpp.tree_sitter_adapter import (
    TreeSitterCppAdapter,
    _ParseCandidate,
    _has_preprocessor_definition_ancestor,
    _language_from_contexts,
    _macro_names,
    _macro_attachments,
    _macro_token_role,
    _node_kind,
    _node_span,
    _node_value,
    _select_languages,
    _span_from_byte_range,
    _walk,
)
from kb_scanner.frontends.cpp.vocabulary import make_evidence, make_source_file_entity
from tests.unit.frontends.cpp.support import make_context


class Node:
    def __init__(self, kind: str, start: int = 0, end: int = 1, *, children=(), fields=None, parent=None, error=False, missing=False, row=0, column=0, end_row=0, end_column=1):
        self.type = kind
        self.start_byte = start
        self.end_byte = end
        self.children = list(children)
        self._fields = fields or {}
        self.parent = parent
        self.is_error = error
        self.is_missing = missing
        self._unused_points = (row, column, end_row, end_column)
        for child in self.children:
            if child.parent is None:
                child.parent = self

    def child_by_field_name(self, name):
        return self._fields.get(name)

    @property
    def named_children(self):
        return self.children

    @property
    def start_point(self):
        raise AssertionError("production scanner must not read start_point")

    @property
    def end_point(self):
        raise AssertionError("production scanner must not read end_point")


class TreeSitterAdapterTests(unittest.TestCase):
    def test_function_macro_parameters_replacement_tokens_and_unsupported_semantics(self) -> None:
        source = b"#define FAST(x, y) _mm_add_ps((x), (y))\n"
        start = source.index(b"FAST")
        name = Node("identifier", start, start + 4)
        definition_node = Node(
            "preproc_function_def",
            0,
            len(source),
            children=(name,),
            fields={"name": name},
        )
        root = Node("translation_unit", 0, len(source), children=(definition_node,))

        class Grammar:
            @staticmethod
            def language(): return "capsule"

        class Parser:
            def __init__(self, _language): pass
            def parse(self, _source): return SimpleNamespace(root_node=root)

        entity = make_source_file_entity("macro.c", ("c",), "1")
        with patch("kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_c", Grammar), patch(
            "kb_scanner.frontends.cpp.tree_sitter_adapter.Language", lambda value: value
        ), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", Parser), patch(
            "kb_scanner.frontends.cpp.tree_sitter_adapter.version", return_value="1"
        ):
            parsed = TreeSitterCppAdapter()._parse_candidate(source, "macro.c", entity, "c", "suffix", False)
        kinds = [item.kind for item in parsed.evidence]
        self.assertEqual(kinds.count("macro_definition"), 1)
        self.assertEqual(kinds.count("macro_parameter"), 2)
        call_tokens = [item for item in parsed.evidence if item.kind == "macro_replacement_token" and item.metadata["tokenRole"] == "call_candidate"]
        self.assertEqual([item.value for item in call_tokens], ["_mm_add_ps"])
        self.assertFalse(any(item.kind in {"call_expression", "macro_expansion"} for item in parsed.evidence))
        self.assertEqual(call_tokens[0].location.start.line, 1)

        zero_source = b"#define ZERO() WRAP()\n"
        zero_start = zero_source.index(b"ZERO")
        zero_name = Node("identifier", zero_start, zero_start + 4)
        zero_node = Node(
            "preproc_function_def",
            0,
            len(zero_source),
            children=(zero_name,),
            fields={"name": zero_name},
        )
        zero_definition = make_evidence(
            kind="macro_definition",
            subject_id=entity.id,
            value="ZERO",
            producer="p",
            parse_mode="m",
            confidence="high",
            span=_span_from_byte_range("macro.c", zero_source, 0, len(zero_source)),
        )
        zero_attachments, zero_unsupported = _macro_attachments(
            zero_node, zero_source, "macro.c", entity.id, zero_definition, "p", "c", "suffix", False
        )
        self.assertFalse(any(item.kind == "macro_parameter" for item in zero_attachments))
        self.assertEqual(
            [item.value for item in zero_attachments if item.metadata["tokenRole"] == "call_candidate"],
            ["WRAP"],
        )
        self.assertEqual(zero_unsupported, ())

        unsupported_source = b"#define JOIN(a, ...) # a ## __VA_ARGS__\n"
        unsupported_name_start = unsupported_source.index(b"JOIN")
        unsupported_name = Node("identifier", unsupported_name_start, unsupported_name_start + 4)
        unsupported_node = Node(
            "preproc_function_def", 0, len(unsupported_source), children=(unsupported_name,), fields={"name": unsupported_name}
        )
        definition = make_evidence(
            kind="macro_definition",
            subject_id=entity.id,
            value="JOIN",
            producer="p",
            parse_mode="m",
            confidence="high",
            span=_span_from_byte_range("macro.c", unsupported_source, 0, len(unsupported_source)),
        )
        attachments, unsupported = _macro_attachments(
            unsupported_node,
            unsupported_source,
            "macro.c",
            entity.id,
            definition,
            "p",
            "c",
            "suffix",
            False,
        )
        self.assertEqual(set(unsupported), {"stringification", "token-pasting", "variadic"})
        self.assertTrue(all(item.metadata["macroDefinitionEvidenceId"] == definition.id for item in attachments))
        self.assertEqual(_macro_token_role(b"7", b"7", 1, set()), "number")
        self.assertEqual(_macro_token_role(b'"x"', b'"x"', 3, set()), "string")
        self.assertEqual(_macro_token_role(b"+", b"+", 1, set()), "operator")

    def test_unparseable_function_macro_parameters_are_reported(self) -> None:
        source = b"#define BROKEN x"
        start = source.index(b"BROKEN")
        name = Node("identifier", start, start + 6)
        node = Node("preproc_function_def", 0, len(source), children=(name,), fields={"name": name})
        entity = make_source_file_entity("macro.c", ("c",), "1")
        definition = make_evidence(
            kind="macro_definition", subject_id=entity.id, value="BROKEN", producer="p", parse_mode="m",
            confidence="medium", span=_span_from_byte_range("macro.c", source, 0, len(source)),
        )
        attachments, unsupported = _macro_attachments(
            node, source, "macro.c", entity.id, definition, "p", "c", "suffix", True
        )
        self.assertEqual(attachments, ())
        self.assertEqual(unsupported, ("unparseable-parameters",))
    def test_node_span_uses_only_byte_offsets(self) -> None:
        source = b"head\n" + (b"x" * 365)
        node = Node("identifier", 13, 370)
        span = _node_span(SourceByteIndex.build("long-line.c", source), node)
        self.assertEqual(
            (span.start.line, span.start.column, span.end.line, span.end.column),
            (2, 9, 2, 366),
        )

    def test_parse_candidate_isolated_from_real_grammar_and_parser(self) -> None:
        source = b"#include <x.h>"
        path = Node("string_literal", 9, 14)
        include = Node("preproc_include", 0, len(source), fields={"path": path})
        root = Node("translation_unit", children=(include,))
        captures = {}

        class Grammar:
            @staticmethod
            def language():
                captures["grammar"] = True
                return "capsule"

        class Language:
            def __init__(self, value):
                captures["language"] = value

        class Parser:
            def __init__(self, language):
                captures["parser_language"] = language

            def parse(self, value):
                captures["bytes"] = value
                return SimpleNamespace(root_node=root)

        entity = make_source_file_entity("a.c", ("c",), "1")
        with patch("kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_c", Grammar), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Language", Language), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", Parser), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.version", return_value="9.8.7"):
            result = TreeSitterCppAdapter()._parse_candidate(source, "a.c", entity, "c", "suffix", False)
        self.assertEqual(captures["bytes"], source)
        self.assertTrue(captures["grammar"])
        self.assertEqual(result.producer, "tree-sitter-c@9.8.7")
        self.assertEqual(result.evidence[0].value, "x.h")
        self.assertEqual(
            {"language", "language_source", "producer", "evidence", "diagnostics", "error_count"},
            set(result.__dataclass_fields__),
        )
        self.assertFalse(any(isinstance(value, (Parser, Language)) for value in result.evidence))

    def test_cpp_candidate_uses_cpp_grammar_and_package_version(self) -> None:
        captures = []
        root = Node("translation_unit")

        class Grammar:
            @staticmethod
            def language():
                captures.append("cpp-grammar")
                return "cpp-capsule"

        class Parser:
            def __init__(self, language): captures.append(language)
            def parse(self, source):
                captures.append(source)
                return SimpleNamespace(root_node=root)

        entity = make_source_file_entity("a.cpp", ("cpp",), "1")
        with patch("kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_cpp", Grammar), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Language", lambda value: f"language:{value}"), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", Parser), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.version", return_value="2") as package_version:
            result = TreeSitterCppAdapter()._parse_candidate(b"x", "a.cpp", entity, "cpp", "suffix", False)
        package_version.assert_called_once_with("tree-sitter-cpp")
        self.assertEqual(result.producer, "tree-sitter-cpp@2")
        self.assertEqual(captures, ["cpp-grammar", "language:cpp-capsule", b"x"])

    def test_read_and_initialization_failures_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            entity = make_source_file_entity("missing.c", ("c",), "1")
            context = make_context(root)
            read = TreeSitterCppAdapter().analyze_file(context, root, "missing.c", entity)
            self.assertEqual(read.status, CompletionStatus.PARTIAL)
            self.assertEqual(read.diagnostics[0].code, "tree-sitter.read-failed")
            (root / "a.c").write_bytes(b"x")
            entity = make_source_file_entity("a.c", ("c",), "1")
            with patch.object(TreeSitterCppAdapter, "_parse_candidate", side_effect=RuntimeError("no grammar")):
                failed = TreeSitterCppAdapter().analyze_file(context, root, "a.c", entity)
            self.assertEqual(failed.status, CompletionStatus.FAILED)
            self.assertTrue(failed.diagnostics[0].affects_exit_code)

    def test_suffix_context_and_header_candidate_selection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            c_context = CompilationUnitContext(path=root / "dir" / "same.h", tokens=("cc", "-x", "c"))
            other = CompilationUnitContext(path=root / "other" / "same.h", tokens=("c++",))
            context = make_context(root, compile_contexts=(other, c_context))
            self.assertEqual(_select_languages("a.cpp", context, root), (("cpp",), "suffix"))
            self.assertEqual(_select_languages("dir/same.h", context, root), (("c",), "compilation_context"))
            self.assertEqual(_select_languages("unknown.h", context, root), (("c", "cpp"), "ambiguous_header"))
            self.assertEqual(_language_from_contexts([CompilationUnitContext(path=root / "x.h", tokens=("cc", "-xc++"))]), "cpp")
            self.assertEqual(_language_from_contexts([CompilationUnitContext(path=root / "x.h", tokens=("cc", "-xobjective-c"))]), "c")
            self.assertIsNone(_language_from_contexts([CompilationUnitContext(path=root / "x.h", tokens=("cc",))]))

    def test_ambiguous_header_uses_error_score_then_cpp_tie_break(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.h").write_bytes(b"x")
            context = make_context(root)
            entity = make_source_file_entity("a.h", ("c", "cpp"), "1")
            made = []

            def candidate(_self, _source, _path, _entity, language, language_source, _comments):
                item = _ParseCandidate(language, language_source, language, (), (), 2 if language == "c" else 1)
                made.append(item)
                return item

            with patch.object(TreeSitterCppAdapter, "_parse_candidate", candidate):
                result = TreeSitterCppAdapter().analyze_file(context, root, "a.h", entity)
            self.assertEqual(result.status, CompletionStatus.PARTIAL)
            self.assertEqual(made, [made[0], made[1]])
            self.assertEqual(min(made, key=lambda x: (x.error_count, 0 if x.language == "cpp" else 1)).language, "cpp")
            made.clear()
            def tie(_self, _source, _path, _entity, language, language_source, _comments):
                item = _ParseCandidate(language, language_source, language, (), (), 0)
                made.append(item)
                return item
            with patch.object(TreeSitterCppAdapter, "_parse_candidate", tie):
                complete = TreeSitterCppAdapter().analyze_file(context, root, "a.h", entity)
            self.assertEqual(complete.status, CompletionStatus.COMPLETE)
            self.assertEqual(made[1].language, "cpp")

    def test_node_kinds_values_spans_walk_and_comment_switch(self) -> None:
        source = b'if constexpr(x) #include "foo.h" else asm call type template //comment'
        cases = [
            ("preproc_if", "preprocessor_condition"), ("preproc_else", "preprocessor_branch"),
            ("preproc_include", "include"), ("preproc_def", "macro_definition"),
            ("preproc_call", "macro_expansion"), ("call_expression", "call_expression"),
            ("type_identifier", "type_reference"), ("template_declaration", "template_declaration"),
            ("if_statement", None), ("condition_clause", None), ("case_statement", None),
            ("gnu_asm_expression", "inline_asm"),
            ("attribute_specifier", "declaration_attribute"),
            ("attribute_declaration", "declaration_attribute"),
            ("ms_declspec_modifier", "declaration_attribute"),
            ("comment", "comment"), ("identifier", None),
        ]
        for kind, expected in cases:
            node = Node(kind, 0, len(source))
            self.assertEqual(_node_kind(node, source, True), expected)
        self.assertIsNone(_node_kind(Node("comment"), source, False))
        field = Node("identifier", 1, 6)
        include = Node("preproc_include", fields={"path": field})
        self.assertEqual(_node_value(include, b'"x.h"', "include"), "x.h")
        self.assertEqual(_node_value(Node("preproc_else"), b"#else", "preprocessor_branch"), "else")
        self.assertEqual(len(_node_value(Node("unknown", 0, 600), b"x" * 600, "comment")), 512)
        positioned = Node("identifier", 2, 4)
        span = _node_span(SourceByteIndex.build("a.c", b"a\nbc\n"), positioned)
        self.assertEqual((span.start.line, span.start.column, span.end.line, span.end.column), (2, 1, 2, 3))
        child = Node("child")
        parent = Node("parent", children=(child,))
        self.assertEqual([n.type for n in _walk(parent)], ["parent", "child"])

    def test_partial_parse_retains_evidence_medium_confidence_and_macro_rules(self) -> None:
        source = b"#define X 1\nX"
        name = Node("identifier", 8, 9)
        definition_use = Node("identifier", 8, 9)
        definition = Node("preproc_def", 0, 11, children=(definition_use,), fields={"name": name})
        use = Node("identifier", 12, 13)
        error = Node("ERROR", 13, 13, error=True, missing=True, row=1, column=1)
        root = Node("translation_unit", children=(definition, use, error))
        self.assertEqual(_macro_names(tuple(_walk(root)), source), frozenset({"X"}))
        self.assertTrue(_has_preprocessor_definition_ancestor(definition_use))
        self.assertFalse(_has_preprocessor_definition_ancestor(use))

        class Grammar:
            @staticmethod
            def language(): return "capsule"
        class Parser:
            def __init__(self, _language): pass
            def parse(self, _source): return SimpleNamespace(root_node=root)
        entity = make_source_file_entity("a.c", ("c",), "1")
        with patch("kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_c", Grammar), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Language", lambda x: x), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", Parser), patch("kb_scanner.frontends.cpp.tree_sitter_adapter.version", return_value="1"):
            first = TreeSitterCppAdapter()._parse_candidate(source, "a.c", entity, "c", "suffix", False)
            second = TreeSitterCppAdapter()._parse_candidate(source, "a.c", entity, "c", "suffix", False)
        self.assertEqual(first.error_count, 1)
        self.assertEqual(first.diagnostics[0].details["errorCount"], 1)
        self.assertEqual((2, 2), (first.diagnostics[0].location.line, first.diagnostics[0].location.column))
        self.assertTrue(all(item.confidence == "medium" for item in first.evidence))
        self.assertEqual([item.id for item in first.evidence], [item.id for item in second.evidence])
        expansions = [item for item in first.evidence if item.kind == "macro_expansion"]
        self.assertEqual(len(expansions), 1)
        object_replacement = [item for item in first.evidence if item.kind == "macro_replacement_token"]
        self.assertEqual([(item.value, item.metadata["tokenRole"]) for item in object_replacement], [("1", "number")])


class AsmBoundaryTests(unittest.TestCase):
    def test_unknown_asm_layout_and_local_error_are_diagnostics_not_child_candidates(self):
        source = b'asm("one");'
        class Grammar:
            @staticmethod
            def language(): return 'capsule'
        class Parser:
            def __init__(self, _): pass
            def parse(self, _): return SimpleNamespace(root_node=root)
        entity = make_source_file_entity('a.c', ('c',), '1')
        for error in (False, True):
            root = Node('translation_unit', children=(Node('future_asm', 0, len(source)), *((Node('ERROR', 0, 3, error=True),) if error else ())))
            with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_c', Grammar), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Language', lambda x: x), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser', Parser), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.version', return_value='1'):
                result = TreeSitterCppAdapter()._parse_candidate(source, 'a.c', entity, 'c', 'suffix', False)
            self.assertEqual((), result.evidence)
            self.assertEqual(1, len(result.diagnostics))
            self.assertEqual('tree-sitter.partial-parse' if error else 'tree-sitter.unsupported-asm-structure', result.diagnostics[0].code)

    def test_only_outer_constructs_and_unbounded_values(self):
        for container in ('gnu_asm_expression', 'attribute_declaration'):
            kind = 'declaration_attribute' if container == 'attribute_declaration' else 'inline_asm'
            nested = Node(container)
            child = Node('gnu_asm_input_operand', children=(nested,))
            root = Node(container, 0, 800, children=(child,))
            self.assertEqual(kind, _node_kind(root, b'x' * 800, False))
            self.assertIsNone(_node_kind(nested, b'x', False))
            self.assertIsNone(_node_kind(child, b'x', False))
            self.assertEqual(800, len(_node_value(root, b'x' * 800, kind)))
        for token in ('__asm__', 'ms_asm_block', 'gnu_asm_qualifier', 'gnu_asm_output_operand_list', 'gnu_asm_clobber_list', 'future_asm_child'):
            self.assertIsNone(_node_kind(Node(token), b'', False))

    def test_fake_parser_keeps_distinct_spans_partial_diagnostic_and_identity(self):
        source = b'asm("one"); asm("two");'
        root = Node('translation_unit', children=(Node('gnu_asm_expression', 0, 10), Node('gnu_asm_expression', 12, 22), Node('ERROR', 22, 22, error=True)))
        class Grammar:
            @staticmethod
            def language(): return 'capsule'
        class Parser:
            def __init__(self, _): pass
            def parse(self, _): return SimpleNamespace(root_node=root)
        entity = make_source_file_entity('a.c', ('c',), '1')
        for language in ('c', 'cpp'):
            with patch('kb_scanner.frontends.cpp.tree_sitter_adapter.tree_sitter_' + language, Grammar), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Language', lambda x: x), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser', Parser), patch('kb_scanner.frontends.cpp.tree_sitter_adapter.version', return_value='1'):
                a = TreeSitterCppAdapter()._parse_candidate(source, 'a.c', entity, language, 'suffix', False)
                b = TreeSitterCppAdapter()._parse_candidate(source, 'a.c', entity, language, 'suffix', False)
            self.assertEqual(a, b)
            self.assertEqual(2, len(a.evidence))
            self.assertNotEqual(a.evidence[0].id, a.evidence[1].id)
            self.assertEqual(1, len(a.diagnostics))
            self.assertTrue(all(x.confidence == 'medium' for x in a.evidence))
            self.assertTrue(a.evidence[0].metadata['structureComplete'])
            self.assertFalse(a.evidence[1].metadata['structureComplete'])


if __name__ == "__main__":
    unittest.main()
