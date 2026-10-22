from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kb_scanner.projection.v2.chain import EvidenceChainBuilder
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.index import SnapshotIndex
from kb_scanner.projection.v2.mapper import V2FindingMapper, _severity, _status
from .support import graph_with_source, graph, report


class FindingMapperTests(unittest.TestCase):
    def test_function_and_family_namespaces_coexist(self):
        values=graph(Path('/synthetic'))
        historical=report().findings[0]
        source=Mock(spec=SourceContextProjector)
        source.project.return_value=historical.fact.primaryLocation
        chain=Mock(spec=EvidenceChainBuilder)
        chain.build.return_value=historical.evidenceChain
        index=SimpleNamespace(entities={},relations={},knowledge={e.id:e for e in values[2].entries},
            observations={o.id:o for o in values[6].observations},evidence={e.id:e for e in values[3].evidence})
        mapper=V2FindingMapper(index,chain,source)
        mapper._families=Mock(finding=Mock(return_value={'org.rvport.kb-scanner.architecture-family':{'marker':'family'}}))
        mapper._multiversion=Mock(finding=Mock(return_value={'org.rvport.kb-scanner.function-multiversion':{'marker':'function'}}))
        mapper._usage=Mock(finding=Mock(return_value={'org.rvport.kb-scanner.candidate-usage':{'marker':'usage'}}))
        result=mapper.map(values[7])[0]
        self.assertEqual({'org.rvport.kb-scanner.architecture-family':{'marker':'family'},
            'org.rvport.kb-scanner.function-multiversion':{'marker':'function'},
            'org.rvport.kb-scanner.candidate-usage':{'marker':'usage'}}, result.fact.extensions)

    def test_fake_boundaries_preserve_every_non_suggestion_field(self):
        values = graph(Path("/synthetic"))
        original = values[7].classifications[0]
        observation = values[6].observations[0]
        historical = report().findings[0]
        source = Mock(spec=SourceContextProjector)
        source.project.return_value = historical.fact.primaryLocation
        chain = Mock(spec=EvidenceChainBuilder)
        chain.build.return_value = historical.evidenceChain
        index = SimpleNamespace(entities={}, relations={}, knowledge={item.id: item for item in values[2].entries},
                                observations={observation.id: observation},
                                evidence={item.id: item for item in values[3].evidence})
        for impact in ("blocking_issue", "actionable_non_blocking", "unknown", "hint", "guarded_inactive"):
            for missing_observation in (False, True):
                with self.subTest(impact=impact, missing=missing_observation):
                    classification = replace(original, impact=impact, observation_ids=() if missing_observation else original.observation_ids)
                    snapshot = replace(values[7], classifications=(classification,))
                    mapper = V2FindingMapper(index, chain, source)
                    with patch("kb_scanner.projection.v2.mapper.select_suggestion", return_value=SimpleNamespace(zh="old advice", en="old English")):
                        before = mapper.map(snapshot)[0].model_dump(mode="json", exclude_none=True)
                    after = mapper.map(snapshot)[0].model_dump(mode="json", exclude_none=True)
                    conclusion = after["conclusion"]
                    self.assertRegex(conclusion["suggestion"], r"[\u4e00-\u9fff]")
                    self.assertTrue(conclusion["suggestion_en"].isascii())
                    if missing_observation and impact in {"blocking_issue", "actionable_non_blocking"}:
                        self.assertIn("保留该事实", conclusion["suggestion"])
                    for value in (before, after):
                        for field in ("suggestion", "suggestion_en"):
                            del value["conclusion"][field]
                    self.assertEqual(before, after)
                    self.assertEqual(historical.evidenceChain.model_dump(mode="json", exclude_none=True), after["evidenceChain"])
        chain.build.assert_called()
        source.project.assert_called_with(values[3].evidence[0].location)

    def test_maps_fact_conclusion_occurrence_and_chain_without_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            values = graph_with_source(Path(temp))
            context, _, knowledge, frontend, facts, analysis, detections, classifications, assessments, _ = values
            source = SourceContextProjector(context.input_root)
            index = SnapshotIndex.build(knowledge, frontend, facts, analysis, detections, classifications, assessments)
            findings = V2FindingMapper(index, EvidenceChainBuilder(index, knowledge, source), source).map(classifications)
            self.assertEqual(1, len(findings))
            finding = findings[0]
            self.assertEqual("intrinsic_call", finding.fact.kind)
            self.assertTrue(finding.conclusion.blocking)
            self.assertEqual(finding.occurrences[0].id, finding.primaryOccurrenceId)
            self.assertFalse(hasattr(finding, "trace"))

    def test_missing_location_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as temp:
            values = list(graph_with_source(Path(temp)))
            evidence = values[3].evidence[0]
            from kb_scanner.core import Evidence, FrontendSnapshot
            values[3] = FrontendSnapshot(values[3].entities, (Evidence(evidence.id, evidence.kind, evidence.subject_id, evidence.value, evidence.producer, evidence.parse_mode, evidence.confidence),))
            source = SourceContextProjector(Path(temp))
            index = SnapshotIndex.build(values[2], values[3], values[4], values[5], values[6], values[7], values[8])
            self.assertEqual((), V2FindingMapper(index, EvidenceChainBuilder(index, values[2], source), source).map(values[7]))

    def test_status_and_severity_vocabulary(self):
        from types import SimpleNamespace
        self.assertEqual("inactive", _status(SimpleNamespace(impact="guarded_inactive", metadata={}), None))
        self.assertEqual("ambiguous", _status(SimpleNamespace(impact="unknown", metadata={"completeness": "ambiguous"}), None))
        self.assertEqual("unknown", _status(SimpleNamespace(impact="unknown", metadata={}), SimpleNamespace(status="unknown")))
        self.assertEqual("unknown", _status(SimpleNamespace(impact="unknown", metadata={}), None))
        self.assertEqual(["high", "medium", "low", "info", "medium"], [_severity(item) for item in ("blocking_issue", "actionable_non_blocking", "guarded_inactive", "hint", "unknown")])
