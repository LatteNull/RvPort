from __future__ import annotations

import unittest

from kb_scanner.analyzers import IncludeResolver, MacroDefinitionResolver
from kb_scanner.analyzers.evidence_graph import GraphIndex
from kb_scanner.core import Entity, Evidence, SourceLocation, SourceSpan, stable_id


def file(path: str) -> Entity:
    return Entity(stable_id("file", path), "source_file", path)


def definition(source: Entity, name: str, marker: str = "same", configuration: str | None = None):
    metadata = {"replacement": marker}
    if configuration:
        metadata["configuration"] = configuration
    evidence = Evidence(stable_id("evidence", source.name, name, marker, configuration), "macro_definition", source.id, name, "unit", "ast", "high", metadata=metadata)
    entity = Entity(stable_id("definition", evidence.id), "macro_definition", name, properties={"sourceEvidenceId": evidence.id})
    return evidence, entity


class MacroResolutionTests(unittest.TestCase):
    def test_missing_definition_evidence_cannot_establish_equivalence(self) -> None:
        source = file("a.c")
        first = Entity(stable_id("missing-one"), "macro_definition", "M")
        second = Entity(stable_id("missing-two"), "macro_definition", "M")
        invocation = Evidence(stable_id("missing-invoke"), "call_expression", source.id, "M", "unit", "ast", "high")
        resolver = MacroDefinitionResolver({first.id: source.id, second.id: source.id}, {})
        result = resolver.resolve(invocation, (first, second), {source.id})
        self.assertEqual(("partial", "ambiguous-macro-definition"), (result.status, result.reason))
        self.assertEqual({first.id, second.id}, {item.id for item in result.definitions})

    def test_unique_visible_and_equivalent_duplicates_are_complete(self) -> None:
        source, left, right = file("a/main.c"), file("a/include/x.h"), file("b/include/x.h")
        invocation = Evidence(stable_id("invoke"), "call_expression", source.id, "M", "unit", "ast", "high")
        first_ev, first = definition(left, "M")
        second_ev, second = definition(right, "M")
        resolver = MacroDefinitionResolver({first.id: left.id, second.id: right.id}, {first_ev.id: first_ev, second_ev.id: second_ev})
        unique = resolver.resolve(invocation, (second, first), {source.id, left.id})
        self.assertEqual((first,), unique.definitions)
        self.assertEqual("complete", unique.status)
        equivalent = resolver.resolve(invocation, (second, first), {source.id, left.id, right.id})
        self.assertEqual("complete", equivalent.status)

    def test_non_equivalent_and_configuration_conflicts_remain_conservative(self) -> None:
        source, left, right = file("main.c"), file("a.h"), file("b.h")
        invocation = Evidence(stable_id("invoke", "cfg"), "call_expression", source.id, "M", "unit", "ast", "high", metadata={"configuration": "cfg-a"})
        left_ev, left_def = definition(left, "M", "left", "cfg-a")
        right_ev, right_def = definition(right, "M", "right", "cfg-b")
        resolver = MacroDefinitionResolver({left_def.id: left.id, right_def.id: right.id}, {left_ev.id: left_ev, right_ev.id: right_ev})
        configured = resolver.resolve(invocation, (right_def, left_def), {left.id, right.id})
        self.assertEqual((left_def,), configured.definitions)
        unresolved = resolver.resolve(invocation, (), set())
        self.assertEqual(("unknown", "unresolved-macro"), (unresolved.status, unresolved.reason))
        no_cfg = Evidence(stable_id("invoke", "no-cfg"), "call_expression", source.id, "M", "unit", "ast", "high")
        ambiguous = resolver.resolve(no_cfg, (right_def, left_def), {left.id, right.id})
        self.assertEqual(("partial", "ambiguous-macro-definition"), (ambiguous.status, ambiguous.reason))

    def test_include_resolver_prefers_unique_nearest_component(self) -> None:
        main, near, far = file("component/src/main.c"), file("component/include/x.h"), file("other/include/x.h")
        index = GraphIndex(
            entities={item.id: item for item in (main, near, far)},
            project=main,
            files_by_id={item.id: item for item in (main, near, far)},
            files_by_path={item.name: item for item in (main, near, far)},
            implementations_by_file={},
            evidence_entities={},
            definitions_by_name={},
            definition_by_evidence={},
            definition_file={},
            invocation_entities=(),
            symbol_entities=(),
            branches=(),
        )
        resolved, status, reason = IncludeResolver(index).resolve(main, "x.h")
        self.assertEqual((near,), resolved)
        self.assertEqual(("complete", None), (status, reason))

    def test_definition_position_and_include_order_select_only_visible_prior_definition(self) -> None:
        source = file("main.c")
        early_ev, early = definition(source, "M", "early")
        late_ev, late = definition(source, "M", "late")
        early_ev = Evidence(
            early_ev.id, early_ev.kind, early_ev.subject_id, early_ev.value, early_ev.producer,
            early_ev.parse_mode, early_ev.confidence,
            SourceSpan(SourceLocation("main.c", 2, 1), SourceLocation("main.c", 2, 10)),
            {**early_ev.metadata, "definitionOrder": 1},
        )
        late_ev = Evidence(
            late_ev.id, late_ev.kind, late_ev.subject_id, late_ev.value, late_ev.producer,
            late_ev.parse_mode, late_ev.confidence,
            SourceSpan(SourceLocation("main.c", 9, 1), SourceLocation("main.c", 9, 10)),
            {**late_ev.metadata, "definitionOrder": 3},
        )
        invocation = Evidence(
            stable_id("invoke", "ordered"), "call_expression", source.id, "M", "unit", "ast", "high",
            SourceSpan(SourceLocation("main.c", 5, 4), SourceLocation("main.c", 5, 8)),
            {"definitionOrder": 2},
        )
        resolver = MacroDefinitionResolver(
            {early.id: source.id, late.id: source.id},
            {early_ev.id: early_ev, late_ev.id: late_ev},
        )
        result = resolver.resolve(invocation, (late, early), {source.id})
        self.assertEqual("complete", result.status)
        self.assertEqual((early,), result.definitions)
        invisible = resolver.resolve(invocation, (early,), {stable_id("other-file")})
        self.assertEqual(("unknown", "unresolved-macro"), (invisible.status, invisible.reason))


if __name__ == "__main__":
    unittest.main()
