import unittest
from dataclasses import replace
from unittest.mock import patch
from kb_scanner.analyzers.cmake_selection import analyze_cmake
from kb_scanner.analyzers.build_selection import BuildSelectionAnalyzer
from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
from kb_scanner.core import Entity,Evidence,NormalizedFact,NormalizedSnapshot,FrontendSnapshot,AnalysisSnapshot,SourceLocation,SourceSpan,stable_id,StageResult,CompletionStatus,KnowledgeEntry,KnowledgeSnapshot,Relation
from kb_scanner.detectors.build_selection import BuildSelectionDetector
from kb_scanner.normalization.build import BuildEvidenceNormalizer
from tests.unit.build_selection.support import context,flag_knowledge


def snapshot(*entries):
    owner=Entity(stable_id('cmake-owner'),'build_file','CMakeLists.txt')
    evidence,facts=[],[]
    for index,(key,kind,value,info,state) in enumerate(entries):
        metadata={'cmake':{'key':key,**info},'selectionStatus':state,'configuration':'cmake:riscv64'}
        e=Evidence(stable_id('cmake-e',key),kind,owner.id,value,'unit','static-build','high',
                   SourceSpan(SourceLocation('CMakeLists.txt',index+1,1),SourceLocation('CMakeLists.txt',index+1,2)),metadata=metadata)
        evidence.append(e)
        facts.append(NormalizedFact(stable_id('cmake-f',key),kind,owner.id,value,'cmake:'+key,(e.id,),metadata=metadata))
    return NormalizedSnapshot((owner,),tuple(evidence),tuple(facts))


class GraphTests(unittest.TestCase):
    def test_source_closure_and_multiple_membership_uncertainty(self):
        source=Entity(stable_id('source'),'source_file','v.cpp')
        e=Evidence(stable_id('intrinsic-e'),'call_expression',source.id,'_mm_add_ps','unit','ast','high')
        local=NormalizedFact(stable_id('intrinsic-f'),'symbol',source.id,'_mm_add_ps','local',(e.id,))
        unrelated=replace(local,id=stable_id('unrelated-f'),canonical_value='ordinary')
        k=flag_knowledge()
        entry=KnowledgeEntry(stable_id('intrinsic-k'),'intrinsics','x86','_mm_add_ps',(k.sources[0].id,))
        k=replace(k,entries=(entry,))
        for state in ('selected','inactive','unknown'):
            f=snapshot(('src','build_source','v.cpp',{'source':'v.cpp'},state))
            f=replace(f,entities=(*f.entities,source),evidence=(*f.evidence,e),facts=(*f.facts,local,unrelated))
            a=analyze_cmake(context(),f,k,AnalysisSnapshot(),100,100).value
            deps=[r for r in a.relations if r.metadata.get('itemKind')=='source_x86_dependency']
            self.assertEqual(1,len(deps))
            self.assertEqual(state,deps[0].status)
            guard=Relation(stable_id('guard'),'guarded_by',source.id,source.id,(e.id,),status='unknown')
            a=analyze_cmake(context(),f,k,AnalysisSnapshot((guard,),(source,)),100,100).value
            self.assertTrue(all(r.status=='unknown' for r in a.relations if r.metadata.get('itemKind')=='source_x86_dependency'))
        f2=snapshot(('other','build_source','v.cpp',{'source':'v.cpp'},'selected'))
        f=replace(f,facts=(*f.facts,*f2.facts),evidence=(*f.evidence,*f2.evidence))
        a=analyze_cmake(context(),f,k,AnalysisSnapshot(),100,100).value
        self.assertTrue(all(r.status=='unknown' for r in a.relations if r.metadata.get('itemKind')=='source_x86_dependency'))
        a=analyze_cmake(context(),f,k,AnalysisSnapshot(),0,0)
        self.assertTrue(a.diagnostics)

    def test_rejection_chain_classifier_and_normalization(self):
        facts=snapshot(('condition','build_condition','riscv',{},'selected'),
                       ('reject','build_arch_constraint','FATAL_ERROR',{'parents':('condition',),'rejection':True,'required':True},'selected'))
        normalized=BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot(facts.entities,facts.evidence)).value
        self.assertEqual(2,len(normalized.facts))
        self.assertTrue(all(f.scope.startswith('cmake:') for f in normalized.facts))
        analysis=analyze_cmake(context(),facts,flag_knowledge(),AnalysisSnapshot(),100,100).value
        detected=BuildSelectionDetector().detect(context(),facts,analysis,flag_knowledge()).value.observations
        self.assertEqual(1,len(detected))
        obs=detected[0]
        self.assertEqual('blocking_issue',DEFAULT_CLASSIFICATION_POLICY.decide(obs,proof_complete=True,relation_unknown=False).impact)
        self.assertEqual('unknown',DEFAULT_CLASSIFICATION_POLICY.decide(obs,proof_complete=False,relation_unknown=False).impact)
        self.assertEqual('unknown',DEFAULT_CLASSIFICATION_POLICY.decide(replace(obs,metadata={**obs.metadata,'cmake':{'rejection':True,'required':False}}),proof_complete=True,relation_unknown=False).impact)
        self.assertEqual(2,max(len(p.relation_ids) for p in analysis.proof_paths))

    def test_argument_effective_vs_declaration_and_target_unknown(self):
        facts=snapshot(('raw','build_argument','-mavx2',{},'selected'),
                       ('use','build_argument','-mavx2',{'parents':('raw',),'effective':True},'unknown'))
        analysis=analyze_cmake(context(),facts,flag_knowledge('-mavx2'),AnalysisSnapshot(),100,100).value
        observations=BuildSelectionDetector().detect(context(),facts,analysis,flag_knowledge('-mavx2')).value.observations
        self.assertEqual(1,len(observations))
        self.assertEqual('confirmed_local',observations[0].status)
        self.assertEqual('build_selection_unknown',observations[0].kind)
        named=snapshot(('src','build_source','avx.cpp',{'source':'avx.cpp'},'selected'))
        analysis=analyze_cmake(context(),named,flag_knowledge(),AnalysisSnapshot(),100,100).value
        observations=BuildSelectionDetector().detect(context(),named,analysis,flag_knowledge()).value.observations
        self.assertEqual('build_selection_unknown',observations[0].kind)
        self.assertEqual('candidate',observations[0].status)

    def test_missing_cycle_and_budgets(self):
        cases=[snapshot(('a','build_condition','a',{'parents':('missing',)},'selected')),
               snapshot(('a','build_condition','a',{'parents':('b',)},'selected'),('b','build_condition','b',{'parents':('a',)},'selected'))]
        for facts in cases:
            result=analyze_cmake(context(),facts,flag_knowledge(),AnalysisSnapshot(),100,100)
            self.assertTrue(result.diagnostics)
            self.assertTrue(all(p.status=='unknown' for p in result.value.proof_paths))
        facts=snapshot(('a','build_source','missing.cpp',{'source':'missing.cpp'},'selected'))
        result=analyze_cmake(context(),facts,flag_knowledge(),AnalysisSnapshot(),100,100)
        self.assertTrue(any('source-unavailable' in d.message for d in result.diagnostics))
        for relation_budget,path_budget in ((0,100),(100,0)):
            result=analyze_cmake(context(),facts,flag_knowledge(),AnalysisSnapshot(),relation_budget,path_budget)
            self.assertTrue(result.diagnostics)
            self.assertLessEqual(len(result.value.relations),relation_budget)

    def test_orchestration_preserves_inherited_budget_and_failures(self):
        facts=snapshot(('a','build_condition','ON',{},'selected'))
        result=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge())
        self.assertTrue(result.value.relations)
        with patch('kb_scanner.analyzers.build_macro_binding.bind_build_macros',return_value=True) as binding:
            result=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge())
        binding.assert_called_once()
        self.assertEqual(100000,binding.call_args.kwargs['max_relations'])
        self.assertTrue(any(d.code=='build-selection.macro-budget' for d in result.diagnostics))
        bad=replace(facts,entities=())
        self.assertEqual(CompletionStatus.FAILED,BuildSelectionAnalyzer().analyze(context(),bad,flag_knowledge()).status)
