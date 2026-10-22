"""用途投影与 HTML 的纯快照单元测试，无原生 parser。"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch
import copy
import html

from kb_scanner.core import KnowledgeSnapshot, AnalysisSnapshot, stable_id
from kb_scanner.analyzers.candidate_usage.analysis import CandidateUsageAnalyzer, CATALOG_KIND
from kb_scanner.classifiers.migration import MigrationClassifier
from kb_scanner.detectors.local import LocalX86Detector
from kb_scanner.projection.v2.candidate_usage import CandidateUsageProjection, ProjectionBudget, NAMESPACE, render_usage_summary
from kb_scanner.projection.v2.context import SourceContextProjector
from tests.unit.test_usage_analysis import candidate_inputs
from tests.unit.knowledge_detection.support import make_context


def fixture(path):
    facts, _ = candidate_inputs()
    knowledge = KnowledgeSnapshot(stable_id("knowledge"), "1")
    context = make_context(path)
    analysis = CandidateUsageAnalyzer().analyze(context, facts, knowledge, AnalysisSnapshot(entities=facts.entities)).value
    detections = LocalX86Detector(deferred_capabilities={}).detect(context, facts, analysis, knowledge).value
    classifications = MigrationClassifier().classify(context, detections, analysis).value
    return SimpleNamespace(entities={e.id: e for e in analysis.entities},
        relations={e.id: e for e in analysis.relations}, proofs={e.id: e for e in analysis.proof_paths},
        evidence={e.id: e for e in facts.evidence}, facts={e.id: e for e in facts.facts},
        observations={e.id: e for e in classifications.observations}, classifications={})


class UsageProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / "a.c").write_text("// <script>&\"\n" * 30)
        self.index = fixture(self.path)
        self.context = SourceContextProjector(self.path)

    def test_excluded_root_is_self_contained_with_real_context(self):
        projection = CandidateUsageProjection(self.index, self.context)
        report = projection.report()[NAMESPACE]
        self.assertEqual(1, report["excludedCount"])
        item = report["excludedCandidates"][0]
        self.assertEqual("excluded", item["status"])
        self.assertEqual("X86", item["symbol"])
        self.assertTrue(item["explanation_en"])
        self.assertTrue(item["sources"])
        self.assertEqual("a.c", item["sources"][0]["file"])
        self.assertEqual(20, item["sources"][0]["context"]["budget"]["afterLines"])
        self.assertTrue(item["sources"][0]["context"]["highlights"])
        for forbidden in ("factId", "recordIds", "evidenceId", "relationIds", "proofId"):
            self.assertNotIn('"'+forbidden+'"', json.dumps(report))
        self.assertEqual(report, projection.report()[NAMESPACE])
        self.assertEqual(1, len(projection.decisions))

    def test_source_json_is_equal_to_original_and_shared_only_within_projection(self):
        projection = CandidateUsageProjection(self.index, self.context)
        span = next(e.location for e in self.index.evidence.values() if e.location)
        first = projection._source_view(span)
        self.assertEqual(self.context.project(span).model_dump(mode='json', exclude_none=True), first)
        self.assertIs(first, projection._source_view(span))
        shifted = replace(span, start=replace(span.start, line=2), end=replace(span.end, line=2))
        second = projection._source_view(shifted)
        self.assertEqual(self.context.project(shifted).model_dump(mode='json', exclude_none=True), second)
        self.assertIs(first['context']['lines'][0], second['context']['lines'][0])
        fresh = CandidateUsageProjection(self.index, self.context)._source_view(span)
        self.assertEqual(first, fresh)
        self.assertIsNot(first['context']['lines'][0], fresh['context']['lines'][0])
        missing = replace(span, start=replace(span.start, path='missing.c'), end=replace(span.end, path='missing.c'))
        self.assertEqual('unavailable', projection._source_view(missing)['context']['status'])

    def test_classified_complete_and_partial_proof_are_not_claimed_excluded(self):
        observation = next(iter(self.index.observations.values()))
        self.index.classifications = {"kept": SimpleNamespace(observation_ids=(observation.id,))}
        projection = CandidateUsageProjection(self.index, self.context)
        self.assertEqual(0, projection.report()[NAMESPACE]["excludedCount"])
        finding = projection.finding((observation,))[NAMESPACE]
        self.assertEqual("unknown", finding["roots"][0]["status"])
        self.index.classifications = {}
        self.index.proofs = {key: replace(proof, status="partial", truncated=True) for key, proof in self.index.proofs.items()}
        projection = CandidateUsageProjection(self.index, self.context)
        self.assertEqual(0, projection.report()[NAMESPACE]["excludedCount"])
        self.assertIn("candidate-semantic-proof-incomplete-or-conflicting", projection.finding((observation,))[NAMESPACE]["roots"][0]["reasonCodes"])

    def test_empty_duplicate_and_invalid_budget(self):
        observation = next(iter(self.index.observations.values()))
        catalog = next(entity for entity in self.index.entities.values() if entity.kind == CATALOG_KIND)
        self.index.entities["duplicate"] = catalog
        with self.assertRaises(ValueError): CandidateUsageProjection(self.index, self.context)
        del self.index.entities["duplicate"]
        self.index.entities[catalog.id] = replace(catalog, properties={**catalog.properties,
            "entries": (*catalog.properties["entries"], *catalog.properties["entries"])})
        with self.assertRaises(ValueError): CandidateUsageProjection(self.index, self.context)
        del self.index.entities[catalog.id]
        projection = CandidateUsageProjection(self.index, self.context)
        self.assertEqual({}, projection.report())
        self.assertEqual({}, projection.finding((observation,)))
        self.assertEqual("", render_usage_summary(None))
        empty = CandidateUsageProjection(SimpleNamespace(entities={}), self.context)
        self.assertIsNone(empty.gate)
        self.assertEqual({}, empty.report())
        self.assertEqual({}, empty.finding((observation,)))
        for value in (-1, True, "1", 101):
            with self.assertRaises(ValueError): ProjectionBudget(excluded=value)

    def test_clipping_missing_sources_and_missing_fact_are_explicit(self):
        observation = next(iter(self.index.observations.values()))
        projection = CandidateUsageProjection(self.index, self.context, ProjectionBudget(excluded=0, roots=0))
        self.assertEqual(1, projection.report()[NAMESPACE]["omittedExcludedCandidates"])
        self.assertEqual(1, projection.finding((observation,))[NAMESPACE]["omittedRoots"])
        projection = CandidateUsageProjection(self.index, self.context, ProjectionBudget(sources=0))
        item = projection.report()[NAMESPACE]["excludedCandidates"][0]
        self.assertEqual("partial", item["projectionStatus"])
        self.assertEqual(item["sourceCount"], item["omittedSources"])
        self.assertFalse(item["sources"])
        self.index.evidence.clear()
        self.index.facts.clear()
        item = CandidateUsageProjection(self.index, self.context).report()[NAMESPACE]["excludedCandidates"][0]
        self.assertEqual("", item["symbol"])
        self.assertGreater(item["missingSources"], 0)

    def test_html_escapes_symbols_paths_and_code_and_shows_counts(self):
        projection = CandidateUsageProjection(self.index, self.context)
        view = projection.report()
        item = view[NAMESPACE]["excludedCandidates"][0]
        item["symbol"] = '<img src="x" onerror="bad()">'
        item["sources"][0]["file"] = "<script>"
        rendered = render_usage_summary(view)
        self.assertIn("排除总数 1", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertIn("<mark>", rendered)
        self.assertIn("候选根 1", render_usage_summary(projection.finding(self.index.observations.values())))

    def test_multiple_roots_share_finding_source_budget(self):
        observation = next(iter(self.index.observations.values()))
        other = replace(observation, id=stable_id("another-observation"))
        projection = CandidateUsageProjection(self.index, self.context, ProjectionBudget(sources=1))
        view = projection.finding((other, observation))[NAMESPACE]
        self.assertEqual(2, view["rootCount"])
        self.assertEqual(1, sum(len(root["sources"]) for root in view["roots"]))
        self.assertTrue(all(root["omittedSources"] > 0 for root in view["roots"]))
        self.assertEqual(view, projection.finding((observation, other))[NAMESPACE])

    def test_html_shared_sources_render_once_without_changing_bytes_or_leaking_between_calls(self):
        view = CandidateUsageProjection(self.index, self.context).report()
        record = view[NAMESPACE]["excludedCandidates"][0]
        source = record["sources"][0]
        source["context"]["lines"][0]["text"] = '<unique-source>&"'
        record["sources"] = [source, source]
        view[NAMESPACE]["excludedCandidates"].append(record)
        independent = copy.deepcopy(view)
        independent[NAMESPACE]["excludedCandidates"] = [
            {**record, "sources": [copy.deepcopy(source), copy.deepcopy(source)]}
            for _ in range(2)]
        expected = render_usage_summary(independent)
        with patch("kb_scanner.projection.v2.candidate_usage.html.escape", wraps=html.escape) as escaped:
            actual = render_usage_summary(view)
        self.assertEqual(expected, actual)
        self.assertEqual(1, sum(call.args[0] == '<unique-source>&"' for call in escaped.call_args_list))
        self.assertEqual(4, actual.count('&lt;unique-source&gt;&amp;&quot;'))
        source["context"]["lines"][0]["text"] = '<updated>'
        updated = render_usage_summary(view)
        self.assertNotIn('unique-source', updated)
        self.assertEqual(4, updated.count('&lt;updated&gt;'))

    def test_usage_source_has_twenty_lines_each_side_and_exact_hit(self):
        (self.path / "a.c").write_text("// <script>&\" padding padding\n" * 60)
        def shifted(item):
            span = item.location
            if span is None:
                return item
            return replace(item, location=replace(span,
                start=replace(span.start, line=span.start.line+24),
                end=replace(span.end, line=span.end.line+24)))
        self.index.evidence = {key: shifted(item) for key, item in self.index.evidence.items()}
        self.index.entities = {key: shifted(item) for key, item in self.index.entities.items()}
        view = CandidateUsageProjection(self.index, SourceContextProjector(self.path)).report()[NAMESPACE]
        source = view["excludedCandidates"][0]["sources"][0]
        self.assertEqual(25, source["span"]["start"]["line"])
        self.assertEqual(list(range(5, 46)), [line["line"] for line in source["context"]["lines"]])
        self.assertEqual(25, source["context"]["highlights"][0]["line"])
        self.assertEqual(5, source["context"]["highlights"][0]["startColumn"])
        missing = SourceContextProjector(self.path, reader=lambda _: (_ for _ in ()).throw(OSError("missing")))
        source = CandidateUsageProjection(self.index, missing).report()[NAMESPACE]["excludedCandidates"][0]["sources"][0]
        self.assertEqual("unavailable", source["context"]["status"])
        self.assertIn("context_unavailable", source["context"]["reasonCodes"])


if __name__ == "__main__":
    unittest.main()
