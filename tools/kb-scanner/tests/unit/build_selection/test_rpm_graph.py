import unittest
from dataclasses import replace
from kb_scanner.core import Entity,Evidence,FrontendSnapshot,SourceSpan,SourceLocation,stable_id,AnalysisSnapshot,StageResult,CompletionStatus
from kb_scanner.frontends.build.vocabulary import make_build_file_entity,make_build_evidence,BuildInputKind,BuildRecord
from kb_scanner.normalization import BuildEvidenceNormalizer
from kb_scanner.analyzers import BuildSelectionAnalyzer,BuildProofBudgets
from kb_scanner.detectors import BuildSelectionDetector
from kb_scanner.classifiers.policy import DEFAULT_CLASSIFICATION_POLICY
from tests.unit.build_selection.support import context,flag_knowledge
from unittest.mock import patch


def normalized(records):
    entity=make_build_file_entity('x.spec',BuildInputKind.RPM,'1')
    evidence=tuple(make_build_evidence(r,path='x.spec',subject_id=entity.id,producer='fake',input_kind=BuildInputKind.RPM) for r in records)
    return BuildEvidenceNormalizer().normalize(context(),FrontendSnapshot((entity,),evidence)).value


def record(key,kind='build_dependency',value='foo(x86-64)',parents=(),state='selected',**rpm):
    return BuildRecord(kind,value,len(key)+1,1,len(value)+1,{'selectionStatus':state,'rpm':{'key':key,'parents':parents,**rpm}})


class RpmGraphTests(unittest.TestCase):
    def test_graph_references_conditions_and_stable_proofs(self):
        facts=normalized([record('a','build_arch_probe','%{_arch}'),record('b','build_branch','%if',('a',),state='inactive'),
                          record('c',parents=('b',),state='inactive',x86Confirmed=True)])
        result=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge())
        self.assertEqual(CompletionStatus.COMPLETE,result.status)
        rel={r.id:r for r in result.value.relations}
        for p in result.value.proof_paths:
            self.assertEqual(p.source_id,rel[p.relation_ids[0]].source_id)
            self.assertEqual(p.target_id,rel[p.relation_ids[-1]].target_id)
            for a,b in zip(p.relation_ids,p.relation_ids[1:]): self.assertEqual(rel[a].target_id,rel[b].source_id)
        again=BuildSelectionAnalyzer().analyze(context(),replace(facts,facts=tuple(reversed(facts.facts))),flag_knowledge())
        self.assertEqual(result.value,again.value)
        obs=BuildSelectionDetector().detect(context(),facts,result.value,flag_knowledge()).value.observations
        self.assertEqual('build_inactive_x86_path',obs[0].kind)
        self.assertTrue(obs[0].metadata['matchedEvidenceIds'])

    def test_missing_cycle_budget_unknown_and_constraints(self):
        for records in ([record('a',parents=('missing',))], [record('a',parents=('b',)),record('b',parents=('a',))],
                        [record('a',state='unknown')],[record('a','build_argument','-mavx',buildUseKnown=False)]):
            facts=normalized(records)
            result=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge('-mavx'))
            self.assertEqual(CompletionStatus.PARTIAL,result.status)
            self.assertFalse(any(p.status=='complete' for p in result.value.proof_paths))
            by_id = {r.id:r for r in result.value.relations}
            for proof in result.value.proof_paths:
                self.assertEqual(proof.source_id,by_id[proof.relation_ids[0]].source_id)
                for left,right in zip(proof.relation_ids,proof.relation_ids[1:]):
                    self.assertEqual(by_id[left].target_id,by_id[right].source_id)
        records=[record('a'),record('b',parents=('a',)),record('c',parents=('a','b'))]
        facts=normalized(records)
        for budgets in (BuildProofBudgets(1,5),BuildProofBudgets(5,1)):
            result=BuildSelectionAnalyzer(budgets).analyze(context(),facts,flag_knowledge())
            self.assertEqual(CompletionStatus.PARTIAL,result.status)
            self.assertLessEqual(len(result.value.relations),budgets.max_relations)
            self.assertLessEqual(len(result.value.proof_paths),budgets.max_paths)
        facts=normalized([record('a','build_arch_constraint','x86_64',targetAllowed=False,valueKnown=True)])
        result=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge()).value
        self.assertTrue(any(r.metadata.get('issue')=='missing_riscv_selection_path' for r in result.relations))

    def test_detector_and_soft_policy(self):
        siblings=normalized([record('same1',value='pkg%{_isa}',targetAdaptive=True,architectureRelated=True),
                             record('same2',value='pkg%{_isa}',state='unknown',architectureRelated=True)])
        sibling_graph=BuildSelectionAnalyzer().analyze(context(),siblings,flag_knowledge()).value
        sibling_observations=BuildSelectionDetector().detect(context(),siblings,sibling_graph,flag_knowledge()).value.observations
        self.assertEqual(2,len(siblings.facts))
        self.assertEqual(['build_selection_unknown'],[o.kind for o in sibling_observations])
        facts=normalized([record('allowed','build_arch_constraint','riscv64 x86_64',targetAllowed=True,valueKnown=True,architectureRelated=True)])
        graph=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge()).value
        self.assertEqual((),BuildSelectionDetector().detect(context(),facts,graph,flag_knowledge()).value.observations)
        self.assertTrue(facts.facts)
        cases=[({'targetAdaptive':True,'architectureRelated':True},'foo%{_isa}',None),
               ({'architectureRelated':True},'foo%{external}', 'build_selection_unknown'),
               ({'x86Confirmed':True,'architectureRelated':True,'softDependency':True},'foo(x86-64)','build_selected_x86_dependency'),
               ({},'ordinary',None),({},'x86-only','build_selection_unknown')]
        for metadata,value,expected in cases:
            facts=normalized([record('a',value=value,**metadata)])
            graph=BuildSelectionAnalyzer().analyze(context(),facts,flag_knowledge()).value
            observations=BuildSelectionDetector().detect(context(),facts,graph,flag_knowledge()).value.observations
            self.assertEqual(expected,observations[0].kind if observations else None)
            if metadata.get('softDependency'):
                self.assertEqual('actionable_non_blocking',DEFAULT_CLASSIFICATION_POLICY.decide(observations[0],proof_complete=True,relation_unknown=False,selected_reachable=True).impact)
                self.assertEqual('unknown',DEFAULT_CLASSIFICATION_POLICY.decide(observations[0],proof_complete=False,relation_unknown=True).impact)

    def test_adapter_partition_failure_and_inherited_graph(self):
        facts=normalized([record('a')]);analyzer=BuildSelectionAnalyzer()
        original=BuildSelectionAnalyzer._analyze
        def fail_other(self,ctx,fs,k,base=AnalysisSnapshot()):
            if not any('rpm' in f.metadata for f in fs.facts): return StageResult(None,CompletionStatus.FAILED)
            return original(self,ctx,fs,k,base)
        with patch.object(BuildSelectionAnalyzer,'_analyze',fail_other):
            self.assertIsNone(analyzer.analyze(context(),facts,flag_knowledge()).value)
        base=AnalysisSnapshot(entities=(Entity(stable_id('unrelated'),'source_file','other.c'),))
        with_base=analyzer.analyze(context(),facts,flag_knowledge(),base).value
        self.assertEqual(analyzer.analyze(context(),facts,flag_knowledge()).value.relations,with_base.relations)
        from kb_scanner.core import Relation
        entity = base.entities[0]
        inherited = replace(base,relations=tuple(Relation(stable_id('old',i),'contains',entity.id,entity.id,(),status='selected') for i in range(1000)))
        small = BuildSelectionAnalyzer(BuildProofBudgets(1,1)).analyze(context(),facts,flag_knowledge(),base).value
        large = BuildSelectionAnalyzer(BuildProofBudgets(1,1)).analyze(context(),facts,flag_knowledge(),inherited).value
        self.assertEqual(small.relations,tuple(r for r in large.relations if 'rpm' in r.metadata))
        self.assertEqual(small.proof_paths,large.proof_paths)
        selector=Entity(stable_id('build_entity',1,'architecture_selector',context().target_arch),
                        'architecture_selector',context().target_arch,properties={'inherited':True})
        same=analyzer.analyze(context(),facts,flag_knowledge(),AnalysisSnapshot(entities=(selector,))).value
        self.assertEqual([selector],[e for e in same.entities if e.kind=='architecture_selector'])
