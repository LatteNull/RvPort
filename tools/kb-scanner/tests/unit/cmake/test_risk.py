import unittest
from dataclasses import replace
from types import SimpleNamespace
from kb_scanner.classifiers.risk import present_risk, confirmed_dependency
from kb_scanner.classifiers import MigrationClassifier
from kb_scanner.core import DetectionSnapshot, AnalysisSnapshot
from kb_scanner.projection.v2.suggestions import select_suggestion, SUGGESTIONS
from tests.unit.compatible_cutover.support import graph
from pathlib import Path


class RiskTests(unittest.TestCase):
    def test_shared_march_name_is_not_confirmed_x86_even_when_selected(self):
        from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
        values=graph(Path('/fixture'))
        for flag in ('-march=rv64gc','-march=native','-mtune=generic','-mcpu=unknown','--target=riscv64'):
            obs=replace(values[6].observations[0],kind='x86_compiler_flag',metadata={'compilerFlagValue':flag})
            self.assertFalse(confirmed_dependency(obs))
            decision=DEFAULT_CLASSIFICATION_POLICY.decide(obs,proof_complete=True,relation_unknown=False,selected_reachable=True)
            self.assertEqual('unknown',decision.impact)
            risk=present_risk(replace(values[7].classifications[0],impact=decision.impact),obs)
            self.assertEqual(('medium','unknown',False),(risk.severity,risk.status,risk.blocking))
        self.assertTrue(confirmed_dependency(replace(obs,metadata={'compilerFlagValue':'-mavx2'})))

    def test_guard_metadata_alone_is_not_an_exclusion_proof(self):
        from kb_scanner.core import Relation, stable_id
        values=graph(Path('/fixture'))
        obs=replace(values[6].observations[0],metadata={'branchRole':'x86'},relation_ids=())
        cls=MigrationClassifier().classify(values[0],DetectionSnapshot((obs,)),AnalysisSnapshot()).value.classifications[0]
        self.assertNotEqual('guarded_inactive',cls.impact)
        guard=Relation(stable_id('local-guard'),'guarded_by',stable_id('a'),stable_id('b'),status='complete')
        obs=replace(obs,relation_ids=(guard.id,))
        analysis=AnalysisSnapshot((guard,))
        cls=MigrationClassifier().classify(values[0],DetectionSnapshot((obs,)),analysis).value.classifications[0]
        self.assertEqual('guarded_inactive',cls.impact)
        include=replace(guard,id=stable_id('unread-system-header'),kind='includes',status='unknown')
        linked=replace(obs,relation_ids=(guard.id,include.id))
        cls=MigrationClassifier().classify(values[0],DetectionSnapshot((linked,)),replace(analysis,relations=(guard,include))).value.classifications[0]
        self.assertEqual('guarded_inactive',cls.impact)
        cls=MigrationClassifier().classify(values[0],DetectionSnapshot((obs,)),replace(analysis,relations=(replace(guard,status='partial'),))).value.classifications[0]
        self.assertNotEqual('guarded_inactive',cls.impact)

    def test_only_relevant_unknown_paths_can_invalidate_selection(self):
        from kb_scanner.core import Relation, ProofPath, stable_id
        from tests.unit.classification_assessment.support import context, proof_analysis
        analysis,obs=proof_analysis(status='selected')
        terminal=replace(analysis.relations[-1],metadata={'itemKind':'source_x86_dependency'})
        irrelevant=Relation(stable_id('unrelated'), 'includes', terminal.source_id, terminal.target_id, status='unknown')
        partial=ProofPath(stable_id('unrelated-proof'),terminal.source_id,terminal.target_id,(irrelevant.id,),'partial','include-unavailable',2,False)
        obs=replace(obs,relation_ids=(*obs.relation_ids,irrelevant.id))
        analysis=replace(analysis,relations=(*analysis.relations[:-1],terminal,irrelevant),proof_paths=(*analysis.proof_paths,partial))
        cls=MigrationClassifier().classify(context(),DetectionSnapshot((obs,)),analysis).value.classifications[0]
        self.assertEqual('blocking_issue',cls.impact)
        self.assertIn(partial.id,cls.proof_path_ids)
        incomplete=replace(analysis,proof_paths=tuple(replace(p,status='partial') for p in analysis.proof_paths))
        self.assertNotEqual('blocking_issue',MigrationClassifier().classify(context(),DetectionSnapshot((obs,)),incomplete).value.classifications[0].impact)
        inactive=replace(terminal,status='inactive')
        analysis=replace(analysis,relations=(*analysis.relations[:-2],inactive))
        obs=replace(obs,relation_ids=(inactive.id,),kind='x86_intrinsic_reference',status='confirmed_local')
        self.assertEqual('guarded_inactive',MigrationClassifier().classify(context(),DetectionSnapshot((obs,)),analysis).value.classifications[0].impact)

    def test_priority_is_not_certainty(self):
        values=graph(Path('/fixture'))
        obs,classification=values[6].observations[0],values[7].classifications[0]
        for status in ('complete','partial','unknown','ambiguous'):
            risk=present_risk(replace(classification,impact='actionable_non_blocking',metadata={'completeness':status}),obs)
            self.assertEqual('high',risk.severity)
            self.assertTrue(risk.actionable)
            self.assertFalse(risk.blocking)
            self.assertNotEqual('complete',risk.status)
        self.assertFalse(confirmed_dependency(None))
        self.assertFalse(confirmed_dependency(replace(obs,metadata={'rpm':{'softDependency':True}})))
        self.assertFalse(confirmed_dependency(replace(obs,knowledge_ids=())))

    def test_impact_matrix_and_incomplete_blocker(self):
        for impact, expected in [('unknown',('medium','unknown',False,False)),('hint',('info','complete',False,False)),
                                 ('guarded_inactive',('low','inactive',False,False)),('blocking_issue',('high','complete',True,True)),
                                 ('actionable_non_blocking',('medium','complete',True,False))]:
            risk=present_risk(SimpleNamespace(impact=impact,metadata={}))
            self.assertEqual(expected,(risk.severity,risk.status,risk.actionable,risk.blocking))
        self.assertFalse(present_risk(SimpleNamespace(impact='blocking_issue',metadata={'completeness':'partial'})).blocking)
        self.assertEqual('ambiguous',present_risk(SimpleNamespace(impact='unknown',metadata={}),SimpleNamespace(status='ambiguous')).status)
        with self.assertRaises(ValueError): present_risk(SimpleNamespace(impact='new',metadata={}))

    def test_confirmed_header_with_unknown_target_stays_high(self):
        values=graph(Path('/fixture'))
        obs=replace(values[6].observations[0],kind='x86_header_reference',relation_ids=())
        result=MigrationClassifier().classify(values[0],DetectionSnapshot((obs,)),AnalysisSnapshot())
        cls=result.value.classifications[0]
        self.assertEqual('partial',cls.metadata['completeness'])
        self.assertEqual('high',present_risk(cls,obs).severity)
        self.assertFalse(present_risk(cls,obs).blocking)
        macro=replace(obs,kind='x86_platform_macro_reference')
        result=MigrationClassifier().classify(values[0],DetectionSnapshot((macro,)),AnalysisSnapshot())
        self.assertEqual('unknown',result.value.classifications[0].impact)

    def test_new_bilingual_advice(self):
        self.assertEqual(SUGGESTIONS['local'],select_suggestion('actionable_non_blocking','partial','x86_header_reference',confirmed_local=True))
        self.assertEqual(SUGGESTIONS['configuration_rejected'],select_suggestion('blocking_issue','complete','missing_riscv_selection_path',reason='cmake-target-configuration-rejected'))
        self.assertEqual(SUGGESTIONS['unknown'],select_suggestion('unknown','unknown','missing_riscv_selection_path',reason='cmake-target-configuration-rejected'))
