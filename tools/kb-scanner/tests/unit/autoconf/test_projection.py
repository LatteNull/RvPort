import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from kb_scanner.projection.v2.chain import EvidenceChainBuilder
from kb_scanner.projection.v2.context import SourceContextProjector
from kb_scanner.projection.v2.mapper import V2FindingMapper
from tests.unit.schema_v2_projection.support import graph, report


class ProjectionTests(unittest.TestCase):
    def test_existing_extensions_carry_version_and_scope_in_fact_occurrence_and_step(self):
        values = graph(Path("/synthetic"))
        info = {"digest": "a" * 64, "unit": "configure", "outcome": "unknown", "bound": False,
                "reason": "autoconf-target-environment-unknown", "scope": "current-file-bytes"}
        evidence = replace(values[3].evidence[0], kind="build_configuration", metadata={"autoconf": info})
        observation = values[6].observations[0]
        index = SimpleNamespace(knowledge={}, observations={observation.id: observation}, evidence={evidence.id: evidence},
                                entities={}, relations={}, facts={})
        context = Mock(spec=SourceContextProjector)
        context.project.return_value = report().findings[0].fact.primaryLocation
        chain = Mock(spec=EvidenceChainBuilder)
        chain.build.return_value = report().findings[0].evidenceChain
        finding = V2FindingMapper(index, chain, context).map(values[7])[0]
        self.assertEqual(finding.fact.extensions["org.rvport.kb-scanner.autoconf"], info)
        self.assertEqual(finding.occurrences[0].extensions["org.rvport.kb-scanner.autoconf"], info)
        builder = EvidenceChainBuilder(index, values[2], context)
        step = builder._evidence_step(evidence)
        self.assertEqual(step.extensions["org.rvport.kb-scanner.autoconf"], info)
        self.assertEqual(step.kind, "source_evidence")
        self.assertTrue(finding.conclusion.suggestion)
        self.assertTrue(finding.conclusion.suggestion_en)
