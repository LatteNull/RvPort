from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb_scanner.analyzers import EvidenceGraphAnalyzer, GraphEntityIndexer, IncludeResolver, RelationBuilder
from kb_scanner.analyzers.evidence_graph import _branch_role
from kb_scanner.core import (
    CompletionStatus,
    Entity,
    Evidence,
    KnowledgeEntry,
    KnowledgeSnapshot,
    KnowledgeSource,
    NormalizedFact,
    NormalizedSnapshot,
    stable_id,
)
from tests.unit.evidence_graph.support import context, evidence, file, knowledge, snapshot, span


def macro_fixture() -> tuple[NormalizedSnapshot, dict[str, Evidence]]:
    main = file("main.c")
    header = file("support.h")
    include = evidence(main, "include", "support.h", 1)
    definition = evidence(header, "macro_definition", "FAST", 2, end_line=3, metadata={"nodeType": "preproc_function_def"})
    parameter = evidence(
        header,
        "macro_parameter",
        "x",
        2,
        metadata={"macroDefinitionEvidenceId": definition.id, "ordinal": 0, "tokenRole": "parameter"},
    )
    replacement = evidence(
        header,
        "macro_replacement_token",
        "_mm_add_ps",
        3,
        metadata={"macroDefinitionEvidenceId": definition.id, "ordinal": 0, "tokenRole": "call_candidate"},
    )
    invocation = evidence(main, "call_expression", "FAST", 5)
    return snapshot(main, header, evidence_items=(include, definition, parameter, replacement, invocation)), {
        "include": include,
        "definition": definition,
        "parameter": parameter,
        "replacement": replacement,
        "invocation": invocation,
    }


class GraphEntityIndexerTests(unittest.TestCase):
    def test_indexer_builds_stable_entities_for_files_macros_calls_and_branches(self) -> None:
        normalized, items = macro_fixture()
        condition = evidence(normalized.entities[0], "preprocessor_condition", "defined(__AVX__)", 4, end_line=8, metadata={"nodeType": "preproc_if"})
        fallback = evidence(normalized.entities[0], "preprocessor_branch", "else", 7, end_line=8, metadata={"nodeType": "preproc_else"})
        normalized = NormalizedSnapshot(normalized.entities, (*normalized.evidence, condition, fallback), ())
        with tempfile.TemporaryDirectory() as raw:
            first = GraphEntityIndexer().index(context(Path(raw)), normalized, knowledge())
            second = GraphEntityIndexer().index(context(Path(raw)), normalized, knowledge())
        self.assertEqual(tuple(first.entities), tuple(second.entities))
        self.assertEqual(len(first.files_by_path), 2)
        self.assertIn("FAST", first.definitions_by_name)
        self.assertIn(items["definition"].id, first.definition_by_evidence)
        self.assertTrue(first.invocation_entities)
        self.assertEqual({item.role for item in first.branches}, {"x86", "fallback"})

    def test_indexer_rejects_unknown_subject_and_keeps_same_name_definitions_distinct(self) -> None:
        left, right = file("left.h"), file("right.h")
        first = evidence(left, "macro_definition", "SAME", 1)
        second = evidence(right, "macro_definition", "SAME", 1)
        with tempfile.TemporaryDirectory() as raw:
            index = GraphEntityIndexer().index(context(Path(raw)), snapshot(left, right, evidence_items=(first, second)), knowledge())
            self.assertEqual(len(index.definitions_by_name["SAME"]), 2)
            invalid = Evidence(stable_id("bad-evidence"), "include", stable_id("missing"), "x.h", "p", "m", "high")
            with self.assertRaises(ValueError):
                GraphEntityIndexer().index(context(Path(raw)), snapshot(left, evidence_items=(invalid,)), knowledge())

    def test_indexer_distinguishes_compilation_contexts_and_accepts_missing_span(self) -> None:
        source = file("main.c")
        first = Evidence(
            stable_id("context-call", 1),
            "call_expression",
            source.id,
            "run",
            "clang",
            "syntax",
            "high",
            span(source.name, 1),
            metadata={"compilationContextId": stable_id("context", 1)},
        )
        second = Evidence(
            stable_id("context-call", 2),
            "call_expression",
            source.id,
            "run",
            "clang",
            "syntax",
            "high",
            first.location,
            metadata={"compilationContextId": stable_id("context", 2)},
        )
        definition_without_span = Evidence(
            stable_id("definition-without-span"),
            "macro_definition",
            source.id,
            "NO_SPAN",
            "unit",
            "syntax",
            "medium",
        )
        normalized = snapshot(source, evidence_items=(first, second, definition_without_span))
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as other_raw:
            left = GraphEntityIndexer().index(context(Path(raw)), normalized, knowledge())
            right = GraphEntityIndexer().index(context(Path(other_raw)), normalized, knowledge())
        call_sites = [item for item in left.entities.values() if item.kind == "call_site"]
        self.assertEqual(len(call_sites), 2)
        self.assertEqual(tuple(left.entities), tuple(right.entities))
        self.assertIsNone(left.definition_by_evidence[definition_without_span.id].location)


class IncludeResolverTests(unittest.TestCase):
    def test_resolver_handles_direct_suffix_ambiguous_external_and_unsafe(self) -> None:
        main, direct, one, two = (file(path) for path in ("src/main.c", "src/support.h", "a/x.h", "b/x.h"))
        with tempfile.TemporaryDirectory() as raw:
            index = GraphEntityIndexer().index(context(Path(raw)), snapshot(main, direct, one, two), knowledge())
        resolver = IncludeResolver(index)
        self.assertEqual(resolver.resolve(main, "support.h")[:2], ((direct,), "complete"))
        self.assertEqual(resolver.resolve(main, "a/x.h")[:2], ((one,), "complete"))
        ambiguous, status, reason = resolver.resolve(main, "x.h")
        self.assertEqual((len(ambiguous), status, reason), (2, "partial", "ambiguous-include"))
        external, status, reason = resolver.resolve(main, "stdio.h")
        self.assertEqual((external[0].kind, status, reason), ("external_header", "unknown", "unresolved-include"))
        unsafe, status, reason = resolver.resolve(main, "../secret.h")
        self.assertEqual((unsafe[0].properties["resolution"], status, reason), ("unsafe", "unknown", "unsafe-include-path"))


class RelationBuilderTests(unittest.TestCase):
    def test_builder_creates_macro_include_call_and_definition_relations(self) -> None:
        normalized, items = macro_fixture()
        original_include = items["include"]
        second_include = Evidence(
            stable_id("second-include"),
            original_include.kind,
            original_include.subject_id,
            original_include.value,
            "second-producer",
            original_include.parse_mode,
            original_include.confidence,
            original_include.location,
        )
        normalized = NormalizedSnapshot(normalized.entities, (*normalized.evidence, second_include), normalized.facts)
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, diagnostics = RelationBuilder(ctx, normalized, knowledge(), index).build()
        kinds = {item.kind for item in relations}
        self.assertTrue({"defines", "includes", "calls", "invokes_macro", "expands_to"} <= kinds)
        self.assertNotIn("reachable_from", kinds)
        self.assertFalse(diagnostics)
        include_relation = next(item for item in relations if item.kind == "includes")
        self.assertEqual(include_relation.evidence_ids, tuple(sorted((original_include.id, second_include.id))))
        definition = index.definition_by_evidence[items["definition"].id]
        macro_calls = [item for item in relations if item.kind == "calls" and item.source_id == definition.id]
        self.assertEqual(len(macro_calls), 1)
        self.assertEqual(macro_calls[0].evidence_ids, (items["replacement"].id,))
        self.assertFalse(any(item.kind == "calls" and items["definition"].id in item.evidence_ids for item in relations))

    def test_builder_keeps_ambiguous_include_but_accepts_equivalent_macro_definitions(self) -> None:
        main, left, right = file("main.c"), file("a/x.h"), file("b/x.h")
        include = evidence(main, "include", "x.h", 1)
        left_def = evidence(left, "macro_definition", "FAST", 1)
        right_def = evidence(right, "macro_definition", "FAST", 1)
        call = evidence(main, "call_expression", "FAST", 3)
        normalized = snapshot(main, left, right, evidence_items=(include, left_def, right_def, call))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, diagnostics = RelationBuilder(ctx, normalized, knowledge(), index).build()
        self.assertEqual(len([item for item in relations if item.kind == "includes"]), 2)
        self.assertTrue(all(item.status == "partial" for item in relations if item.kind == "includes"))
        self.assertTrue(all(item.status == "complete" for item in relations if item.kind == "invokes_macro"))
        self.assertTrue(any(item.code == "graph.include-ambiguous-include" for item in diagnostics))

    def test_builder_propagates_unsupported_replacement_semantics(self) -> None:
        source = file("main.c")
        definition = evidence(source, "macro_definition", "JOIN", 1)
        replacement = evidence(
            source,
            "macro_replacement_token",
            "_mm_add_ps",
            1,
            metadata={
                "macroDefinitionEvidenceId": definition.id,
                "ordinal": 0,
                "tokenRole": "call_candidate",
                "unsupportedSemantics": ("token-pasting",),
            },
        )
        normalized = snapshot(source, evidence_items=(definition, replacement))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, _ = RelationBuilder(ctx, normalized, knowledge(), index).build()
        replacement_relations = [item for item in relations if item.kind in {"calls", "expands_to"}]
        self.assertTrue(replacement_relations)
        self.assertTrue(all(item.status == "partial" for item in replacement_relations))
        self.assertTrue(all(item.metadata["reason"] == "unsupported-preprocessor-semantics" for item in replacement_relations))

    def test_builder_propagates_partial_parse_confidence(self) -> None:
        source, header = file("main.c"), file("partial.h")
        location = span(source.name, 1)
        include = Evidence(
            stable_id("partial-include"),
            "include",
            source.id,
            "partial.h",
            "unit",
            "recovered-syntax",
            "medium",
            location,
        )
        normalized = snapshot(source, header, evidence_items=(include,))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, _ = RelationBuilder(ctx, normalized, knowledge(), index).build()
        relation = next(item for item in relations if item.kind == "includes")
        self.assertEqual((relation.status, relation.metadata["reason"]), ("partial", "partial-evidence"))

    def test_builder_links_nested_macro_and_branch_alternative(self) -> None:
        source = file("main.c")
        header = file("fast.h")
        outer = evidence(source, "preprocessor_condition", "defined(__AVX__)", 1, end_line=8, metadata={"nodeType": "preproc_if"})
        fallback = evidence(source, "preprocessor_branch", "else", 5, end_line=8, metadata={"nodeType": "preproc_else"})
        include = evidence(source, "include", "fast.h", 2)
        first = evidence(source, "macro_definition", "A", 2)
        second = evidence(source, "macro_definition", "B", 3)
        replacement_a = evidence(source, "macro_replacement_token", "B", 2, metadata={"macroDefinitionEvidenceId": first.id, "ordinal": 0, "tokenRole": "call_candidate"})
        replacement_b = evidence(source, "macro_replacement_token", "_mm_add_ps", 3, metadata={"macroDefinitionEvidenceId": second.id, "ordinal": 0, "tokenRole": "call_candidate"})
        call = evidence(source, "call_expression", "A", 4)
        fallback_call = evidence(source, "call_expression", "portable", 6)
        normalized = snapshot(source, header, evidence_items=(outer, fallback, include, first, second, replacement_a, replacement_b, call, fallback_call))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, _ = RelationBuilder(ctx, normalized, knowledge(), index).build()
        kinds = [item.kind for item in relations]
        self.assertIn("alternative_to", kinds)
        self.assertGreaterEqual(kinds.count("guarded_by"), 2)
        implementation_alternatives = [
            item
            for item in relations
            if item.kind == "alternative_to"
            and index.entities[item.source_id].kind == "implementation"
            and index.entities[item.target_id].kind == "implementation"
        ]
        self.assertTrue(implementation_alternatives)
        include_site = next(item for item in index.entities.values() if item.kind == "include_site")
        self.assertTrue(any(item.kind == "guarded_by" and item.source_id == include_site.id for item in relations))
        self.assertTrue(any(item.kind == "expands_to" and item.target_id == index.definition_by_evidence[second.id].id for item in relations))

    def test_nested_and_adjacent_condition_groups_do_not_create_cross_group_alternatives(self) -> None:
        source = file("main.c")
        outer = evidence(
            source,
            "preprocessor_condition",
            "defined(__AVX__)",
            1,
            end_line=10,
            metadata={"nodeType": "preproc_if"},
        )
        nested = evidence(
            source,
            "preprocessor_condition",
            "defined(__riscv)",
            2,
            end_line=5,
            metadata={"nodeType": "preproc_if"},
        )
        nested_else = evidence(
            source,
            "preprocessor_branch",
            "else",
            4,
            end_line=5,
            metadata={"nodeType": "preproc_else"},
        )
        outer_else = evidence(
            source,
            "preprocessor_branch",
            "else",
            9,
            end_line=10,
            metadata={"nodeType": "preproc_else"},
        )
        adjacent = evidence(
            source,
            "preprocessor_condition",
            "defined(portable)",
            11,
            end_line=13,
            metadata={"nodeType": "preproc_if"},
        )
        normalized = snapshot(source, evidence_items=(outer, nested, nested_else, outer_else, adjacent))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            index = GraphEntityIndexer().index(ctx, normalized, knowledge())
            relations, _ = RelationBuilder(ctx, normalized, knowledge(), index).build()
        alternatives = [item for item in relations if item.kind == "alternative_to"]
        self.assertEqual(len(alternatives), 2)
        self.assertTrue(all(item.metadata["targetRole"] == "fallback" for item in alternatives))
        self.assertEqual(len({item.group.id for item in index.branches}), 3)


class EvidenceGraphAnalyzerTests(unittest.TestCase):
    def test_analyzer_materializes_cross_file_macro_proof_and_unknown_reachability(self) -> None:
        normalized, items = macro_fixture()
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            first = EvidenceGraphAnalyzer().analyze(ctx, normalized, knowledge())
            second = EvidenceGraphAnalyzer().analyze(ctx, normalized, knowledge())
        self.assertEqual(first, second)
        self.assertEqual(first.status, CompletionStatus.PARTIAL)
        self.assertTrue(first.value.proof_paths)
        proof = next(item for item in first.value.proof_paths if len(item.relation_ids) >= 2)
        self.assertEqual(proof.status, "complete")
        self.assertTrue(any(item.kind == "reachable_from" and item.metadata["proofPathId"] == proof.id for item in first.value.relations))
        definition_entity = next(item for item in first.value.entities if item.kind == "macro_definition")
        self.assertFalse(any(item.kind == "calls" and item.source_id == definition_entity.id and items["definition"].id in item.evidence_ids for item in first.value.relations))

    def test_empty_and_invalid_snapshots_have_explicit_results(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            empty = EvidenceGraphAnalyzer().analyze(ctx, NormalizedSnapshot(), knowledge())
            invalid_subject = stable_id("missing")
            ev = Evidence(stable_id("evidence"), "include", invalid_subject, "x.h", "p", "m", "high")
            failed = EvidenceGraphAnalyzer().analyze(ctx, NormalizedSnapshot(evidence=(ev,)), knowledge())
        self.assertEqual(empty.status, CompletionStatus.COMPLETE)
        self.assertEqual((empty.value.relations, empty.value.proof_paths), ((), ()))
        self.assertEqual(failed.status, CompletionStatus.FAILED)
        self.assertTrue(failed.diagnostics[0].affects_exit_code)

    def test_unconnected_source_does_not_receive_unproved_reachability(self) -> None:
        source = file("main.c")
        with tempfile.TemporaryDirectory() as raw:
            result = EvidenceGraphAnalyzer().analyze(context(Path(raw)), snapshot(source), knowledge())
        self.assertFalse(any(item.kind == "reachable_from" for item in result.value.relations))

    def test_invalid_fact_relation_and_indexer_failures_are_converted_to_diagnostics(self) -> None:
        subject = file("main.c")
        ev = evidence(subject, "include", "x.h", 1)
        fact = NormalizedFact(stable_id("fact"), "include", subject.id, "x.h", "scope", (stable_id("missing"),))
        bad_facts = NormalizedSnapshot((subject,), (ev,), (fact,))
        with tempfile.TemporaryDirectory() as raw:
            ctx = context(Path(raw))
            failed_fact = EvidenceGraphAnalyzer().analyze(ctx, bad_facts, knowledge())
            with patch.object(GraphEntityIndexer, "index", side_effect=KeyError("bad")):
                failed_index = EvidenceGraphAnalyzer().analyze(ctx, snapshot(subject), knowledge())
        self.assertEqual({failed_fact.status, failed_index.status}, {CompletionStatus.FAILED})
        self.assertTrue(all(item.diagnostics[0].code == "graph.invalid-analysis-input" for item in (failed_fact, failed_index)))

    def test_branch_role_can_use_x86_knowledge_provenance(self) -> None:
        source = file("main.c")
        condition = evidence(source, "preprocessor_condition", "defined(MY_X86)", 1, end_line=3, metadata={"nodeType": "preproc_if"})
        ks = KnowledgeSource(stable_id("source"), "curated", "curated-json-v1", "curated.json", "a" * 64)
        entry = KnowledgeEntry(stable_id("entry"), "architectureAliases", "x86", "my_x86", (ks.id,))
        with tempfile.TemporaryDirectory() as raw:
            index = GraphEntityIndexer().index(
                context(Path(raw)), snapshot(source, evidence_items=(condition,)), KnowledgeSnapshot(stable_id("k"), "1", (ks,), (entry,))
            )
        self.assertEqual(index.branches[0].role, "x86")
        self.assertEqual(index.branches[0].knowledge_ids, (entry.id,))

    def test_negated_x86_condition_is_not_mislabeled_as_x86(self) -> None:
        source = file("main.c")
        condition = evidence(
            source,
            "preprocessor_condition",
            "!defined(__AVX__)",
            1,
            end_line=3,
            metadata={"nodeType": "preproc_if"},
        )
        with tempfile.TemporaryDirectory() as raw:
            index = GraphEntityIndexer().index(context(Path(raw)), snapshot(source, evidence_items=(condition,)), knowledge())
        self.assertEqual(index.branches[0].role, "unknown")

    def test_branch_roles_cover_supported_tokens_and_ignore_comment_words(self) -> None:
        cases = {
            "defined(__riscv)": "riscv",
            "defined(generic)": "generic",
            "defined(portable)": "portable",
            "defined(scalar)": "scalar",
            "defined(__AVX__)": "x86",
            "defined(FEATURE) /* AVX is mentioned only in a comment */": "unknown",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(_branch_role(value, knowledge(), fallback=False)[0], expected)
        self.assertEqual(_branch_role("else", knowledge(), fallback=True)[0], "fallback")


if __name__ == "__main__":
    unittest.main()
