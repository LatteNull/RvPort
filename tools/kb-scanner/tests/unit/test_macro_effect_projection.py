from types import SimpleNamespace as NS
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import unittest

from kb_scanner.projection.v2.evidence_kinds import proven_macro_terminals
from kb_scanner.projection.v2.mapper import V2FindingMapper
from kb_scanner.projection.v2.chain import EvidenceChainBuilder
from kb_scanner.projection.v2.index import SnapshotIndex
from tests.unit.schema_v2_projection.support import graph, report


class MacroEffectProjectionTests(unittest.TestCase):
    def test_only_complete_proven_terminals_have_call_labels(self):
        relations = [NS(status='complete',metadata={'macroEffect':{'proven':True,'terminalEvidenceId':'terminal'}}),
                     NS(status='unknown',metadata={'macroEffect':{'proven':True,'terminalEvidenceId':'unknown'}}),
                     NS(status='complete',metadata={})]
        self.assertEqual(frozenset({'terminal'}),proven_macro_terminals(relations))

    def test_macro_terminal_projection_reuses_schema_and_context(self):
        values = list(graph(Path('/synthetic')))
        original = values[3].evidence[0]
        item = replace(original,kind='macro_argument_token')
        values[3] = replace(values[3],evidence=(item,))
        effect = {'invocationId':'call','terminalEvidenceId':item.id,'proven':True,'translationUnit':'src/main.c','active':True,'buildBound':True}
        values[5] = replace(values[5],relations=tuple(replace(r,status='complete',metadata={**r.metadata,'macroEffect':effect}) for r in values[5].relations))
        index = SnapshotIndex.build(values[2],values[3],values[4],values[5],values[6],values[7],values[8])
        source = Mock(project=Mock(return_value=report().findings[0].fact.primaryLocation))
        chain = Mock(build=Mock(return_value=report().findings[0].evidenceChain))
        finding = V2FindingMapper(index,chain,source).map(values[7])[0]
        self.assertEqual('intrinsic_call',finding.fact.kind)
        builder = EvidenceChainBuilder(index,values[2],source)
        self.assertEqual('intrinsic_call',builder._evidence_step(item).kind)
        self.assertTrue(finding.conclusion.suggestion_en)

    def test_multiple_configuration_states_are_separate_and_extension_is_bounded(self):
        from kb_scanner.projection.v2.macro_effects import MacroEffectsProjection
        relations = []
        for name,active,proven in (('one',True,True),('two',False,True),('three',None,False)):
            relations.append(NS(metadata={'configuration':name,'macroEffect':{
                'terminalEvidenceId':'token','translationUnit':'src/main.c','active':active,
                'buildBound':True,'proven':proven,'reasonCodes':('unproven',) if not proven else ()}}))
        projection = MacroEffectsProjection(relations)
        self.assertEqual(('one','three','two'),projection.configurations('token'))
        self.assertEqual('selected',projection.uses['token']['one']['selectionStatus'])
        self.assertEqual('inactive',projection.uses['token']['two']['selectionStatus'])
        self.assertEqual('unknown',projection.uses['token']['three']['proofStatus'])
        extension = projection.extension('token',limit=1)['org.rvport.kb-scanner.macro-effects']
        self.assertTrue(extension['truncated'])
        self.assertEqual(3,extension['totalUses'])
        self.assertTrue(extension['uses'][0]['description_en'])
        self.assertEqual({},projection.extension('absent'))
