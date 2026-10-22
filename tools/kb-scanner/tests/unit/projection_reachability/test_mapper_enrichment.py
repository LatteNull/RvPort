from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kb_scanner.core import (
    AnalysisSnapshot, Entity, Evidence, FrontendSnapshot, Relation, SourceLocation, SourceSpan, stable_id,
)
from kb_scanner.projection import CompatibilityMapper
from tests.unit.compatible_cutover.support import graph


class MapperEnrichmentTests(unittest.TestCase):
    def test_trace_closes_macro_definition_and_preserves_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = list(graph(Path(tmp)))
            source = args[3].entities[0]
            definition_evidence = Evidence(stable_id("macro-definition-evidence"), "macro_definition", source.id, "M", "unit", "ast", "high")
            definition = Entity(stable_id("macro-definition"), "macro_definition", "M", properties={"sourceEvidenceId": definition_evidence.id})
            relation = args[5].relations[0]
            enriched_relation = replace(relation, target_id=definition.id)
            args[3] = FrontendSnapshot((*args[3].entities, definition), (*args[3].evidence, definition_evidence))
            args[5] = AnalysisSnapshot((enriched_relation,), (*args[5].entities, definition), ())
            observation = replace(args[7].observations[0], relation_ids=(enriched_relation.id,), metadata={"role": "x86"})
            classification = replace(args[7].classifications[0], observation_ids=(observation.id,), relation_ids=(enriched_relation.id,), proof_path_ids=())
            args[6] = replace(args[6], observations=(observation,))
            args[7] = replace(args[7], observations=(observation,), classifications=(classification,))
            args[8] = replace(args[8], assessments=())
            value = CompatibilityMapper().map(*args)
        finding = value["findings"][0]
        self.assertEqual("_mm_add_ps", finding["symbol"])
        self.assertEqual(1, finding["trace"]["occurrenceCount"])
        self.assertIn("macro_definition", {item["kind"] for item in finding["trace"]["evidence"]})
        self.assertEqual("complete", finding["trace"]["referenceClosure"]["status"])

    def test_call_primary_and_occurrence_spans_select_the_symbol_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = list(graph(Path(tmp)))
            original = args[3].evidence[0]
            call = replace(
                original,
                kind="call_expression",
                value="_mm_add_ps",
                location=SourceSpan(
                    SourceLocation("main.c", 7, 5),
                    SourceLocation("main.c", 7, 29),
                ),
            )
            args[3] = replace(args[3], evidence=(call,))
            classification = replace(args[7].classifications[0], evidence_ids=(call.id,))
            observation = replace(args[7].observations[0], evidence_ids=(call.id,))
            args[6] = replace(args[6], observations=(observation,))
            args[7] = replace(args[7], observations=(observation,), classifications=(classification,))
            args[8] = replace(args[8], assessments=())
            value = CompatibilityMapper().map(*args)
        finding = value["findings"][0]
        expected = {
            "file": "main.c",
            "start": {"line": 7, "column": 5},
            "end": {"line": 7, "column": 15},
        }
        self.assertEqual(expected, finding["trace"]["primarySpan"])
        self.assertEqual(expected, finding["trace"]["occurrences"][0]["span"])
        self.assertEqual(29, finding["trace"]["evidence"][0]["location"]["end"]["column"])

    def test_occurrences_keep_independent_configuration_status_and_incomplete_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = list(graph(Path(tmp)))
            original = args[3].evidence[0]
            selected = replace(
                original,
                kind="build_argument",
                value="-mavx",
                metadata={"configuration": "cfg-a", "selectionStatus": "selected"},
            )
            unknown = Evidence(
                stable_id("second-occurrence"), "build_argument", original.subject_id, "-mavx",
                "unit", "static-build", "medium", None,
                metadata={"configuration": "cfg-b", "selectionStatus": "unknown"},
            )
            args[3] = FrontendSnapshot(args[3].entities, (unknown, selected))
            classification = replace(
                args[7].classifications[0], evidence_ids=(unknown.id, selected.id)
            )
            args[7] = replace(args[7], classifications=(classification,))
            args[8] = replace(args[8], assessments=())
            first = CompatibilityMapper().map(*args)["findings"][0]["trace"]
            args[3] = FrontendSnapshot(args[3].entities, (selected, unknown))
            second = CompatibilityMapper().map(*args)["findings"][0]["trace"]
        self.assertEqual(first["occurrences"], second["occurrences"])
        self.assertEqual(2, first["occurrenceCount"])
        self.assertEqual(
            [("cfg-a", "selected", "complete"), ("cfg-b", "unknown", "partial")],
            [
                (item["configuration"], item["selectionStatus"], item["completeness"])
                for item in first["occurrences"]
            ],
        )
        self.assertIsNone(first["occurrences"][1]["span"])


if __name__ == "__main__":
    unittest.main()
