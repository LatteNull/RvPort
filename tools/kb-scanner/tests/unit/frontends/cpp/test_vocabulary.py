from __future__ import annotations

import unittest

from kb_scanner.core import Entity, Evidence, SourceLocation, SourceSpan, stable_id
from kb_scanner.frontends.cpp.vocabulary import (
    CPP_EVIDENCE_KINDS,
    entity_sort_key,
    evidence_sort_key,
    make_evidence,
    make_source_file_entity,
)
from tests.unit.frontends.cpp.support import span


class VocabularyTests(unittest.TestCase):
    def test_source_entity_is_stable_and_normalizes_languages(self) -> None:
        first = make_source_file_entity("src/main.cpp", ("cpp", "c", "cpp"), "1.2.3")
        second = make_source_file_entity("src/main.cpp", ("c", "cpp"), "1.2.3")
        self.assertEqual(first, second)
        self.assertEqual(first.name, "src/main.cpp")
        self.assertEqual(first.properties["languageCandidates"], ("c", "cpp"))
        self.assertEqual(first.properties["identityVersion"], 1)
        self.assertNotEqual(first.id, make_source_file_entity("src/main.cpp", ("c", "cpp"), "2").id)

    def test_every_supported_evidence_kind_preserves_fields_and_identity(self) -> None:
        subject = make_source_file_entity("main.c", ("c",), "1").id
        for kind in sorted(CPP_EVIDENCE_KINDS):
            with self.subTest(kind=kind):
                item = make_evidence(
                    kind=kind,
                    subject_id=subject,
                    value={"name": "x", "items": [1, True]},
                    producer="fake@1",
                    parse_mode="unit",
                    confidence="high",
                    span=span(),
                    metadata={"nested": {"b": 2}},
                    context_id="ctx",
                )
                repeated = make_evidence(
                    kind=kind, subject_id=subject, value={"items": [1, True], "name": "x"},
                    producer="fake@1", parse_mode="unit", confidence="low", span=span(),
                    metadata={"ignoredByIdentity": True}, context_id="ctx",
                )
                self.assertEqual(item.id, repeated.id)
                self.assertEqual(item.metadata["compilationContextId"], "ctx")
                self.assertEqual(item.metadata["identityVersion"], 1)
                self.assertEqual(item.producer, "fake@1")

    def test_context_changes_identity_and_metadata_is_frozen(self) -> None:
        subject = make_source_file_entity("a.c", ("c",), "1").id
        plain = make_evidence(kind="include", subject_id=subject, value="x.h", producer="p", parse_mode="m", confidence="high", span=span("a.c"))
        scoped = make_evidence(kind="include", subject_id=subject, value="x.h", producer="p", parse_mode="m", confidence="high", span=span("a.c"), metadata={"a": [1]}, context_id="one")
        self.assertNotEqual(plain.id, scoped.id)
        self.assertNotIn("compilationContextId", plain.metadata)
        with self.assertRaises(TypeError):
            scoped.metadata["x"] = 1

    def test_invalid_kind_subject_span_and_json_are_rejected(self) -> None:
        subject = make_source_file_entity("a.c", ("c",), "1").id
        common = dict(subject_id=subject, producer="p", parse_mode="m", confidence="high", span=span("a.c"))
        with self.assertRaises(ValueError):
            make_evidence(kind="unknown", value="x", **common)
        with self.assertRaises(ValueError):
            make_evidence(kind="include", subject_id="bad", value="x", producer="p", parse_mode="m", confidence="high", span=span("a.c"))
        with self.assertRaises(ValueError):
            SourceSpan(SourceLocation("a.c", 2, 1), SourceLocation("a.c", 1, 1))
        with self.assertRaises(TypeError):
            make_evidence(kind="include", value=object(), **common)
        with self.assertRaises(TypeError):
            make_evidence(kind="include", value="x", metadata={"bad": object()}, **common)

    def test_sort_keys_cover_locations_producer_context_and_entity_ties(self) -> None:
        entity_a = Entity(stable_id("a"), "source_file", "a.c")
        entity_b = Entity(stable_id("b"), "source_file", "b.c")
        self.assertLess(entity_sort_key(entity_a), entity_sort_key(entity_b))
        subject = entity_a.id
        located = make_evidence(kind="include", subject_id=subject, value="a", producer="b", parse_mode="m", confidence="h", span=span("a.c"), context_id="z")
        same_span = make_evidence(kind="include", subject_id=subject, value="b", producer="a", parse_mode="m", confidence="h", span=span("a.c"), context_id="a")
        unlocated = Evidence(stable_id("unlocated"), "include", subject, "x", "p", "m", "h")
        self.assertLess(evidence_sort_key(unlocated), evidence_sort_key(located))
        self.assertLess(evidence_sort_key(same_span), evidence_sort_key(located))


if __name__ == "__main__":
    unittest.main()
